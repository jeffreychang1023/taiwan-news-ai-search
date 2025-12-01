# Next Steps - ML Search Enhancement

## Immediate Tasks (Week 3-4)

### 🔄 IN PROGRESS: Phase A - XGBoost Infrastructure

**Goal**: Build complete ML ranking infrastructure before data collection

**Status**: Configuration complete (2025-01-26), now implementing modules

**Completed**:
- ✅ Documentation (`algo/XGBoost_implementation.md`)
- ✅ Configuration (`config/config_retrieval.yaml`, `core/config.py`)
- ✅ ML dependencies (`requirements.txt`)
- ✅ Architecture finalization (LLM → XGBoost → MMR)

**In Progress** (Week 1 Remaining):

1. **Feature Engineering Module** (`code/python/training/feature_engineering.py`)
   - Extract 29 features from analytics database
   - Populate feature_vectors table in batches
   - Query-level, document-level, and ranking features
   - Handle missing values and edge cases

2. **XGBoost Ranker Module** (`code/python/core/xgboost_ranker.py`)
   - Load trained models with global caching
   - Extract features from in-memory ranking results
   - Run inference (<100ms target)
   - Calculate confidence scores
   - Shadow mode support

3. **Training Pipeline** (`code/python/training/xgboost_trainer.py`)
   - Binary classification trainer (Phase 1)
   - LambdaMART trainer (Phase 2)
   - XGBRanker trainer (Phase 3)
   - Model evaluation (NDCG@10, Precision@10, MAP)
   - Model saving with metadata

**Week 2 Tasks**:

4. **Integration** (`code/python/core/ranking.py`)
   - Insert XGBoost call after LLM ranking, before MMR
   - Handle enabled/disabled gracefully
   - Log metadata for analytics

5. **Unit Tests** (`code/python/testing/test_xgboost.py`)
   - Feature extraction tests
   - Model loading tests
   - Inference pipeline tests
   - Shadow mode validation

6. **Mock Data** (`code/python/testing/mock_training_data.py`)
   - Generate synthetic features (29 features)
   - Generate labels (binary, regression)
   - Create tiny XGBoost model for testing

---

## Previously Completed

### ✅ COMPLETED: Track A - Analytics Infrastructure
All components deployed and operational:
- PostgreSQL database via Neon.tech
- Query logging with parent_query_id linking
- Multi-click tracking (left/middle/right)
- Dashboard with parent query filtering
- Foreign key integrity issues resolved

---

### ✅ COMPLETED: Track B - BM25 Implementation

**Goal**: Replace LLM keyword scoring with BM25 algorithm

**Steps**:
1. **Research & Library Selection**
   - Evaluate `rank-bm25` Python library
   - Or implement custom BM25 from scratch
   - Consider Qdrant's built-in BM25 capabilities

2. **Implementation** (`code/python/core/bm25.py`)
   - BM25 scoring function
   - Document frequency calculation
   - Inverse document frequency (IDF) weights
   - Configurable parameters (k1, b)

3. **Integration** (`code/python/retrieval_providers/qdrant.py`)
   - Call BM25 scorer after vector retrieval
   - Combine scores: `final_score = α * vector_score + β * bm25_score`
   - Make α, β configurable per site

4. **Analytics Logging**
   - Record `bm25_score` in `retrieved_documents` table
   - Track BM25 contribution to final ranking

5. **Testing**
   - Unit tests for BM25 scorer
   - Verify scores make sense for sample queries
   - Compare against LLM keyword scores

---

### 🔄 IN PROGRESS: Track C - MMR Implementation

**Goal**: Replace LLM diversity re-ranking with MMR algorithm

**Steps**:
1. **Implementation** (`code/python/core/mmr.py`)
   - Classic MMR formula: `λ * relevance - (1-λ) * max_similarity`
   - Document similarity calculation (cosine similarity of embeddings)
   - Intent-based λ tuning (exploratory vs specific queries)

2. **Integration** (`code/python/core/post_ranking.py`)
   - Replace `apply_diversity_reranking()` LLM call
   - Apply MMR to top-N results (e.g., top 50)
   - Keep diversity threshold configurable

