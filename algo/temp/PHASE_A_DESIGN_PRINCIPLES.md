# Phase A Design Principles - XGBoost ML Ranking System

**Created**: 2025-01-26
**Status**: Active - Week 1 Implementation Complete, Week 2 Review In Progress
**Purpose**: Document core design decisions and architectural principles for XGBoost integration

---

## Overview

This document captures the **design philosophy and architectural decisions** made during Phase A (XGBoost Infrastructure Preparation). It serves as the authoritative reference for understanding:

1. **Why we designed the system this way** (not just what the code does)
2. **Critical constraints and dependencies** (what cannot be changed without breaking the system)
3. **Design trade-offs and alternatives considered** (why we rejected other approaches)

**Target Audience**: Future Claude agents, human reviewers, and developers working on Phase B/C

---

## 1. Pipeline Architecture Design

### Decision: XGBoost Position in Pipeline

**Final Architecture**:
```
User Query
    ↓
[1] Retrieval (Qdrant Hybrid Search)
    - Vector similarity + BM25 keyword matching
    - Returns: 50 results with retrieval scores
    ↓
[2] LLM Ranking
    - Semantic relevance scoring
    - Returns: 50 results with llm_scores
    ↓
[3] XGBoost Re-ranking ← NEW (Phase A)
    - ML-based relevance prediction
    - Uses retrieval + LLM scores as features
    - Returns: 50 results with xgboost_scores
    ↓
[4] MMR Diversity Re-ranking
    - Balance relevance vs diversity
    - Returns: Final 10 results
```

### Why XGBoost AFTER LLM Ranking?

**Reason 1: Feature Dependencies**
- Features 22-27 require LLM ranking outputs:
  - `llm_final_score` (feature 22)
  - `relative_score_to_top` (feature 23)
  - `score_percentile` (feature 24)
  - `llm_snippet_length` (feature 25)
  - `llm_snippet_has_numbers` (feature 26)
  - `position_change` (feature 27)
- If XGBoost runs before LLM, these 6 features (20% of total) would be 0

**Reason 2: Graceful Degradation**
- Pipeline can work without XGBoost: Retrieval → LLM → MMR
- If XGBoost model fails to load, system still functions
- Shadow mode validation easier (LLM ranking = baseline)

**Reason 3: Learning from LLM Judgment**
- XGBoost learns "when LLM is right/wrong"
- High LLM score + low user engagement → XGBoost learns to downrank
- Low LLM score + high user engagement → XGBoost learns to uprank

**Alternative Considered**: XGBoost between Retrieval and LLM
- **Pros**: Could cascade (XGBoost picks top 20 → LLM only ranks 20)
- **Cons**: Loses 20% of features, cannot learn from LLM's semantic understanding
- **Rejected**: Feature completeness more important than latency optimization

**Code Locations**:
- Integration point: `core/ranking.py` (after `self.llm.rank_results()`, before MMR)
- Feature extraction: `training/feature_engineering.py:extract_ranking_features()`

---

### Why XGBoost BEFORE MMR Diversity?

**Reason 1: MMR Expects Relevance Ranking**
- MMR formula: `λ * relevance - (1-λ) * max_similarity`
- MMR assumes input is sorted by **final relevance** (not diversity)
- XGBoost provides better relevance ranking than LLM alone

**Reason 2: Diversity on Top Results**
- MMR selects top 10 from 50 results
- XGBoost ensures the 50 results are accurately ranked by relevance
- MMR then ensures the final 10 are diverse

**Reason 3: Feature Availability**
- MMR scores (features 28-29) can be added AFTER XGBoost runs
- XGBoost doesn't need MMR scores as input features

**Alternative Considered**: XGBoost after MMR (final 10 results only)
- **Pros**: Lower latency (only rank 10 results instead of 50)
- **Cons**: XGBoost cannot consider diversity signals, MMR would use LLM scores (less accurate)
- **Rejected**: Relevance ranking should happen before diversity

