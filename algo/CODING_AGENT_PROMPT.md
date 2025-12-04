# Phase A Implementation Prompt for Coding Agent

**Date**: 2025-01-28
**Status**: Ready for Implementation
**Primary Reference**: `algo/REVIEW_DECISIONS.md`

---

## 📋 Mission Overview

You are tasked with implementing **Phase A: XGBoost Infrastructure** for the NLWeb ML-powered search ranking system. This phase focuses on **infrastructure setup and shadow mode logging** - XGBoost will run in parallel but **will NOT affect user-visible results**.

**Success Criteria**:
- ✅ XGBoost pipeline integrates without breaking existing LLM ranking
- ✅ Analytics logging captures all required data for Phase B/C training
- ✅ No production impact (100% shadow mode)
- ✅ All tests pass

---

## 🎯 Core Principles (MUST FOLLOW)

### Constitution Constraints
Read `algo/phase_A_constitution.md` for complete rules. Key points:

1. **❌ DO NOT** change user-visible ranking results
   - XGBoost runs in shadow mode (logs predictions, doesn't affect output)
   - Always return LLM ranking results to users

2. **❌ DO NOT** query database during ranking loop
   - All features extracted from in-memory objects only
   - Latency must stay < 20ms

3. **✅ MUST** maintain pipeline order
   - Retrieval → LLM Ranking → **XGBoost (shadow)** → MMR → PostRanking
   - XGBoost depends on LLM scores (feature #23)

4. **✅ MUST** handle failures gracefully
   - XGBoost errors must never break production flow
   - Extensive error handling with fallback to LLM-only path

---

## 📦 Implementation Tasks

### **Priority 1: Critical (MUST Complete)**

#### Task 1.1: RankingResult Dataclass (Issue #1)
**Files**: `code/python/core/ranking.py`

**Specification**: `algo/REVIEW_DECISIONS.md` Lines 10-50

**Implementation**:
1. Create `@dataclass RankingResult` with these fields:
   - Basic: `url`, `title`, `description`, `site`, `schema_object`
   - Retrieval scores: `vector_score`, `bm25_score`, `keyword_boost`, `temporal_boost` (=0.0), `final_retrieval_score`
   - LLM: `llm_score`, `llm_snippet`
   - XGBoost: `xgboost_score`, `xgboost_confidence` (Optional[float])
   - MMR: `mmr_score`, `detected_intent` (Optional)
   - Vector: `vector` (Optional[List[float]], for MMR)

2. Update `retrieval_providers/qdrant.py`:
   - Change return type: `List[Tuple]` → `List[Dict]`
   - Dict structure includes `retrieval_scores` sub-dict (see spec)

3. Update `rank_results()`:
   - Accept Dict format from Qdrant
   - Use factory function `create_ranking_result()` to convert Dict → RankingResult
   - Preserve all existing LLM ranking logic

**Validation**:
- Run existing tests: `code/python/testing/run_all_tests.sh`
- Verify no change in ranking output

---

#### Task 1.2: Analytics Schema Migration (Issue #2)
**Files**: `code/python/core/query_logger.py`

**Specification**: `algo/REVIEW_DECISIONS.md` Lines 53-127

**Implementation**:

1. **Schema Migration** (Lines 168 & 199):
   - Add `xgboost_confidence DOUBLE PRECISION` column to `ranking_scores` table
   - Support both SQLite and PostgreSQL
   - Auto-detect existing v1 databases and upgrade

2. **New Logging Method** `log_xgboost_scores()`:
   ```python
   def log_xgboost_scores(
       self,
       query_id: str,
       doc_url: str,
       xgboost_score: float,
       xgboost_confidence: float,
       ranking_position: int
   ) -> None:
       """
       Log XGBoost predictions in shadow mode.

       Creates a NEW row in ranking_scores table with:
       - ranking_method = "xgboost_shadow"
       - xgboost_score, xgboost_confidence = actual values
       - llm_final_score, mmr_diversity_score = 0 (placeholder)
       """
   ```

3. **Multiple INSERTs Pattern** (CRITICAL - Lines 103-127):
   - Same `(query_id, doc_url)` will have MULTIPLE rows:
     - Row 1: `ranking_method='llm'` (LLM scores)
     - Row 2: `ranking_method='xgboost_shadow'` (XGBoost predictions)
     - Row 3: `ranking_method='mmr'` (MMR scores)
   - Phase C will JOIN by `ranking_method` field (see SQL example in spec)

**Validation**:
- Check schema migration works on both SQLite and PostgreSQL
- Verify `xgboost_confidence` column exists
- Test `log_xgboost_scores()` writes to database correctly

---

#### Task 1.3: Feature Index Constants (Issue #4)
**Files**: `code/python/training/feature_engineering.py`, `code/python/core/xgboost_ranker.py`

**Specification**: `algo/REVIEW_DECISIONS.md` Lines 175-212 + Lines 682-738

**Implementation**:

1. **Add constants to `feature_engineering.py`** (file top):
   ```python
   # Feature Index Constants (0-based)
   # Total: 29 features (Phase A)

   # Query Features (0-5)
   FEATURE_IDX_QUERY_LENGTH = 0
   FEATURE_IDX_WORD_COUNT = 1
   FEATURE_IDX_HAS_QUOTES = 2
   FEATURE_IDX_HAS_NUMBERS = 3
   FEATURE_IDX_HAS_QUESTION_WORDS = 4
   FEATURE_IDX_KEYWORD_COUNT = 5

   # Document Features (6-13)
   FEATURE_IDX_DOC_LENGTH = 6
   FEATURE_IDX_RECENCY_DAYS = 7
   FEATURE_IDX_HAS_AUTHOR = 8
   FEATURE_IDX_HAS_PUBLICATION_DATE = 9
   FEATURE_IDX_SCHEMA_COMPLETENESS = 10
   FEATURE_IDX_TITLE_LENGTH = 11
   FEATURE_IDX_DESCRIPTION_LENGTH = 12
   FEATURE_IDX_URL_LENGTH = 13

   # Query-Doc Features (14-20)
   FEATURE_IDX_VECTOR_SIMILARITY = 14
   FEATURE_IDX_BM25_SCORE = 15
   FEATURE_IDX_KEYWORD_BOOST = 16
   FEATURE_IDX_TEMPORAL_BOOST = 17
   FEATURE_IDX_FINAL_RETRIEVAL_SCORE = 18
   FEATURE_IDX_KEYWORD_OVERLAP_RATIO = 19
   FEATURE_IDX_TITLE_EXACT_MATCH = 20

   # Ranking Features (21-26)
   FEATURE_IDX_RETRIEVAL_POSITION = 21
   FEATURE_IDX_RANKING_POSITION = 22
   FEATURE_IDX_LLM_FINAL_SCORE = 23  # ← Critical for xgboost_ranker.py
   FEATURE_IDX_RELATIVE_SCORE_TO_TOP = 24
   FEATURE_IDX_SCORE_PERCENTILE = 25
   FEATURE_IDX_POSITION_CHANGE = 26

   # MMR Features (27-28)
   FEATURE_IDX_MMR_DIVERSITY_SCORE = 27
   FEATURE_IDX_DETECTED_INTENT = 28

   # Total
   TOTAL_FEATURES_PHASE_A = 29
   ```

2. **Update `xgboost_ranker.py`**:
   ```python
   from training.feature_engineering import (
       FEATURE_IDX_LLM_FINAL_SCORE,
       TOTAL_FEATURES_PHASE_A
   )

   def predict(self, features: np.ndarray):
       # Validate feature count
       assert features.shape[1] == TOTAL_FEATURES_PHASE_A, \
           f"Expected {TOTAL_FEATURES_PHASE_A} features, got {features.shape[1]}"

       # Use constant instead of hardcoded 23
       llm_scores = features[:, FEATURE_IDX_LLM_FINAL_SCORE]
   ```

3. **Version Management** (Lines 682-738):
   - Keep Phase A constants forever
   - Phase C will ADD new constants (don't replace):
     ```python
     # Phase C (future)
     TOTAL_FEATURES_PHASE_C = 35
     FEATURE_IDX_URL_CTR_7D = 29  # New historical features
     ```

**Validation**:
- Verify hardcoded `23` is replaced with `FEATURE_IDX_LLM_FINAL_SCORE`
- Test feature extraction produces 29 features
- Confirm assertion catches wrong feature counts

---

### **Priority 2: Optional (Nice to Have)**

#### Task 2.1: Magic Numbers Constant (Issue #9)
**Files**: `code/python/training/feature_engineering.py`

**Specification**: `algo/REVIEW_DECISIONS.md` Lines 373-413

**Implementation**:
- Add `MISSING_RECENCY_DAYS = 999999` constant
- Replace Line 126 & 128: `recency_days = MISSING_RECENCY_DAYS`

**Skip if time-constrained**: This is code style, not functionality.

---

#### Task 2.2: Edge Case Warning Logs (Issue #12)
**Files**: `code/python/core/xgboost_ranker.py`, `code/python/training/feature_engineering.py`

**Specification**: `algo/REVIEW_DECISIONS.md` Lines 527-555

**Implementation**:
- Add `logger.warning()` for **異常** edge cases:
  - Feature extraction 失敗
  - 所有 LLM scores = 0
  - Model loading 失敗

- **Do NOT log** 正常情況:
  - 只有 1 個結果
  - 沒有發布日期
  - Query keywords 為空

**Skip if time-constrained**: Logging enhancement, not core functionality.

---

## 🧪 Testing Requirements

### Unit Tests
Run existing test suite:
```bash
cd code/python
./testing/run_all_tests.sh
```

**All tests must pass**. If any test fails:
1. Check if your changes broke existing functionality
2. Update tests if test assumptions changed (but verify with architect first)

### Integration Test
Create a simple end-to-end test:

```python
# test_xgboost_shadow_mode.py

def test_xgboost_shadow_mode():
    """Verify XGBoost runs in shadow mode without affecting results"""

    # 1. Perform a search query
    query = "台北天氣"
    results_without_xgboost = search(query, xgboost_enabled=False)
    results_with_xgboost = search(query, xgboost_enabled=True)

    # 2. Rankings should be IDENTICAL (shadow mode)
    assert results_without_xgboost == results_with_xgboost

    # 3. But analytics should have xgboost_score logged
    db_rows = query_db("SELECT * FROM ranking_scores WHERE ranking_method='xgboost_shadow'")
    assert len(db_rows) > 0
    assert db_rows[0]['xgboost_score'] is not None
```

---

## 📚 Reference Documents (Read Before Coding)

### MUST READ:
1. **`algo/REVIEW_DECISIONS.md`** - Your implementation spec (THIS IS THE SOURCE OF TRUTH)
2. **`algo/phase_A_constitution.md`** - Non-negotiable constraints
3. **`.claude/CLAUDE.md`** - Project coding standards and debugging best practices

### Optional Reference:
4. **`algo/XGBoost_implementation.md`** - Full technical design (detailed background)
5. **`systemmap.md`** - API endpoints and system architecture

---

## ⚠️ Common Pitfalls (AVOID THESE)

### ❌ Don't:
1. **Modify LLM ranking logic** - XGBoost is shadow only, don't change production behavior
2. **Query database during ranking** - Will violate latency requirements
3. **Break existing tests** - All tests must pass
4. **Use hardcoded indices** - Use named constants (Issue #4)
5. **Add historical features** - Phase A is 29 features only (defer to Phase B/C)

### ✅ Do:
1. **Handle errors gracefully** - XGBoost failures shouldn't crash ranking
2. **Follow existing code style** - Match patterns in neighboring files
3. **Add async logging** - Use `query_logger.log_queue` (don't block ranking)
4. **Validate inputs** - Assert feature counts, check None values
5. **Ask if unclear** - Better to clarify than implement wrong spec

---

## 🚦 Completion Checklist

Before submitting, verify:

- [ ] **Issue #1**: RankingResult dataclass created, Qdrant returns Dict
- [ ] **Issue #2**: `xgboost_confidence` column added, `log_xgboost_scores()` implemented
- [ ] **Issue #4**: Feature index constants added, hardcoded `23` replaced
- [ ] All existing tests pass (`./testing/run_all_tests.sh`)
- [ ] Integration test shows shadow mode works (rankings unchanged)
- [ ] Analytics database logs XGBoost scores correctly
- [ ] No errors in logs during test queries
- [ ] Code follows project style (see `.claude/CLAUDE.md`)

**Optional**:
- [ ] Issue #9: Magic numbers → constants
- [ ] Issue #12: Edge case warning logs

---

## 🆘 When You Need Help

**If stuck or unclear**:
1. Re-read the relevant section in `algo/REVIEW_DECISIONS.md`
2. Check `algo/phase_A_constitution.md` for constraints
3. Look at existing code patterns in neighboring files
4. **Ask for clarification** - include:
   - Which Issue/Task you're working on
   - What's unclear
   - What you've tried

**Red Flags (Stop and Ask)**:
- 🚨 Tests are failing after your changes
- 🚨 Rankings changed (shadow mode violated)
- 🚨 Database queries during ranking (latency issue)
- 🚨 Uncertainty about multiple INSERTs pattern

---

## 📊 Success Metrics

**Phase A is successful when**:
1. ✅ XGBoost pipeline exists and runs
2. ✅ Analytics captures all 29 features + XGBoost predictions
3. ✅ User-visible results unchanged (shadow mode working)
4. ✅ No production errors or crashes
5. ✅ Ready for Phase B data collection

**Good luck! Follow the spec closely and you'll do great.** 🚀

---

**Questions? Re-read `algo/REVIEW_DECISIONS.md` - it has all the answers.**
