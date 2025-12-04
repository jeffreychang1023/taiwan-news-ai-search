# Completed Work Archive

This file contains detailed implementation history for completed tracks. Refer to this only when you need detailed context about past implementations.

---

## ✅ Track A: Analytics Logging Infrastructure (Week 1-2)

**Achievement**: Full analytics system deployed to production with PostgreSQL backend, Schema v2, parent query ID linking, and all foreign key issues resolved.

**Components Implemented**:

1. **Database Schema v2** (`code/python/core/analytics_db.py`, `code/python/core/query_logger.py`)
   - 4 core tables: queries, retrieved_documents, ranking_scores, user_interactions
   - 1 ML table: feature_vectors (35 columns for XGBoost training)
   - Dual database support: SQLite (local) + PostgreSQL (production via Neon.tech)
   - Auto-detection via `ANALYTICS_DATABASE_URL` environment variable
   - **Schema v2 changes**:
     - queries: +5 ML fields + parent_query_id
     - retrieved_documents: +9 ML fields (including bm25_score, keyword_overlap_ratio, doc_length)
     - ranking_scores: +3 ML fields (relative_score, score_percentile, schema_version)
     - user_interactions: +1 field (schema_version)

2. **Query Logger** (`code/python/core/query_logger.py`)
   - **Synchronous parent table writes**: `log_query_start()` writes directly to prevent race conditions
   - Async queue for child tables (retrieved_documents, ranking_scores, user_interactions)
   - Tracks full query lifecycle: start → retrieval → ranking → completion
   - User interaction tracking: clicks (left/middle/right), dwell time, scroll depth
   - Foreign key retry logic for PostgreSQL race conditions
   - **Query ID generation**: Backend-authoritative (format: `query_{timestamp}` - UUID suffix removed)
   - **Parent Query ID**: Links generate requests to their parent summarize requests

3. **Analytics API** (`code/python/webserver/analytics_handler.py`)
   - Dashboard endpoints: `/api/analytics/stats`, `/api/analytics/queries`, `/api/analytics/top-clicks`
   - CSV export: `/api/analytics/export` with UTF-8 BOM for Chinese characters
   - **Schema v2 export**: Now exports 29 columns (was 14) with all ML features
   - PostgreSQL dict_row compatibility (handles both dict and tuple formats)
   - **Parent query filtering**: Dashboard only shows parent queries (WHERE parent_query_id IS NULL)

4. **Dashboard** (`static/analytics-dashboard.html`)
   - Real-time metrics: total queries, avg latency, CTR, error rate
   - Recent queries table with click-through data (parent queries only)
   - Top clicked results tracking
   - Training data export functionality
   - **Parent Query Filter**: Only displays summarize requests, hides generate duplicates
   - **Cost column removed**: FinOps separate from ML ranking analytics

5. **Frontend Analytics Tracker** (`static/analytics-tracker-sse.js`, `static/news-search-prototype.html`)
   - **Uses SSE (Server-Sent Events), NOT WebSocket**
   - **Multi-click tracking** (commit 122c697):
     - Left click: `click` event listener
     - Middle click: `auxclick` event listener
     - Right click: `contextmenu` event listener
   - Batch event sending to `/api/analytics/event/batch`
   - **Query ID sync**: Frontend receives query_id from backend via "begin-nlweb-response" SSE message
   - **Parent Query ID**: Extracts query_id from summarize response and sends as parent_query_id to generate request

6. **Deployment**
   - Production database: Neon.tech PostgreSQL (free tier, 512MB)
   - Render deployment with health check at `/health`
   - $0/month cost (Render Free + Neon Free)

**Key Implementation Lessons**:
- ✅ Incremental deployment: Fix one method at a time to avoid service disruption
- ✅ PostgreSQL strictness: GROUP BY requirements, NULL handling, type safety
- ✅ Row format compatibility: Handle both dict (PostgreSQL) and tuple (SQLite)
- ✅ **Synchronous writes for parent tables**: Prevents foreign key race conditions
- ✅ **Analytics before cache checks**: Ensure logging even when using cached results
- ✅ **Multi-click tracking**: Support all click types for comprehensive analytics
- ✅ **Debug logging cleanup**: Remove console prints, use logger for production debugging

**Resolved Issues**:
1. **Async Queue Race Condition** (commit 743871e): Made `log_query_start()` synchronous
2. **Cache Early Return** (commit fc44ded): Moved analytics logging before cache check
3. **Missing parent_query_id Column**: Manual ALTER TABLE on PostgreSQL
4. **Query ID Format Inconsistency**: Changed from `query_{timestamp}_{uuid}` to `query_{timestamp}`
5. **Multi-Click Tracking Missing** (commit 122c697): Added `auxclick` and `contextmenu` listeners
6. **Batch Handler Missing Click Events** (commit 0e913c9): Added `result_clicked` case

---

## ✅ Track B: BM25 Implementation (Week 1-2)

**Goal**: Replace LLM keyword scoring with BM25 algorithm for consistent, fast keyword relevance.

**Status**: ✅ Implementation complete, ready for A/B testing

**What Was Built**:

