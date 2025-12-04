# Phase B: Data Collection Status Report
**Date**: 2025-12-03
**Database**: `data/analytics/query_logs.db`

---

## Executive Summary

**STATUS**: ⚠️ **DATA COLLECTION IN PROGRESS - NOT READY FOR TRAINING**

- **Total queries logged**: 137 (88 parent, 49 child)
- **XGBoost shadow predictions**: 5,603 records across 76 queries
- **User click events**: 8 total, but **0 valid training examples**
- **Feature completeness**: 100% (all XGBoost queries have complete features)
- **Training readiness**: **BLOCKED** - Need user clicks on summarize mode results

---

## 1. Data Collection Overview

### Queries by Type
| Type | Count | Has XGBoost Data | Description |
|------|-------|------------------|-------------|
| Summarize (parent) | 88 | 76 (86%) | Main search results - **training candidates** |
| Generate (child) | 49 | 0 (0%) | Answer generation - not used for training |

### Shadow Mode Performance
- **XGBoost shadow predictions**: 5,603 out of 5,913 ranking records (94.8%)
- **Queries with complete XGBoost data**: 76 parent queries
- **Feature coverage**: 100% (vector similarity, LLM scores, BM25, MMR all present)

---

## 2. Critical Issue: No Valid Training Labels

### Problem Statement
**Zero valid training examples** despite 8 click events. Why?

### Root Cause Analysis

#### Issue 1: Click Events from Deleted Queries
- **7 out of 8 clicks** are from old queries that no longer exist in the database
- These query_ids are NOT in the `queries` table (likely deleted or from pre-Phase A)
- Cannot be used for training (no feature data available)

```
OLD CLICKS (NOT USABLE):
  query_1762492527667_82qji8nmh (2 clicks) - DELETED
  query_1762773469946_bem3886x4 (1 click)  - DELETED
  query_1762841662561_mcj7rkz5w (3 clicks) - DELETED
  query_1762844818863_vdapfcb80 (1 click)  - DELETED
```

#### Issue 2: Click on Generate Mode Query
- **1 out of 8 clicks** is from a valid query BUT it's in **generate mode**
- Generate mode queries do NOT create `retrieved_documents` or `ranking_scores`
- Cannot be used for training (no ranking features)

```
GENERATE MODE CLICK (NOT USABLE):
  query_1764341061721 (1 click) - mode=generate, no ranking data
```

### Impact
**Training Examples Available**:
- Positive examples (clicks): **0**
- Negative examples (shown but not clicked): **0**
- **Total training examples**: **0**

---

## 3. Data Quality Assessment

### ✅ What's Working Well

1. **Feature Extraction (100% complete)**
   - Vector similarity scores: 6,010/6,010 (100%)
   - LLM ranking scores: 5,913/5,913 (100%)
   - XGBoost shadow predictions: 5,603/5,913 (94.8%)
   - MMR diversity scores: 5,913/5,913 (100%)

2. **XGBoost Shadow Mode**
   - Successfully deployed since 2025-11-07
   - Running on 76 summarize mode queries
   - Generating predictions with confidence scores
   - No errors or missing features

3. **Database Schema**
   - All 4 core tables operational
   - Foreign key integrity working
   - No schema-related errors

### ⚠️ What's Blocking Training

1. **No User Clicks on Summarize Mode Results**
   - 76 summarize queries with XGBoost data
   - **0 clicks** on any of these results
   - Users may be clicking in generate mode only (after answer is shown)

2. **Click Tracking May Be Incomplete**
   - Only 8 total clicks across 137 queries (5.8% click rate)
   - Expected: 10-30% click-through rate for search results
   - Possible issues:
     - Click tracker not attached to summarize mode results?
     - Users viewing results but not clicking through?
     - Frontend tracking issue?

---

## 4. Training Readiness Assessment

### Phase C Requirements vs Current Status

| Phase | Requirement | Current Status | Gap |
|-------|-------------|----------------|-----|
| **Phase C1** | 500-2,000 clicks | **0 clicks** | Need 500+ |
| Binary Classification | Basic relevance | No data | BLOCKED |
|  |  |  |  |
| **Phase C2** | 2,000-5,000 clicks | **0 clicks** | Need 2,000+ |
| LambdaMART | Pairwise ranking | No data | BLOCKED |
|  |  |  |  |
| **Phase C3** | 5,000-10,000 clicks | **0 clicks** | Need 5,000+ |
| XGBRanker | Listwise ranking | No data | BLOCKED |

### Time to Training (Estimates)

Assuming 10% click-through rate on summarize mode queries:

| Target | Clicks Needed | Queries Needed | Days @ 10 queries/day | Days @ 50 queries/day |
|--------|---------------|----------------|----------------------|----------------------|
| Phase C1 Start | 500 | 5,000 | 500 days | 100 days |
| Phase C2 Start | 2,000 | 20,000 | 2,000 days | 400 days |
| Phase C3 Start | 5,000 | 50,000 | 5,000 days | 1,000 days |