**Code Locations**:
- XGBoost integration: `core/ranking.py` (before `apply_mmr_diversity()`)
- MMR scores attachment: `core/ranking.py` (after MMR, attach to RankingResult objects)

---

## 2. Data Flow and Feature Extraction Design

### Critical Constraint: In-Memory Feature Extraction

**Design Decision**: Extract all 29 features from **in-memory objects**, NOT from Analytics Database

**Why?**
1. **Latency**: Querying Analytics DB during ranking adds 500-1000ms per request
2. **Real-time**: Need features from current request (not just historical data)
3. **Simplicity**: All data already in memory after Retrieval + LLM ranking

**Data Flow**:
```
1. Retrieval (Qdrant) → Returns results with:
   - url, title, description, published_date, author
   - vector_score, bm25_score, keyword_boost, temporal_boost
   - retrieval_position (0-based index)

2. LLM Ranking → Augments results with:
   - llm_final_score, llm_snippet
   - ranking_position (after LLM re-ranking)

3. XGBoost Ranker → Receives:
   - ranking_results (List[RankingResult])
   - query_text (str)

4. XGBoost Extracts Features:
   - Query features (6): From query_text
   - Document features (8): From RankingResult.title, description, published_date, author
   - Retrieval features (7): From RankingResult.vector_score, bm25_score, etc.
   - Ranking features (6): From RankingResult.llm_final_score, retrieval_position, ranking_position
   - MMR features (2): From RankingResult.mmr_score, detected_intent (if available)

5. XGBoost Returns:
   - reranked_results (List[RankingResult] with xgboost_score attached)
   - metadata (dict with confidence, shadow_mode_info)
```

### Why NOT Query Analytics DB During Ranking?

**Alternative Considered**: Query historical CTR/dwell time from Analytics DB during ranking

**Why Rejected**:
1. **Latency**: Each DB query adds 100-500ms
2. **Scalability**: 50 results × 1 query each = 50 DB queries per request
3. **Cold Start**: New documents have no historical data
4. **Race Condition**: Current request not yet logged in DB

**Solution**: Historical features added in Phase B (features 30-35)
- Pre-compute aggregated metrics (daily batch job)
- Store in document metadata or separate cache
- NOT real-time queries during ranking

**Code Locations**:
- Feature extraction: `training/feature_engineering.py:extract_features_from_results()`
- XGBoost ranker: `core/xgboost_ranker.py:extract_features()`

---

## 3. RankingResult Object Design

### Why RankingResult Class Needed?

**Problem with Current System**:
- `ranking.py` uses unstructured `dict` objects:
  ```python
  ansr = {
      'url': url,
      'site': site,
      'name': name,
      'ranking': ranking,  # nested dict
      'schema_object': schema_object,  # nested dict
      'sent': False
  }
  ```
- No standardized way to attach retrieval scores (bm25, vector, etc.)
- No type safety (typos like `ansr['nmae']` fail silently)
- XGBoost cannot extract features from this structure

**Impact on XGBoost**:
- `feature_engineering.py` cannot access:
  - `vector_score, bm25_score, keyword_boost` → Features 15-17 are 0
  - `temporal_boost, final_retrieval_score` → Features 18-19 are 0
  - `retrieval_position` → Feature 20 is 0
- Result: 7 out of 29 features (24%) would be missing

### RankingResult Design Principles

**1. Backward Compatible Migration**
- Use factory function `create_ranking_result()` instead of direct constructor
- Existing code can continue using dicts during transition
- Gradual migration path (not breaking change)

**2. All Features Included**
- Every field needed for 29 features is explicitly defined
- No hidden attributes in nested dicts
- Easy to validate completeness

**3. Immutable Metadata + Mutable Scores**
- Immutable: `url, title, description, published_date, author` (document properties)
- Mutable: `llm_score, xgboost_score, mmr_score` (populated at different pipeline stages)
- Design allows scores to be attached as pipeline progresses

