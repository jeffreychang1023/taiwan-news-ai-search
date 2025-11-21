# NLWeb Project Context

## Project Status: Week 1-2 (ML Search Enhancement)

### Current Focus
**Track A (Analytics) COMPLETED** ✅
Moving to Track B (BM25) and Track C (MMR) implementation.

---

## Completed Work

### ✅ Track A: Analytics Logging Infrastructure (Week 1-2)

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

---

## Recently Completed

### ✅ Track B: BM25 Implementation (Week 1-2) - COMPLETED

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

**Next Steps**:
- ⏳ A/B testing (Week 3): Compare BM25 vs old keyword boosting
- ⏳ Parameter tuning: Adjust k1, b, α, β based on user feedback
- ⏳ Intent detection validation: Test with 50 diverse queries

**Future ML Enhancement (Week 4+)**:
- **ML-based intent detection**: Replace rule-based scoring with XGBoost classifier
  - Features: query length, has_quotes, has_numbers, has_question_words, etc.
  - Labels: User engagement metrics (CTR, dwell time) by detected intent type
  - Output: Continuous α/β values instead of categorical (0.4/0.6, 0.7/0.3, default)
- **XGBoost for α/β optimization**: Learn optimal vector/BM25 balance from user behavior
  - Current: Fixed α/β per intent type (EXACT_MATCH, SEMANTIC, BALANCED)
  - Future: Predict optimal α/β for each query based on features
  - Example features: query length, term diversity, embedding entropy, user history
  - Training data: Logged in analytics database

**Future Schema Considerations (NOT implementing now, just documenting for Week 4+)**:
- When implementing XGBoost intent classifier, may need to add to `queries` table:
  - `detected_intent VARCHAR(20)` - Intent type (EXACT_MATCH, SEMANTIC, BALANCED)
  - `alpha_used FLOAT` - Vector score weight used for this query
  - `beta_used FLOAT` - BM25 score weight used for this query
  - `intent_exact_score INT` - Rule-based exact match score
  - `intent_semantic_score INT` - Rule-based semantic score
- Purpose: Enable A/B testing, training data collection, correlation analysis
- Decision will be made in Week 4 based on actual needs

---

## In Progress



### 🔄 Track C: MMR Implementation (Week 1-2)

**Goal**: Replace LLM diversity re-ranking with MMR (Maximal Marginal Relevance) algorithm.

**Status**: Planning phase

**Implementation Plan**:
1. Create `code/python/core/mmr.py` - MMR algorithm implementation
2. Modify `code/python/core/post_ranking.py` - replace `apply_diversity_reranking()` LLM call
3. Update analytics logging to record `mmr_diversity_score` in `ranking_scores` table
4. Implement intent-based λ tuning (exploratory vs specific queries)
5. Apply in both list and generate modes

**Database Ready**:
- ✅ `ranking_scores.mmr_diversity_score` column already exists (currently NULL)
- ✅ Schema supports diversity tracking

---

## Next Immediate Steps

1. ✅ **COMPLETED: Implement BM25** (`code/python/core/bm25.py`)
   - ✅ Custom implementation with full control
   - ✅ Integrated into `qdrant.py` retrieval flow with intent detection
   - ✅ Logging `bm25_score` to database

2. **Implement MMR** (`code/python/core/mmr.py`)
   - Classic MMR formula implementation
   - Integrate into `post_ranking.py`
   - Log `mmr_diversity_score` to database

3. **Test BM25 with Diverse Queries**
   - Collect 50 diverse query types
   - Verify intent detection accuracy (EXACT_MATCH, SEMANTIC, BALANCED)
   - Validate BM25 scores improve keyword matching
   - Check analytics logging captures new scores

4. **Deploy BM25 + MMR to Production**
   - Week 3: Full BM25 + MMR integration
   - Slim down LLM prompts (remove keyword/freshness scoring)
   - A/B testing and validation
   - Expected: 40% cost reduction, 40% latency reduction

---

## Known Issues & Workarounds

### ✅ RESOLVED: Foreign Key Constraint Violations

**Root Causes & Fixes**:

1. **Async Queue Race Condition** (commit 743871e):
   - Problem: `log_query_start()` used async queue, child tables wrote before parent
   - Fix: Made `log_query_start()` synchronous - calls `_write_to_db()` directly

2. **Cache Early Return** (commit fc44ded):
   - Problem: GenerateAnswer using cached results returned before analytics logging
   - Fix: Moved analytics logging to START of `get_ranked_answers()`, before cache check

3. **Missing parent_query_id Column**:
   - Problem: Neon PostgreSQL missing `parent_query_id` column after schema migration
   - Fix: Manual `ALTER TABLE queries ADD COLUMN parent_query_id VARCHAR(255);`

4. **Query ID Format Inconsistency**:
   - Problem: UUID suffix caused tracking issues
   - Fix: Changed from `query_{timestamp}_{uuid}` to `query_{timestamp}`

5. **Multi-Click Tracking Missing** (commit 122c697):
   - Problem: Only left-click tracked, user interactions incomplete
   - Fix: Added `auxclick` and `contextmenu` event listeners

6. **Batch Handler Missing Click Events** (commit 0e913c9):
   - Problem: Backend ignored `result_clicked` events in batch processing
   - Fix: Added `result_clicked` case to `handle_analytics_batch()`

**Status**: ✅ All issues resolved, deployed to production

### Issue: Render Free Plan Auto-Sleep
**Symptom**: First request after 15 minutes returns 503, takes 30-60s to wake up
**Status**: Expected behavior (Render Free plan)
**Workaround**: Users must wait for service to wake up

---

## References

- Analytics Dashboard: https://taiwan-news-ai-search.onrender.com/analytics
- Neon Database: https://console.neon.tech
- Render Service: https://dashboard.render.com
- Implementation Plan: See `~/.claude/CLAUDE.md` "Machine Learning & Search Enhancement Project"
