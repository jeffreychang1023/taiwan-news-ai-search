# Week 4+ Machine Learning Enhancements

## Overview

This document outlines planned ML improvements to replace rule-based algorithms with learned models. These enhancements build on the Week 1-2 foundation (BM25 + MMR + Analytics).

---

## 1. ML-Based Lambda (λ) Tuning for MMR

### Current State (Week 1-2)

**Rule-Based Intent Detection** in `core/mmr.py`:
- **SPECIFIC** (λ=0.8): Keyword matching ("how to", "什麼是", "where", "when")
- **EXPLORATORY** (λ=0.5): Keyword matching ("best", "推薦", "trends", "ideas")
- **BALANCED** (λ=0.7): Default fallback

**Limitations**:
- Simple keyword matching - no context understanding
- Fixed categorical values (only 3 options: 0.5, 0.7, 0.8)
- No learning from user behavior
- Cannot handle novel query patterns

### Week 4+ Enhancement: XGBoost Lambda Classifier

**Goal**: Replace keyword matching with ML model that predicts optimal λ based on query characteristics and user behavior.

#### Input Features (12-15 features)

**Query Text Features**:
1. `query_length` (INT) - Number of characters
2. `word_count` (INT) - Number of words/tokens
3. `has_quotes` (BOOL) - Contains quotation marks
4. `has_numbers` (BOOL) - Contains numeric values
5. `has_question_words` (BOOL) - Contains "how", "what", "why", etc.
6. `keyword_count` (INT) - Number of keywords extracted

**Embedding Features**:
7. `embedding_entropy` (FLOAT) - Semantic specificity measure
   - High entropy = broad/ambiguous query → Lower λ (more diversity)
   - Low entropy = specific query → Higher λ (more relevance)
8. `vector_norm` (FLOAT) - L2 norm of query embedding

**User History Features** (if available):
9. `user_past_click_rate` (FLOAT) - Historical CTR for this user
10. `user_avg_dwell_time` (FLOAT) - Average time spent on results
11. `query_frequency` (INT) - How often this user searches

**Temporal Features**:
12. `time_of_day` (INT) - Hour 0-23
13. `day_of_week` (INT) - 0=Monday, 6=Sunday
14. `is_trending_topic` (BOOL) - Query matches trending topics

**Current Intent Features** (from rule-based):
15. `specific_indicator_count` (INT) - Number of SPECIFIC keywords found
16. `exploratory_indicator_count` (INT) - Number of EXPLORATORY keywords found

#### Training Labels

**Label**: `optimal_lambda` (FLOAT, 0.0-1.0)

**How to Determine Optimal λ**:

For each logged query in analytics database:
1. Check user engagement metrics:
   - `clicked` (from `user_interactions` table)
   - `dwell_time_ms` (from `user_interactions` table)
   - `result_position` (from `user_interactions` table)

2. Calculate engagement score:
   ```python
   engagement_score = (
       0.4 * click_rate +
       0.3 * normalized_dwell_time +
       0.2 * diversity_of_clicks +  # Did user click diverse results?
       0.1 * (1 - avg_click_position / 10)  # Clicked higher results = better
   )
   ```

3. Group queries by similar features (clustering)

4. For each cluster, find λ that correlates with highest engagement:
   ```
   If high engagement when λ=0.8 → Label: 0.8 (user wanted relevance)
   If high engagement when λ=0.5 → Label: 0.5 (user wanted diversity)
   ```

#### Model Architecture

**Algorithm**: XGBoost Regressor (not classifier, since λ is continuous)

**Hyperparameters**:
- `max_depth`: 5-7 (prevent overfitting)
- `learning_rate`: 0.05-0.1
- `n_estimators`: 100-200
- `objective`: 'reg:squarederror'

**Training Data**:
- Source: `queries` + `user_interactions` + `ranking_scores` tables
- Minimum: 10,000 queries with user interactions
- Split: 80% train, 20% test

**Validation**:
- Metric: Mean Absolute Error (MAE) between predicted λ and optimal λ
- Target: MAE < 0.1 (within ±10% of optimal)

#### Deployment Strategy

**Phase 1: Shadow Mode** (Week 4-5)
- Run XGBoost model in parallel with rule-based
- Log both predictions: `lambda_rule_based`, `lambda_ml`
- Compare engagement metrics
- Do NOT use ML predictions for actual ranking yet

**Phase 2: A/B Testing** (Week 6)
- 50% traffic: Use XGBoost λ
- 50% traffic: Use rule-based λ
- Compare metrics:
  - Click-through rate (CTR)
  - Average dwell time
  - Diversity score (avg similarity between clicked results)