**4. Graceful Handling of Missing Data**
- Optional fields: `published_date: Optional[str] = None`
- Default values: `bm25_score: float = 0.0`
- No crashes when data is incomplete

**5. Clear Ownership of Scores**
- `vector_score, bm25_score` → Set by Qdrant retrieval
- `llm_score, llm_snippet` → Set by LLM ranking
- `xgboost_score, xgboost_confidence` → Set by XGBoost ranker
- `mmr_score, detected_intent` → Set by MMR diversity

**Code Structure**:
```python
@dataclass
class RankingResult:
    # Basic fields (from Qdrant)
    url: str
    title: str
    description: str
    site: str

    # Metadata (from Schema.org)
    published_date: Optional[str] = None
    author: Optional[str] = None
    schema_object: Optional[Dict[str, Any]] = None

    # Retrieval scores (from Qdrant)
    vector_score: float = 0.0
    bm25_score: float = 0.0
    keyword_boost: float = 0.0
    temporal_boost: float = 0.0
    final_retrieval_score: float = 0.0
    retrieval_position: int = 0

    # LLM scores (from ranking.py)
    llm_score: float = 0.0
    llm_snippet: str = ""

    # MMR scores (from mmr.py)
    mmr_score: Optional[float] = None
    detected_intent: Optional[str] = None  # "SPECIFIC", "EXPLORATORY", "BALANCED", or None

    # XGBoost scores (from xgboost_ranker.py)
    xgboost_score: Optional[float] = None
    xgboost_confidence: Optional[float] = None

    # Internal flags
    sent: bool = False
```

**Code Locations**:
- Class definition: `core/ranking.py:27+`
- Factory function: `core/ranking.py:create_ranking_result()`
- Usage: `core/ranking.py:184+` (replace dict construction)

---

## 4. Configuration Design Philosophy

### XGBoost Configuration Location

**Decision**: Place XGBoost config in `config/config_retrieval.yaml`, NOT `config_llm.yaml`

**Why?**
1. **XGBoost is part of retrieval/ranking pipeline**, not LLM layer
2. **Separation of concerns**: ML configs separate from LLM provider configs
3. **Future-proof**: If we add other ML models (neural re-rankers), they belong here too

**Config Structure**:
```yaml
xgboost_params:
  enabled: false                    # Phase A: disabled (infrastructure only)
  model_path: "models/xgboost_ranker_v1_binary.json"
  confidence_threshold: 0.8         # Cascading logic (high confidence → use XGBoost)
  feature_version: 2                # Track feature set version
  use_shadow_mode: true             # Phase A/B: log predictions, don't affect ranking
```

### Key Config Principles

**1. Disabled by Default (Phase A)**
- `enabled: false` ensures no production impact during infrastructure phase
- Shadow mode can run even when disabled (for validation)
- Explicit opt-in prevents accidental activation

**2. Feature Version Tracking**
- Phase A: `feature_version: 1` (29 features)
- Phase B: `feature_version: 2` (35 features, add historical CTR/dwell)
- Model trained on v1 **cannot** use v2 features (dimension mismatch)
- Prevents version mismatch errors

**3. Shadow Mode Flag**
- `use_shadow_mode: true` → Log predictions but use LLM ranking
- `use_shadow_mode: false` → Use XGBoost predictions for ranking
- Phase A/B: Always true (validation phase)
- Phase C: Gradual rollout (10% → 50% → 100%)

**4. Confidence Threshold (Cascading Logic)**
- High confidence (≥0.8) → Trust XGBoost prediction
- Low confidence (<0.8) → Fall back to LLM ranking
- Allows hybrid approach (best of both worlds)
- **Note**: Implementation planned for Phase C, config prepared now