3. **Analytics Logging**
   - Record `mmr_diversity_score` in `ranking_scores` table
   - Track diversity improvement metrics

4. **Testing**
   - Verify diversity improves (fewer duplicate topics)
   - Compare against LLM diversity re-ranking
   - A/B test with real users

---

## Week 3: Integration & LLM Optimization

**Goals**:
- Deploy BM25 + MMR to production
- Slim down LLM prompts (remove keyword/freshness scoring)
- Target: 40% cost reduction, 40% latency reduction

**Tasks**:
1. **Update LLM Prompts** (`config/prompts.xml`)
   - Remove keyword scoring dimension (now BM25)
   - Remove freshness scoring dimension (now algorithmic)
   - Keep only semantic relevance scoring

2. **Score Combination** (`code/python/core/ranking.py`)
   - Combine BM25, vector, and LLM scores
   - Configurable weights per site

3. **Gradual Rollout**
   - Deploy to 10% of traffic first
   - Monitor latency, cost, and quality metrics
   - Scale to 100% if successful

4. **A/B Testing**
   - Compare against baseline (current LLM-only)
   - Measure CTR, dwell time, user satisfaction
   - Track cost and latency improvements

---

## Week 4-6: Data Collection & XGBoost Training

**Goals**:
- Collect 10,000+ queries with user interactions
- Feature engineering for ML ranking
- Train initial XGBoost model

**Prerequisites**:
- ✅ Analytics system collecting data
- ✅ Schema v2 with ML feature columns
- 🔄 BM25 and MMR deployed (provides more features)

**Tasks**:
1. **Monitor Data Collection**
   - Verify 100+ queries/day being logged
   - Check user interaction data quality
   - Export training data periodically

2. **Feature Engineering** (`code/python/ml/feature_engineering.py`)
   - Extract 12-15 features per query-doc pair
   - Implement feature calculation functions
   - Handle missing values and edge cases

3. **Prepare Training Data** (`code/python/ml/prepare_training_data.py`)
   - Create train/val/test splits (70/15/15)
   - Balance positive/negative examples
   - Generate feature vectors table

4. **Train XGBoost Model** (`code/python/ml/train_ranker.py`)
   - Hyperparameter tuning (max_depth, learning_rate, etc.)
   - Cross-validation
   - Model evaluation (NDCG, MAP)

5. **Model Registry** (`code/python/ml/model_registry.py`)
   - Version tracking
   - Model metadata storage
   - Rollback capabilities

---

## Week 7-8: XGBoost Deployment

**Goals**:
- Shadow mode validation
- Gradual traffic migration (10% → 50% → 100%)
- Cascading architecture: XGBoost → LLM (top-10 only)
- Target: 88% total cost reduction, 75% latency reduction

**Tasks**:
1. **XGBoost Inference** (`code/python/core/xgboost_ranker.py`)
   - Load trained model
   - Feature extraction in real-time
   - Fast inference (<100ms)

2. **Cascading Logic**
   - High confidence (>0.85): Skip LLM entirely
   - Medium (0.7-0.85): LLM refines top-10 only
   - Low (<0.7): LLM processes all results

3. **Shadow Mode Testing**
   - Run XGBoost in parallel with LLM
   - Compare rankings but don't show to users
   - Validate accuracy before switching

4. **Gradual Rollout**
   - 10% → 50% → 100% traffic migration
   - Monitor quality metrics closely
   - Rollback procedure ready

---

## Future Improvements

1. **Model Retraining Pipeline**
   - Automated weekly/monthly retraining
   - Incorporate latest user interaction data
   - Continuous learning loop

2. **Advanced Features**
   - User personalization features
   - Session context features
   - Time-of-day patterns

3. **Multi-Objective Optimization**
   - Balance relevance, diversity, and freshness
   - Incorporate business metrics (engagement, revenue)

4. **Online Learning**
   - Update model incrementally with new data
   - Faster adaptation to changing patterns