**Phase 3: Gradual Rollout** (Week 7)
- If ML outperforms rule-based:
  - 10% → 25% → 50% → 100% traffic
- Monitor for regressions

**Rollback Plan**:
- Config flag: `mmr_params.use_ml_lambda: false`
- Instantly reverts to rule-based intent detection

#### Expected Impact

| Metric | Rule-Based | ML-Based | Improvement |
|--------|------------|----------|-------------|
| CTR | Baseline | +8-12% | Better intent matching |
| Avg Dwell Time | Baseline | +10-15% | More relevant results |
| Diversity Score | Baseline | Same | Maintains diversity |
| Lambda Accuracy | ~70% | ~85% | More precise tuning |

---

## 2. XGBoost Ranking Model (Week 5-8)

### Goal

Replace LLM-based ranking with XGBoost model that predicts document relevance scores.

### Architecture

**UPDATED** (2025-01-26): Corrected pipeline order based on Phase A implementation.

**Cascading Model** (cost optimization):
```
Retrieval (BM25 + Vector)
    ↓
LLM Ranking (50 results → scored)
    ↓
XGBoost Re-ranking (uses LLM scores as features)
    ↓
MMR Diversity Re-ranking (50 results → 10 results)
    ↓
Final Results
```

**Key Design Decision**: XGBoost runs AFTER LLM ranking because:
- XGBoost uses LLM scores as input features (features 22-27 in feature list)
- MMR should work on final relevance ranking from XGBoost
- Allows graceful degradation if XGBoost disabled

**Note**: This differs from the original Week 4 plan which suggested XGBoost before MMR without LLM. Phase A implementation (see `algo/XGBoost_implementation.md`) uses a hybrid approach where XGBoost enhances LLM ranking rather than replacing it entirely.

### Input Features (25-30 features)

**Retrieval Features**:
1. `vector_similarity_score` - Cosine similarity
2. `bm25_score` - Keyword relevance
3. `keyword_overlap_ratio` - Query-doc overlap
4. `title_exact_match` - Boolean
5. `description_exact_match` - Boolean
6. `final_retrieval_score` - Combined score

**Document Quality**:
7. `doc_length` - Word count
8. `recency_days` - Days since publication
9. `has_author` - Boolean
10. `has_publication_date` - Boolean
11. `schema_completeness` - % of schema fields populated

**Ranking Context**:
12. `retrieval_position` - 0-indexed position
13. `relative_score_to_top` - Normalized score
14. `score_percentile` - Ranking in result set

**MMR Features**:
15. `mmr_diversity_score` - Diversity score from MMR

**Historical Features** (if URL seen before):
16. `historical_ctr` - Past CTR for this URL
17. `historical_avg_dwell_time` - Past engagement
18. `times_shown` - How often this URL was returned

### Training Labels

**Label**: `relevance_grade` (INT, 0-4)

**Grading System**:
- **4 (Excellent)**: Clicked + dwell time > 30s
- **3 (Good)**: Clicked + dwell time 10-30s
- **2 (Fair)**: Clicked + dwell time < 10s (bounce)
- **1 (Poor)**: Shown but not clicked (position 1-5)
- **0 (Irrelevant)**: Shown but not clicked (position 6-10)

**Data Collection**:
- Minimum: 50,000 query-document pairs with interactions
- Balanced sampling (avoid over-representing high-ranking docs)

### Model Outputs

**Primary Output**: `xgboost_score` (FLOAT, 0-1)

**Secondary Output**: `xgboost_confidence` (FLOAT, 0-1)
- Based on tree agreement / variance
- High confidence (>0.8) → Skip LLM
- Low confidence (<0.8) → Use LLM refinement

### Expected Impact

**Cost Reduction**:
- Before: 50 LLM calls per query (ranking all results)
- After: 0-10 LLM calls per query (only low-confidence results)
- **Savings**: 80-100% of ranking cost

**Latency Reduction**:
- Before: 10-15s LLM ranking
- After: 0.5-1s XGBoost + 2-3s LLM (top-10 only)
- **Savings**: 70-80% latency

**Accuracy**:
- Target: ±5% of LLM ranking quality
- Measured by: CTR, dwell time, user satisfaction

---

## 3. Intent Detection for BM25 Alpha/Beta (Week 6+)

### Current State

**Rule-Based** in `retrieval_providers/qdrant.py`:
- **EXACT_MATCH** (α=0.4, β=0.6): Quotes, numbers, hashtags
- **SEMANTIC** (α=0.7, β=0.3): Question words, concept words
- **BALANCED** (default α/β): Mixed intent

### Enhancement: ML-Based Alpha/Beta Prediction