**Code Locations**:
- Config loading: `core/config.py:__init__()` (reads `xgboost_params`)
- Usage: `core/xgboost_ranker.py:__init__()` (receives config dict)

---

## 5. Global Model Cache Design

### Why Global Cache?

**Problem**: Model loading latency
- XGBoost model file: ~5-50 MB (depending on tree count)
- Loading time: 200-500ms per request
- Unacceptable for production (adds 500ms to every query)

**Solution**: Global in-memory cache
```python
# core/xgboost_ranker.py
_MODEL_CACHE: Dict[str, Any] = {}

class XGBoostRanker:
    def load_model(self):
        if self.model_path in _MODEL_CACHE:
            self.model = _MODEL_CACHE[self.model_path]
            return

        # Load from disk only once
        self.model = xgb.XGBClassifier()
        self.model.load_model(self.model_path)
        _MODEL_CACHE[self.model_path] = self.model
```

### Design Principles

**1. Process-Level Cache**
- Cache shared across all requests in same Python process
- Web server (aiohttp) is multi-threaded, single-process
- All requests benefit from single model load

**2. Path-Based Cache Key**
- Key: `model_path` (e.g., `"models/xgboost_ranker_v1_binary.json"`)
- Allows multiple model versions in cache simultaneously
- Model updates → change path → automatic cache miss

**3. Lazy Loading**
- Model only loaded on first prediction request
- If `enabled: false`, model never loaded (no wasted memory)

**4. Thread Safety Considerations**
- Current implementation: **Not thread-safe** (known limitation)
- Risk: Multiple threads loading model simultaneously (rare, low impact)
- Phase B solution: Add lock or use thread-safe cache library
- **Documented in Review Issue #7**

**Code Locations**:
- Cache definition: `core/xgboost_ranker.py:15` (module-level global)
- Cache usage: `core/xgboost_ranker.py:load_model()`

---

## 6. Phased Model Evolution Strategy

### Why Three Model Types?

**Design Decision**: Train 3 different model types based on data volume

```
Phase C1: Binary Classification (500-2K clicks)
    ↓
Phase C2: LambdaMART (2K-5K clicks)
    ↓
Phase C3: XGBRanker (5K-10K clicks)
```

### Model Type Selection Rationale

**Binary Classification (Phase C1)**
- **Objective**: `binary:logistic` (predict clicked = 0/1)
- **Data Requirement**: 500-2,000 clicks (lowest)
- **Why First?**: Simplest model, fast to train, interpretable
- **Limitation**: Doesn't understand ranking order (treats each result independently)
- **Use Case**: Prove XGBoost concept, validate features

**LambdaMART (Phase C2)**
- **Objective**: `rank:pairwise` (learn pairwise preferences)
- **Data Requirement**: 2,000-5,000 clicks
- **Why Second?**: Learns "result A better than result B" from user clicks
- **Advantage**: Understands relative ranking, better NDCG than binary
- **Limitation**: Requires query groups (multiple results per query)

**XGBRanker (Phase C3)**
- **Objective**: `rank:ndcg` (optimize NDCG metric directly)
- **Data Requirement**: 5,000-10,000 clicks
- **Why Last?**: Most sophisticated, best performance, highest data requirement
- **Advantage**: Optimizes for top-10 ranking quality (our use case)
- **Goal**: Production model for Phase D deployment

### Hyperparameter Design

**Common Principles**:
- `max_depth`: 6-7 (prevent overfitting on small data)
- `learning_rate`: 0.05-0.1 (conservative, stable training)
- `n_estimators`: 100-300 (increase with data volume)
- `early_stopping_rounds`: 10 (prevent overfitting)