1. **BM25 Scorer** (`code/python/core/bm25.py` - 733 lines)
   - Custom BM25 implementation (no external libraries)
   - Tokenization: Chinese 2-4 character sequences, English 2+ character words
   - Parameters: k1=1.5 (term saturation), b=0.75 (length normalization)
   - Corpus statistics: avg_doc_length, term_doc_counts calculated per query
   - IDF calculation with proper handling of rare/common terms
   - **Tested**: 19 unit tests, all passing ✅

2. **Intent Detection** (`code/python/retrieval_providers/qdrant.py:555-619`)
   - **Purpose**: Dynamically adjust α/β based on query intent
   - **EXACT_MATCH intent** (α=0.4, β=0.6): Prioritize BM25 for keyword matching
     - Indicators: quotes, numbers, hashtags, proper nouns, long queries (10+ chars)
   - **SEMANTIC intent** (α=0.7, β=0.3): Prioritize vector for conceptual search
     - Indicators: question words (什麼, how, why), concept words (趨勢, impact), short queries
   - **BALANCED intent** (default α/β): Mixed or unclear intent
   - **Scoring algorithm**: Feature-based with 2-point threshold for classification

3. **Qdrant Integration** (`code/python/retrieval_providers/qdrant.py`)
   - Hybrid scoring: `final_score = α * vector_score + β * bm25_score`
   - Intent-based α/β adjustment (replaces fixed weights)
   - Title weighting: 3x repetition in document text
   - Score storage: `point_scores = {}` dictionary (avoids modifying immutable ScoredPoint)
   - Terminal output: BM25 breakdown for top 5 results with score formula
   - Analytics logging: bm25_score, vector_score, keyword_boost, final_score

4. **Configuration** (`config/config_retrieval.yaml`, `code/python/core/config.py`)
   ```yaml
   bm25_params:
     enabled: true
     k1: 1.5
     b: 0.75
     alpha: 0.6    # Default vector weight
     beta: 0.4     # Default BM25 weight
   ```
   - Feature flag to enable/disable BM25
   - Fallback to old keyword boosting if disabled
   - Added `self.bm25_params` to CONFIG object

5. **Documentation** (`algo/BM25_implementation.md`)
   - Complete algorithm documentation with formulas, examples, code structure
   - Intent detection strategy with 3 query examples
   - Testing strategy, performance metrics, rollback plan
   - Changelog tracking implementation progress

**Key Implementation Decisions**:
- ✅ Custom BM25 implementation (not `rank-bm25` library) for full control
- ✅ Per-query corpus statistics (not global) to match retrieval context
- ✅ Intent detection via rule-based scoring (ML-based planned for Week 4+)
- ✅ Dictionary score storage to avoid modifying immutable Qdrant objects
- ✅ Terminal `print()` statements for debugging (logger.info only writes to files)

**Testing Results**:
- ✅ Query "Martech雙周報第77期" → BM25: 219.3, Vector: 0.52, Final: 220.1 (exact match ranked top)
- ✅ Intent detection working: Detected EXACT_MATCH intent (quotes + numbers)
- ✅ Analytics logging verified: bm25_score populated in database

---

## ✅ Track C: MMR Implementation (Week 1-2)

**Goal**: Replace LLM diversity re-ranking with MMR (Maximal Marginal Relevance) algorithm.

**Status**: ✅ COMPLETED

**What Was Built**:

1. **MMR Algorithm** (`code/python/core/mmr.py` - 274 lines)
   - Classic MMR formula: `λ * relevance - (1-λ) * max_similarity`
   - Intent-based λ tuning:
     - SPECIFIC (λ=0.8): "how to", "什麼是", "where", "when"
     - EXPLORATORY (λ=0.5): "best", "推薦", "trends", "方法", "方式"
     - BALANCED (λ=0.7): Default
   - Cosine similarity calculation for diversity measurement
   - Diversity metrics logging to `algo/mmr_metrics.log`
   - Iterative greedy selection algorithm

2. **Integration** (`code/python/core/ranking.py:485-528`)
   - Executes once after LLM ranking on 49 results → selects diverse 10
   - Removes duplicate MMR call that was in `post_ranking.py`
   - Cleans up vectors (1536 floats) to avoid console pollution
   - Logs MMR scores to analytics database

3. **Analytics Logging**
   - Per-document MMR scores → `ranking_scores.mmr_diversity_score`
   - Per-query diversity metrics → `algo/mmr_metrics.log`
   - Intent detection → tracked in `detected_intent` attribute

4. **Documentation**
   - `algo/MMR_implementation.md` - Complete algorithm documentation
   - `algo/Week4_ML_Enhancements.md` - Future ML improvements plan
   - `code/python/testing/scratchpad.md` - Testing notes and fixes

**Testing Results**:
- ✅ Query "零售業應用生成式AI的方法" → EXPLORATORY intent detected (λ=0.5)
- ✅ Diversity improvement visible: similarity 0.823 → 0.809 (with λ=0.5, expect 0.750+)
- ✅ No duplicate MMR calls
- ✅ Clean console output (vectors removed)

**Commits**:
- `f7dc48e` - Implement MMR diversity re-ranking with intent detection
- `56896b4` - Update BM25 implementation documentation and configuration
- `4fbde5d` - Update documentation and clean up obsolete files
- `a6e866a` - Backend and frontend updates for BM25 and analytics