**Model**: XGBoost Classifier (3 classes: EXACT_MATCH, SEMANTIC, BALANCED)

**Input Features**:
- Query text features (same as MMR lambda model)
- Embedding features
- BM25 score distribution (std dev, range)

**Training Labels**:
- Analyze which intent type led to better engagement
- Use clicked results' scores to infer optimal α/β

**Output**:
- Predicted intent class → Corresponding α/β values
- OR: Direct regression to predict α and β separately

---

## Implementation Timeline

### Week 4-5: Data Collection & Feature Engineering
- ✅ Analytics infrastructure already in place
- Collect 10,000+ queries with user interactions
- Build feature extraction pipeline
- Create training dataset (features + labels)

### Week 6: ML Lambda Model
- Train XGBoost lambda predictor
- Shadow mode deployment
- Validate predictions vs rule-based

### Week 7: ML Lambda A/B Testing
- 50/50 traffic split
- Compare engagement metrics
- Tune hyperparameters

### Week 8: XGBoost Ranking Model (Training)
- Collect 50,000+ query-document pairs
- Train ranking model
- Implement cascading architecture

### Week 9: XGBoost Ranking Deployment
- Shadow mode validation
- Gradual rollout (10% → 100%)
- Monitor cost/latency improvements

---

## Database Schema Extensions

### New Columns in `queries` Table (Optional)

For tracking ML predictions:
```sql
ALTER TABLE queries ADD COLUMN lambda_ml_predicted DOUBLE PRECISION;
ALTER TABLE queries ADD COLUMN lambda_rule_based DOUBLE PRECISION;
ALTER TABLE queries ADD COLUMN intent_ml_predicted VARCHAR(20);
ALTER TABLE queries ADD COLUMN intent_rule_based VARCHAR(20);
```

### New Table: `ml_model_versions` (Recommended)

Track model deployments:
```sql
CREATE TABLE ml_model_versions (
    model_id SERIAL PRIMARY KEY,
    model_name VARCHAR(50),  -- 'lambda_predictor', 'xgboost_ranker'
    version VARCHAR(20),      -- 'v1.0', 'v1.1'
    deployed_at TIMESTAMP,
    hyperparameters JSONB,
    training_metrics JSONB,   -- MAE, RMSE, etc.
    active BOOLEAN DEFAULT FALSE
);
```

---

## Monitoring & Evaluation

### Key Metrics to Track

**Engagement Metrics**:
- Click-through rate (CTR)
- Average dwell time
- Scroll depth
- Multi-click rate (diversity indicator)

**Model Performance**:
- Prediction accuracy (MAE for lambda, F1 for intent)
- Inference latency (should be <100ms)
- Model drift detection (monthly retraining)

**Cost & Latency**:
- Cost per query
- Time-to-first-result (TTFR)
- Total query latency

### A/B Testing Framework

**Metrics Dashboard**:
- Real-time comparison: ML vs Rule-based
- Statistical significance testing (p-value < 0.05)
- User segmentation (new vs returning users)

**Decision Criteria**:
- ML must outperform rule-based by ≥5% on CTR
- OR equal CTR + ≥10% cost reduction
- No degradation in dwell time

---

## Risk Mitigation

### Data Quality Risks

**Risk**: Biased training data (only clicked results labeled)
**Mitigation**:
- Use negative sampling (non-clicked results)
- Collect explicit feedback (thumbs up/down)
- Manual labeling for 1,000 query-doc pairs

### Model Drift

**Risk**: User behavior changes over time, model becomes stale
**Mitigation**:
- Monthly retraining schedule
- Monitor prediction confidence distribution
- Shadow mode for new models before deployment

### Overfitting

**Risk**: Model memorizes training data, poor generalization
**Mitigation**:
- Cross-validation during training
- Regularization (L1/L2)
- Early stopping based on validation loss

---

## Success Criteria

### Week 8 Targets (After Full ML Deployment)

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Cost Reduction** | 88% from baseline | Cost per query: $1.20 → $0.15 |
| **Latency Reduction** | 75% from baseline | Total time: 20s → 5s |
| **Accuracy** | ±5% of LLM baseline | CTR, dwell time comparison |
| **Model Inference** | <100ms per query | P95 latency |
| **User Satisfaction** | No degradation | Survey, bounce rate |

---

## References

- **Current Implementation**: `algo/BM25_implementation.md`, `algo/MMR_implementation.md`
- **Analytics Schema**: `.claude/CLAUDE.md` (Analytics Database Schema section)
- **XGBoost Docs**: https://xgboost.readthedocs.io/
- **Feature Engineering**: `code/python/core/query_logger.py` (feature_vectors table)