**⚠️ WARNING**: At current volume, Phase C1 would take **100+ days** even with 50 queries/day.

### Realistic Assessment

With improved click tracking (30% CTR assumed):

| Target | Clicks Needed | Queries Needed | Days @ 50 queries/day |
|--------|---------------|----------------|----------------------|
| Phase C1 Start | 500 | 1,667 | **33 days** |
| Phase C2 Start | 2,000 | 6,667 | **133 days** |
| Phase C3 Start | 5,000 | 16,667 | **333 days** |

---

## 5. Feature Extraction Implementation Review

### Current Features (29 total)

Based on `core/xgboost_ranker.py:extract_features()`:

#### Retrieval Features (6)
1. `vector_similarity_score` - Embedding-based relevance
2. `keyword_boost_score` - Keyword match bonus
3. `bm25_score` - BM25 keyword relevance (NEW in Phase A)
4. `final_retrieval_score` - Combined retrieval score
5. `retrieval_position` - Original ranking position (0-based)
6. `keyword_overlap_ratio` - Query-doc keyword overlap

#### LLM Ranking Features (8)
7. `llm_relevance_score` - Semantic relevance
8. `llm_keyword_score` - Keyword match (LLM-scored)
9. `llm_semantic_score` - Semantic match
10. `llm_freshness_score` - Recency score
11. `llm_authority_score` - Source authority
12. `llm_final_score` - Combined LLM score
13. `relative_score` - Score relative to top result
14. `score_percentile` - Ranking percentile

#### Document Features (7)
15. `doc_length` - Document word count
16. `recency_days` - Days since publication
17. `has_author` - Boolean: author present
18. `has_publication_date` - Boolean: date present
19. `schema_completeness` - Metadata quality (0-1)
20. `title_exact_match` - Boolean: query in title
21. `desc_exact_match` - Boolean: query in description

#### Query Features (3)
22. `query_length` - Query word count
23. `query_type` - Question vs keyword (boolean)
24. `temporal_indicator` - Query has time words (boolean)

#### Diversity Features (2)
25. `mmr_diversity_score` - MMR re-ranking score
26. `diversity_penalty` - Similarity to already-selected docs

#### Position Features (3)
27. `ranking_position` - Final position after LLM ranking
28. `position_change` - Movement from retrieval to ranking
29. `xgboost_confidence` - Model confidence score

### Feature Status: ✅ ALL IMPLEMENTED

All 29 features are being extracted and stored in the database for 5,603 query-document pairs.

---

## 6. Immediate Action Items

### Priority 1: Fix Click Tracking

**Problem**: Users are not clicking on summarize mode results (or clicks not being tracked).

**Investigation needed**:
1. Verify click tracking is attached to summarize mode results
   - Check: `static/news-search-prototype.html` event listeners
   - Confirm: Analytics tracker initializes before results display
2. Test click tracking manually:
   - Submit query in summarize mode
   - Click on a result
   - Verify click appears in `user_interactions` table with correct `query_id`
3. Check if users are clicking in generate mode only:
   - Review user flow: Do users wait for summarize results or skip to generate?
   - Add dwell time tracking to understand engagement

**Expected outcome**: 10-30% click-through rate on summarize mode results.

### Priority 2: Accelerate Data Collection

**Options to increase training data velocity**:

1. **Increase query volume**:
   - Run automated test queries (with manual quality checks)
   - Share search tool with beta users
   - Create sample query templates for testing

2. **Reduce training requirements** (Alternative approach):
   - Start with Binary Classification using implicit signals:
     - Position clicked (higher = more relevant)
     - Dwell time (longer = more relevant)
     - Results shown but not clicked = negative labels
   - Train with as few as **50-100 queries** with position/dwell data

3. **Synthetic labels** (Phase C1 only):
   - Use LLM scores as pseudo-labels for initial model
   - Train XGBoost to predict LLM scores (regression)
   - Fine-tune later with real user clicks

### Priority 3: Prepare Training Infrastructure

Even without training data, prepare the pipeline:

1. **Update `training/feature_engineering.py`**:
   - Add function to export training data from database
   - Join `ranking_scores` + `user_interactions` + `retrieved_documents`
   - Create feature matrix (29 features per query-doc pair)
   - Generate labels (clicked=1, not clicked=0)

2. **Create `training/xgboost_trainer.py`**:
   - Binary classification model (Phase C1)
   - LambdaMART pairwise ranking (Phase C2 - future)
   - XGBRanker listwise ranking (Phase C3 - future)
   - Model evaluation metrics (AUC, NDCG, MRR)
   - Cross-validation with query-level splits

3. **Create mock training data**:
   - Generate synthetic training examples
   - Use for pipeline testing and validation
   - Ensure training code works before real data arrives

---

## 7. Revised Timeline