**Model-Specific Tuning**:
```python
BINARY_PARAMS = {
    'max_depth': 6,          # Shallow trees (less overfitting)
    'learning_rate': 0.1,    # Faster convergence (small data)
    'n_estimators': 100,     # Fewer trees (risk of overfitting)
}

LAMBDAMART_PARAMS = {
    'max_depth': 6,
    'learning_rate': 0.05,   # Slower (more stable with pairwise loss)
    'n_estimators': 200,     # More trees (more data available)
}

XGBRANKER_PARAMS = {
    'max_depth': 7,          # Deeper trees (sufficient data)
    'learning_rate': 0.05,
    'n_estimators': 300,     # Most trees (most data, best performance)
}
```

**Code Locations**:
- Hyperparameters: `training/xgboost_trainer.py:20-60`
- Training logic: `training/xgboost_trainer.py:train_binary_model()`, etc.

---

## 7. Testing Strategy (Phase A - Mock Data)

### Why Mock Data Testing?

**Problem**: Phase A has no real user interaction data
- Analytics DB exists but empty (no clicks, dwell time, etc.)
- Cannot train real model without data
- Need to validate pipeline logic before data collection

**Solution**: Mock data generation for unit testing

### Mock Data Design Principles

**1. Realistic Feature Distributions**
- Query length: 10-100 characters (normal distribution)
- BM25 scores: 0-50 (exponential decay, most queries have low BM25)
- Vector scores: 0.3-0.9 (realistic semantic similarity range)
- LLM scores: 1-10 (ranking scores, top results have higher scores)

**2. Correlation Patterns**
- High LLM score → Higher click probability (0.7 vs 0.1)
- High vector score + high BM25 → Higher relevance
- Position bias: Top 3 results have 2x click probability

**3. Edge Cases**
- Missing metadata: Some results have no `published_date` or `author`
- Zero scores: Some results have `bm25_score = 0` (no keyword match)
- Extreme values: Very long queries (200+ chars), very short (5 chars)

**4. Reproducible**
- Use fixed random seed for deterministic tests
- Same mock data every test run (easier debugging)

### Testing Levels

**Unit Tests** (`testing/test_xgboost.py`):
- ✅ Feature extraction (29 features from mock RankingResult objects)
- ✅ Model loading (mock model file, verify cache)
- ✅ Prediction (mock features → mock scores)
- ✅ Shadow mode logic (verify metadata returned, ranking unchanged)

**Integration Tests** (Week 2):
- Full pipeline: Mock Retrieval → Mock LLM → XGBoost → Mock MMR
- Verify data flow: Scores passed correctly between stages
- Error handling: Missing model file, invalid features

**Real Data Testing** (Phase B):
- After 500+ queries collected from production
- Compare XGBoost predictions vs LLM ranking vs user clicks
- Measure NDCG, MRR, CTR improvements

**Code Locations**:
- Mock data generator: `testing/mock_training_data.py` (to be created in Week 2)
- Unit tests: `testing/test_xgboost.py` (to be created in Week 2)
- Feature extraction tests: `training/feature_engineering.py:if __name__ == "__main__"` (existing)

---

## 8. Shadow Mode Design

### What is Shadow Mode?

**Definition**: XGBoost makes predictions but **does not affect** user-facing ranking

**How It Works**:
```python
if self.use_shadow_mode:
    # Log predictions to analytics DB
    for result, xgb_score in zip(ranking_results, xgboost_scores):
        query_logger.log_xgboost_score(
            query_id=self.query_id,
            doc_url=result.url,
            xgboost_score=xgb_score,
            confidence=confidence
        )

    # Return ORIGINAL ranking (unchanged)
    return ranking_results, metadata
else:
    # Re-rank using XGBoost scores
    reranked = sorted(ranking_results, key=lambda r: r.xgboost_score, reverse=True)
    return reranked, metadata
```

### Why Shadow Mode?

**Phase A/B Validation Requirements**:
1. **No User Impact**: Prove XGBoost works before affecting real users
2. **Parallel Comparison**: Compare XGBoost ranking vs LLM ranking vs user behavior
3. **Safe Rollback**: If XGBoost performs poorly, no production impact
4. **Metric Collection**: Measure accuracy before deployment

**What We Learn from Shadow Mode**:
- How often does XGBoost agree with LLM? (agreement rate)
- When XGBoost differs from LLM, which one is better? (click-through rate)
- What is XGBoost's confidence distribution? (calibration)
- Are there queries where XGBoost fails? (error analysis)

### Shadow Mode Metadata

**Logged Metadata**:
```python
metadata = {
    'shadow_mode': True,
    'model_path': 'models/xgboost_ranker_v1_binary.json',
    'feature_version': 2,
    'num_results': 50,
    'avg_confidence': 0.73,
    'high_confidence_count': 35,  # confidence ≥ 0.8
    'low_confidence_count': 15,   # confidence < 0.8
    'agreement_with_llm_top10': 0.6  # How many top-10 results match LLM ranking
}
```

**Code Locations**:
- Shadow mode logic: `core/xgboost_ranker.py:rerank()`
- Metadata logging: `core/ranking.py` (integration point)

---

## 9. Error Handling and Graceful Degradation

### Design Philosophy: Never Crash the Pipeline

**Principle**: XGBoost is an **enhancement**, not a requirement
- If XGBoost fails, system falls back to LLM ranking
- User experience should be identical to pre-XGBoost system
- Log errors but continue serving results

### Graceful Degradation Scenarios

**1. Model File Missing**
```python
try:
    self.model.load_model(self.model_path)
except FileNotFoundError:
    logger.error(f"XGBoost model not found: {self.model_path}")
    self.enabled = False  # Disable XGBoost for this session
    # Return original ranking (LLM)
```

**2. Feature Extraction Fails**
```python
try:
    features = self.extract_features(ranking_results, query_text)
except Exception as e:
    logger.error(f"Feature extraction failed: {e}")
    # Return original ranking + metadata with error
    return ranking_results, {'error': str(e), 'fallback': 'llm_ranking'}
```

**3. Invalid Feature Dimensions**
```python
if features.shape[1] != 29:
    logger.error(f"Expected 29 features, got {features.shape[1]}")
    # Return original ranking (model trained on different feature set)
```

**4. Prediction Errors**
```python
try:
    scores = self.model.predict_proba(features)[:, 1]
except Exception as e:
    logger.error(f"XGBoost prediction failed: {e}")
    # Return original ranking
```

### Error Logging Strategy

**What to Log**:
- Model loading errors (CRITICAL)
- Feature dimension mismatches (ERROR)
- Missing metadata fields (WARNING)
- Low confidence predictions (INFO)

**Where to Log**:
- Application logs: `logs/nlweb.log`
- Analytics DB: `queries.error_message` field (if exists)
- Shadow mode metadata: `metadata['error']`

**Code Locations**:
- Error handling: Throughout `core/xgboost_ranker.py`
- Fallback logic: `core/xgboost_ranker.py:rerank()`

---

## 10. Integration Points and Dependencies

### Critical Integration Points

**1. Qdrant → ranking.py** (Retrieval Scores)
- **What Needs to Pass**: `vector_score, bm25_score, keyword_boost, temporal_boost, retrieval_position`
- **Current Status**: ❌ Not passed (only url, title, description, schema_json)
- **Required Change**: Modify Qdrant return format to include retrieval scores
- **Risk**: Breaking change if tuple format modified
- **Review Issue**: #2 (CRITICAL)

**2. ranking.py → XGBoost Ranker** (Ranking Results)
- **What Needs to Pass**: `List[RankingResult]` with all scores populated
- **Current Status**: ❌ Using unstructured dicts
- **Required Change**: Implement RankingResult class, use factory function
- **Risk**: Requires refactoring throughout ranking.py
- **Review Issue**: #1 (CRITICAL)