### Original Plan (Week 3-7)
- Week 5-7: Collect 500-10,000+ queries → **BLOCKED**

### Revised Plan

#### Option A: Wait for Real Data (Conservative)
- **Weeks 5-17** (3 months): Collect 500+ clicks at current volume
- **Week 18**: Train Phase C1 Binary Classifier
- **Months 6-12**: Continue collection for Phase C2/C3

#### Option B: Synthetic Labels + Real Data (Recommended)
- **Week 5** (NOW): Train Phase C1 with synthetic labels (LLM scores as pseudo-labels)
  - Use existing 5,603 query-doc pairs
  - Train XGBoost to predict LLM scores (regression task)
  - Deploy model in shadow mode (validate predictions)
- **Weeks 6-10**: Collect 100-500 queries with position/dwell signals
  - Re-train with implicit feedback (position clicked, dwell time)
  - Deploy model with confidence-based fallback
- **Weeks 11-20**: Collect 500-2,000 explicit clicks
  - Fine-tune model with real click data (Phase C1 complete)
- **Months 6-12**: Progress to Phase C2/C3

#### Option C: Alternative Signals (Hybrid)
- **Week 5**: Implement extended engagement tracking:
  - Dwell time on results page
  - Scroll depth (which results viewed)
  - Time to generate request (did they review results?)
- **Weeks 6-10**: Collect 100+ queries with rich engagement data
- **Week 11**: Train with implicit relevance signals:
  - High dwell time + scroll to result = positive
  - Shown but not viewed = negative
  - View but quick exit = weak negative

---

## 8. Recommendations

### Immediate (This Week)

1. **Investigate click tracking** for summarize mode results
   - Test manually: Submit query → Click result → Verify database entry
   - Fix any frontend tracking issues
   - Ensure `query_id` synchronization is working

2. **Add engagement tracking** beyond clicks:
   - Dwell time per result
   - Scroll depth tracking
   - Time spent reviewing results before generate request

3. **Prepare training pipeline** with mock data:
   - `training/feature_engineering.py` - Feature export function
   - `training/xgboost_trainer.py` - Binary classifier with synthetic labels
   - `testing/mock_training_data.py` - Generate test dataset

### Short-term (Weeks 5-6)

4. **Deploy synthetic label training** (Option B):
   - Train XGBoost to predict LLM scores (regression)
   - Use existing 5,603 examples (no user data needed)
   - Validate in shadow mode
   - Compare XGBoost predictions vs LLM scores

5. **Accelerate data collection**:
   - Increase query volume (beta users, automated tests)
   - Focus on high-quality, diverse queries
   - Monitor click tracking health

### Medium-term (Weeks 7-12)

6. **Transition to real user feedback**:
   - Re-train with position clicks (implicit feedback)
   - Add dwell time as a signal
   - Fine-tune with explicit clicks as they arrive

7. **Deploy Phase C1 model** with confidence-based fallback:
   - High confidence → Use XGBoost
   - Low confidence → Use LLM ranking
   - Monitor performance metrics (NDCG, MRR, click-through rate)

---

## 9. Technical Debt & Cleanup

### Database Issues
- **7 orphaned click events**: user_interactions references deleted queries
- **Solution**: Add CASCADE DELETE or periodic cleanup job

### Analytics Dashboard
- Currently shows 88 parent queries but 0 with clicks
- Add filter to show "Training-ready queries" (XGBoost + summarize mode)

### Monitoring
- Add alerting for:
  - Click-through rate drops below 5%
  - XGBoost shadow mode failures
  - Feature extraction errors

---

## 10. Conclusion

### Current State: ✅ Infrastructure Complete, ⚠️ No Training Data

**Accomplishments**:
- XGBoost shadow mode deployed and running successfully
- Feature extraction (29 features) working perfectly
- 5,603 query-document pairs with complete feature data
- Database schema and analytics pipeline operational

**Blockers**:
- **Zero valid training labels** (no clicks on summarize mode results)
- Click tracking may have issues or user behavior different than expected
- Timeline to Phase C1 significantly delayed (3+ months at current volume)

### Recommended Path Forward: **Option B (Synthetic Labels + Real Data)**

**Why**:
- Unblocks training immediately (use existing 5,603 examples)
- Validates training pipeline before real data arrives
- Provides baseline XGBoost model for comparison
- Smooth transition to real user feedback as data accumulates

**Next Steps**:
1. Fix/verify click tracking (Priority 1)
2. Implement synthetic label training (Week 5)
3. Deploy engagement tracking (Week 5)
4. Collect 100-500 queries with position/dwell data (Weeks 6-10)
5. Fine-tune with real clicks (Weeks 11+)

---

**Report Generated**: 2025-12-03 20:30 UTC
**Database**: `data/analytics/query_logs.db`
**Phase**: B (Data Collection)
**Status**: IN PROGRESS - BLOCKED ON USER CLICKS