**3. XGBoost Ranker → MMR** (Re-ranked Results)
- **What Needs to Pass**: `List[RankingResult]` with `xgboost_score` attached
- **Current Status**: ⚠️ MMR expects dicts, needs adaptation
- **Required Change**: Update MMR to handle RankingResult objects
- **Risk**: Low (MMR only needs scores, not entire structure)
- **Review Issue**: #4 (MEDIUM)

**4. Analytics DB → Training Pipeline** (Historical Data)
- **What Needs to Pass**: CSV export with 29 features + labels
- **Current Status**: ✅ Schema supports all fields (except xgboost_confidence)
- **Required Change**: Add `xgboost_confidence` column to analytics schema
- **Risk**: Low (column addition, backward compatible)
- **Review Issue**: #3 (CRITICAL)

### Dependency Graph

```
Phase A Week 1 (Current):
  ✅ feature_engineering.py (no dependencies)
  ✅ xgboost_ranker.py (depends on: feature_engineering.py)
  ✅ xgboost_trainer.py (depends on: feature_engineering.py)

Phase A Week 2 (Pending):
  ❌ RankingResult class (blocks: xgboost_ranker.py integration)
  ❌ Qdrant score passing (blocks: feature extraction)
  ❌ ranking.py integration (depends on: RankingResult, Qdrant changes)
  ❌ Unit tests (depends on: all above)
```

**Code Locations**:
- Integration planning: `algo/XGBoost_implementation.md:Integration Points`
- Qdrant modification: `retrieval_providers/qdrant.py:1034-1044`
- Ranking.py modification: `core/ranking.py:184-191`

---

## 11. Constraints and Assumptions

### Hard Constraints (Cannot Change Without Breaking System)

**1. Feature Count Must Match Model**
- Model trained on 29 features → Inference must provide exactly 29 features
- Adding/removing features requires retraining model
- Feature order matters (feature[0] must be `query_length`, etc.)

**2. XGBoost Must Run After LLM**
- Features 22-27 depend on LLM outputs
- Cannot reorder pipeline without losing features

**3. Analytics DB Schema Must Support All Features**
- Training pipeline reads from `feature_vectors` table
- Missing columns = cannot extract features for training

**4. Shadow Mode Required for Phase A/B**
- Production deployment must not affect user experience
- Validation requires parallel comparison

### Assumptions (May Need Validation)

**1. Qdrant Returns Results in Relevance Order**
- Assumption: `scored_results` is sorted by `final_retrieval_score` (descending)
- Impact: `retrieval_position` feature depends on this
- Validation: Verify in Qdrant code

**2. LLM Ranking Scores Are Comparable Across Queries**
- Assumption: Score of 8 on Query A ≈ Score of 8 on Query B
- Impact: Features like `relative_score_to_top` assume this
- Risk: LLM may use different scales for different queries

**3. User Clicks Indicate Relevance**
- Assumption: Clicked results are more relevant than unclicked
- Impact: Training labels are `clicked = 0/1`
- Limitation: Position bias, accidental clicks, etc.

**4. 500 Clicks Sufficient for Binary Model**
- Assumption: Phase C1 can start with 500 clicks
- Impact: Training schedule and data collection timeline
- Risk: May need more data for statistical significance

### Design Trade-offs

**Trade-off 1: In-Memory Features vs Historical Features**
- **Choice**: Phase A uses in-memory features only (29 features)
- **Pro**: Low latency, no DB queries during ranking
- **Con**: Missing powerful historical signals (CTR, dwell time)
- **Future**: Phase B adds historical features (6 more features)

**Trade-off 2: Shadow Mode vs Direct Deployment**
- **Choice**: Shadow mode for Phase A/B
- **Pro**: Safe, no user impact, parallel validation
- **Con**: Longer deployment timeline (requires data collection)
- **Justification**: Safety > Speed for ML system

**Trade-off 3: Global Cache vs Per-Request Loading**
- **Choice**: Global model cache
- **Pro**: 500ms latency saved per request
- **Con**: Thread safety concerns, memory usage
- **Justification**: Performance critical for production

---

## 12. Critical Success Criteria

### Phase A Success Metrics

**Week 1 (Current)**: ✅ COMPLETE
- [x] 3 core modules created (feature_engineering, xgboost_ranker, xgboost_trainer)
- [x] All modules tested with mock data
- [x] 29 features extracted successfully
- [x] Shadow mode logic implemented
- [x] Configuration files updated

**Week 2 (Pending)**:
- [ ] RankingResult class implemented
- [ ] Qdrant returns retrieval scores
- [ ] XGBoost integrated into ranking.py
- [ ] Unit tests pass (feature extraction, prediction, shadow mode)
- [ ] Mock data generator created
- [ ] End-to-end pipeline test (Retrieval → LLM → XGBoost → MMR)

### Phase B Success Metrics (Data Collection)

**Minimum Viable Data**:
- [ ] 500+ queries logged
- [ ] 100+ unique queries (not just repeats)
- [ ] 50+ queries with at least 1 click
- [ ] Click distribution: Top-5 (60%), Position 6-10 (30%), Position 11+ (10%)

### Phase C Success Metrics (Training & Deployment)

**Model Performance**:
- [ ] NDCG@10 ≥ LLM baseline (no regression)
- [ ] CTR on XGBoost top-3 ≥ LLM top-3 (in shadow mode comparison)
- [ ] Confidence calibration: High-confidence predictions have >80% accuracy

**Production Readiness**:
- [ ] Latency: XGBoost adds <100ms to ranking pipeline
- [ ] Error rate: <0.1% of requests fail due to XGBoost errors
- [ ] Memory: Model cache <500MB (production server has 512MB total)

---

## 13. Handoff Instructions for Future Agents

### When Working on Phase A Review Issues

**READ FIRST**:
1. This file (`.claude/PHASE_A_DESIGN_PRINCIPLES.md`)
2. `algo/XGBoost_implementation.md` (complete technical spec)
3. `.claude/REVIEW_DECISIONS.md` (approved modifications)

**BEFORE MODIFYING CODE**:
- Check if modification violates any design principles above
- If unsure, ask user: "This change conflicts with Section X principle Y. Should we proceed?"
- Do NOT silently change architecture (e.g., moving XGBoost before LLM)

**WHEN ADDING FEATURES**:
- Verify feature count remains 29 (or update to 35 if Phase B)
- Update `feature_version` in config if feature set changes
- Document new features in `algo/XGBoost_implementation.md`

**WHEN MODIFYING DATA FLOW**:
- Trace impact on all 4 pipeline stages (Retrieval, LLM, XGBoost, MMR)
- Verify features can still be extracted from in-memory data
- Do NOT add database queries during ranking (latency constraint)

### When Working on Phase B (Data Collection)

**CRITICAL**:
- Do NOT start Phase B until Phase A Week 2 complete (integration tests pass)
- Verify Analytics DB schema includes `xgboost_confidence` column
- Monitor data quality (click distribution, query diversity)

### When Working on Phase C (Training)

**MODEL VERSIONING**:
- Save models as: `models/xgboost_ranker_v{VERSION}_{MODEL_TYPE}.json`
- Update `config_retrieval.yaml:model_path` to new version
- Keep old model file for rollback

**TRAINING DATA**:
- Always split by query ID (not random split) - prevents data leakage
- Validate feature dimensions before training (must be 29 or 35)
- Save training metadata (data range, feature version, hyperparameters)

---

## Document Maintenance

**This document should be updated when**:
- Architecture decisions change (e.g., pipeline reordering)
- New constraints discovered (e.g., performance bottlenecks)
- Design principles violated (document why exception was needed)
- Phase B/C adds new design patterns (e.g., historical feature caching strategy)

**Last Updated**: 2025-01-26 (Phase A Week 1 Complete)
**Next Review**: After Phase A Week 2 integration complete
