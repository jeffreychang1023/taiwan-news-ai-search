# Negative Constraints - What We Deliberately Did NOT Do

**Purpose**: Document rejected design decisions to prevent future agents from reintroducing them
**Created**: 2025-01-26
**Related**: `PHASE_A_DESIGN_PRINCIPLES.md`, `REVIEW_DECISIONS.md`

---

## Overview

This document records **design alternatives that were considered and explicitly rejected**. These are "negative constraints" - things we deliberately chose NOT to do, with documented rationale.

**Why This Matters**:
- Future agents may suggest the same "improvements" without knowing they were already rejected
- During refactoring, it's tempting to "optimize" in ways that violate original design principles
- Review feedback (e.g., performance concerns) can lead to reintroducing complexity we intentionally avoided

**If you're considering violating a constraint in this document**:
1. Re-read the rationale carefully
2. Check if the original concern still applies
3. Ask the user before proceeding
4. If approved, document why the constraint was lifted

---

## 1. Pipeline Architecture Constraints

### ❌ DO NOT: Place XGBoost Before LLM Ranking

**Rejected Alternative**: Retrieval → XGBoost → LLM (or Retrieval → XGBoost → Top 20 → LLM)

**Why It Seems Appealing**:
- Could reduce LLM calls (XGBoost picks top 20, LLM only ranks 20 instead of 50)
- Potential cost savings: 60% fewer LLM ranking calls
- Lower latency: Fewer documents to process

**Why We Rejected It**:
1. **Feature Loss**: Features 22-27 (LLM scores) would be unavailable to XGBoost
   - `llm_final_score`, `relative_score_to_top`, `score_percentile`, etc.
   - Loses 20% of feature set (6 out of 29 features)
2. **Cannot Learn from LLM**: XGBoost needs to learn "when LLM is right/wrong"
   - High LLM score + low engagement → downrank
   - Low LLM score + high engagement → uprank
3. **Accuracy > Cost**: Design principle is "Accuracy > Speed > Cost"
   - Losing 20% of features would hurt accuracy
   - Cost optimization should not sacrifice ML model effectiveness

**When This Might Be Reconsidered**:
- If features 22-27 prove to be low-importance (feature importance analysis in Phase C)
- If cost becomes prohibitive (> $10/day) and accuracy impact is measured as < 5%
- MUST validate with A/B testing before changing

**Related Decisions**:
- Section 1 of `PHASE_A_DESIGN_PRINCIPLES.md` (Pipeline Architecture)

---

### ❌ DO NOT: Place XGBoost After MMR Diversity

**Rejected Alternative**: Retrieval → LLM → MMR → XGBoost (final 10 results)

**Why It Seems Appealing**:
- Only re-rank 10 results instead of 50 (lower latency)
- XGBoost sees diverse results (diversity signals)

**Why We Rejected It**:
1. **MMR Expects Relevance Ranking**: MMR formula `λ * relevance - (1-λ) * similarity`
   - Assumes input is sorted by **final relevance**
   - If input is pre-diversified, MMR breaks
2. **Relevance Before Diversity**: Standard IR pipeline
   - First: Sort by relevance (XGBoost's job)
   - Then: Diversify top results (MMR's job)
3. **Feature Availability**: MMR scores (features 28-29) can be added after XGBoost
   - No dependency preventing this order

**When This Might Be Reconsidered**:
- Never (this violates fundamental IR principles)

**Related Decisions**:
- Section 1 of `PHASE_A_DESIGN_PRINCIPLES.md` (Why XGBoost BEFORE MMR)

---

### ❌ DO NOT: Run XGBoost in Parallel with LLM

**Rejected Alternative**: Retrieval → [XGBoost + LLM in parallel] → Ensemble/Voting

**Why It Seems Appealing**:
- Lower latency (parallel execution)
- Could ensemble XGBoost + LLM scores (weighted average)
- Diversity of ranking signals

**Why We Rejected It**:
1. **Feature Dependency**: XGBoost needs LLM scores as features (features 22-27)
   - Cannot run in parallel if one depends on the other
2. **Complexity**: Ensemble logic adds another tuning parameter
   - How to weight XGBoost vs LLM? (another hyperparameter to tune)
   - Harder to debug when results are poor
3. **XGBoost Already Learns Weighting**: XGBoost can learn to trust/distrust LLM scores
   - No need for manual ensemble weights

**When This Might Be Reconsidered**:
- If we build a separate XGBoost model that doesn't use LLM features
- If we use a meta-learner to combine both (Phase D advanced topic)

---

## 2. Data Flow and Feature Extraction Constraints

### ❌ DO NOT: Query Analytics Database During Ranking

**Rejected Alternative**: Extract features by querying Analytics DB in real-time during ranking

**Why It Seems Appealing**:
- Single source of truth (all features from DB)
- Historical features (CTR, dwell time) immediately available
- No need to pass data through pipeline

**Why We Rejected It**:
1. **Latency**: Each DB query adds 100-500ms
   - 50 results × 1 query each = 50 DB queries = 5-25 seconds added latency
   - Unacceptable for production (current total latency target: 3-5 seconds)
2. **Scalability**: DB becomes bottleneck
   - Concurrent queries would overload Neon.tech free tier (512MB)
3. **Race Condition**: Current request not yet logged
   - `query_id` for current request doesn't exist in DB yet
   - Cannot get "current query's" LLM scores from DB
4. **Cold Start**: New documents have no historical data
   - Would need fallback logic anyway

**Allowed Alternative**:
- **Pre-computed Historical Features** (Phase B):
  - Batch job computes aggregated metrics daily (CTR, avg dwell time per URL)
  - Store in document metadata or separate cache (in-memory or Redis)
  - Feature extraction reads from cache (< 10ms), not DB query

**When This Might Be Reconsidered**:
- Never for in-request features (features 1-29)
- Possibly for historical features (features 30-35) if we use pre-computed cache

**Related Decisions**:
- Section 2 of `PHASE_A_DESIGN_PRINCIPLES.md` (In-Memory Feature Extraction)

---

### ❌ DO NOT: Use Asynchronous Feature Extraction

**Rejected Alternative**: Extract features asynchronously (background tasks, message queues)

**Why It Seems Appealing**:
- Non-blocking: Don't wait for feature extraction
- Parallel processing: Extract features for 50 results concurrently
- Could reduce latency if features are slow to compute

**Why We Rejected It**:
1. **Synchronous Pipeline**: Current design is synchronous request-response
   - User sends query → waits for response
   - Async feature extraction doesn't fit this model
2. **Complexity**: Adds async coordination overhead
   - Need to wait for all 50 feature extractions to complete
   - Error handling becomes harder (what if 1 out of 50 fails?)
3. **Features Are Fast**: Current feature extraction is < 10ms
   - No need to optimize something that's already fast
   - Premature optimization

**When This Might Be Reconsidered**:
- If feature extraction becomes a bottleneck (> 500ms)
- If we add slow features (e.g., neural network inference for embeddings)

**Related Decisions**:
- Section 2 of `PHASE_A_DESIGN_PRINCIPLES.md` (Data Flow Design)

---

## 3. Data Structure Constraints

### ❌ DO NOT: Use Named Tuples Instead of Dataclass

**Rejected Alternative**: Use `collections.namedtuple` or `typing.NamedTuple` for RankingResult

**Why It Seems Appealing**:
- Lightweight: No dataclass decorator overhead
- Immutable: Prevents accidental mutation
- Compatible with tuple unpacking

**Why We Rejected It**:
1. **Mutability Required**: RankingResult scores are populated at different stages
   - `llm_score` set during LLM ranking
   - `xgboost_score` set during XGBoost re-ranking
   - `mmr_score` set during MMR diversity
   - Named tuples are immutable (would need to create new instance each time)
2. **Default Values**: Dataclass supports `field(default=0.0)`
   - Named tuples require all fields at creation time
3. **Type Hints**: Dataclass has better IDE support
   - Auto-completion for fields
   - Type checking

**Allowed Alternative**:
- **Dict Format** (current Qdrant return): Acceptable for backward compatibility
- **Pydantic Models**: If we need validation (Phase B/C)

**When This Might Be Reconsidered**:
- If we switch to functional programming style (immutable data)
- If we need serialization/deserialization (Pydantic BaseModel)

**Related Decisions**:
- Section 3 of `PHASE_A_DESIGN_PRINCIPLES.md` (RankingResult Design)
- Issue #1 in `REVIEW_DECISIONS.md` (RankingResult vs Dict)

---

### ❌ DO NOT: Modify Qdrant Return Format to Tuple with More Elements

**Rejected Alternative**: Change Qdrant from 4/5-tuple to 6/7-tuple (add retrieval_scores)

**Why It Seems Appealing**:
- Minimal code change: Just add one more element to tuple
- Backward compatible-ish: Old code ignores extra elements

**Why We Rejected It**:
1. **Backward Compatibility Risk**: All calling code must be updated
   - `url, schema_json, name, site = item` → fails if item has 5 elements
   - Need to update baseHandler.py, ranking.py, and any other callers
2. **Tuple Unpacking Fragility**: Easy to make mistakes
   - `url, schema_json, name, site, scores = item` vs `url, schema_json, name, site, vector, scores = item`
   - Hard to remember which position is which
3. **Not Future-Proof**: Adding more fields requires changing tuple size again
   - Phase B might add more fields → another breaking change

**Approved Alternative**:
- **Dict Format** (Review Agent recommendation):
  - `{'url': ..., 'title': ..., 'retrieval_scores': {...}}`
  - Future-proof: Can add fields without breaking structure
  - Readable: `item['url']` vs `item[0]`

**When This Might Be Reconsidered**:
- Never (this decision is final for Phase A)

**Related Decisions**:
- Issue #1 Modification #2 in `REVIEW_DECISIONS.md`

---

## 4. Configuration and Deployment Constraints

### ❌ DO NOT: Place XGBoost Config in config_llm.yaml

**Rejected Alternative**: Add `xgboost_params` to `config/config_llm.yaml`

**Why It Seems Appealing**:
- XGBoost uses LLM scores → seems related to LLM
- Fewer config files to manage

**Why We Rejected It**:
1. **Separation of Concerns**: XGBoost is part of retrieval/ranking pipeline, not LLM layer
   - LLM is a service provider (like Anthropic, OpenAI)
   - XGBoost is a pipeline component (like BM25, MMR)
2. **Future ML Models**: If we add neural re-rankers, they also belong in retrieval config
   - Keeps all ML ranking configs together
3. **Clarity**: Config file names should match functionality
   - `config_llm.yaml` = LLM provider settings (API keys, models, prompts)
   - `config_retrieval.yaml` = Retrieval and ranking settings (BM25, MMR, XGBoost)

**When This Might Be Reconsidered**:
- Never (architectural principle)

**Related Decisions**:
- Section 4 of `PHASE_A_DESIGN_PRINCIPLES.md` (Configuration Design)

---

### ❌ DO NOT: Enable XGBoost by Default in Phase A

**Rejected Alternative**: Set `enabled: true` in config for Phase A

**Why It Seems Appealing**:
- Get immediate feedback on XGBoost performance
- Start collecting shadow mode data sooner

**Why We Rejected It**:
1. **No Trained Model Yet**: Phase A is infrastructure only
   - Model file doesn't exist until Phase C training
   - `enabled: true` would cause errors
2. **Explicit Opt-In**: Prevents accidental activation
   - Phase B: Enable shadow mode explicitly
   - Phase C: Enable production mode explicitly
3. **Safety**: No production impact until proven safe

**When This Might Be Reconsidered**:
- Phase B: Set `enabled: false`, `use_shadow_mode: true` (logging only)
- Phase C: Set `enabled: true`, `use_shadow_mode: false` (gradual rollout)

**Related Decisions**:
- Section 4 of `PHASE_A_DESIGN_PRINCIPLES.md` (Disabled by Default)

---

## 5. Testing and Validation Constraints

### ❌ DO NOT: Use Random Train/Test Split for Model Training

**Rejected Alternative**: Shuffle all query-document pairs and split 80/20

**Why It Seems Appealing**:
- Simple: `train_test_split(X, y, test_size=0.2, shuffle=True)`
- Standard practice in many ML tutorials
- Ensures balanced distribution

**Why We Rejected It**:
1. **Data Leakage**: Same query's results appear in both train and test
   - Query "machine learning" has 50 results
   - Random split: 40 results in train, 10 in test
   - Model learns query-specific patterns → overfitting
2. **Violates IR Evaluation**: Ranking models should be evaluated at query-level
   - Metrics like NDCG, MRR are per-query metrics
   - Need to test on unseen queries, not unseen documents
3. **Phase A Design**: `xgboost_trainer.py` has `split_by_query_group()` placeholder
   - Intentionally designed for query-aware splitting

**Approved Alternative**:
- **Query Group Split**: Group by `query_id`, then split
  - Train queries: 80% of unique queries
  - Test queries: 20% of unique queries
  - All results for a query stay in same set

**When This Might Be Reconsidered**:
- Never (this is fundamental to IR evaluation)

**Related Decisions**:
- Issue #6 in `REVIEW_DECISIONS.md` (Query Group Split)
- Section 7 of `PHASE_A_DESIGN_PRINCIPLES.md` (Testing Strategy)

---

### ❌ DO NOT: Skip Shadow Mode and Deploy XGBoost Directly to Production

**Rejected Alternative**: Phase A → Phase C (skip Phase B shadow mode validation)

**Why It Seems Appealing**:
- Faster deployment: Save 2-3 weeks of data collection
- Start seeing cost savings sooner
- Simpler workflow

**Why We Rejected It**:
1. **Safety**: No validation of XGBoost predictions before affecting users
   - What if XGBoost systematically ranks irrelevant results higher?
   - What if confidence scores are miscalibrated?
2. **Baseline Comparison**: Need to compare XGBoost vs LLM with same queries
   - Shadow mode: Both run on same queries → direct comparison
   - Direct deployment: No baseline (can't measure improvement)
3. **User Trust**: Bad recommendations hurt user trust
   - Better to be slow and accurate than fast and wrong
   - Shadow mode = safety net

**When This Might Be Reconsidered**:
- If Phase A testing with mock data shows 100% agreement with LLM
- If we have offline evaluation dataset with ground truth labels
- MUST have explicit user approval before skipping shadow mode

**Related Decisions**:
- Section 8 of `PHASE_A_DESIGN_PRINCIPLES.md` (Shadow Mode Design)
- Design Principle: "Accuracy > Speed > Cost"

---

## 6. Performance Optimization Constraints

### ❌ DO NOT: Add Thread-Safe Locking to Global Model Cache (Phase A)

**Rejected Alternative**: Use `threading.Lock()` for `_MODEL_CACHE` access

**Why It Seems Appealing**:
- Prevents race condition: Multiple threads loading model simultaneously
- Thread safety: Best practice for shared state
- Correctness: Avoid potential bugs

**Why We Rejected It**:
1. **Premature Optimization**: Risk is extremely low
   - Model loads once per process (at first request)
   - After first load, all threads hit cache (no lock contention)
   - Race condition window: < 500ms during startup
2. **Simplicity**: No lock = simpler code
   - Easier to understand
   - Fewer things to debug
3. **Impact of Race Condition**: Low
   - Worst case: Two threads load model → waste 500ms + 50MB memory
   - Model cache overwrites itself → no crash, just redundant load

**Deferred to Phase B**:
- If production logs show duplicate model loads
- If memory usage spikes (multiple cached models)
- Solution: Add `threading.Lock()` or use `functools.lru_cache`

**When This Might Be Reconsidered**:
- Phase B: If logs show frequent race conditions
- If we switch to multi-process server (need process-safe cache)

**Related Decisions**:
- Issue #7 in `REVIEW_DECISIONS.md` (Thread Safety)
- Section 5 of `PHASE_A_DESIGN_PRINCIPLES.md` (Global Model Cache)

---

### ❌ DO NOT: Implement Confidence-Based Cascading in Phase A

**Rejected Alternative**: Use `confidence_threshold` to fall back to LLM for low-confidence predictions

**Why It Seems Appealing**:
- Config already has `confidence_threshold: 0.8`
- Could improve accuracy: Trust XGBoost when confident, LLM when not
- Hybrid approach: Best of both worlds

**Why We Rejected It**:
1. **Phase A is Shadow Mode Only**: XGBoost doesn't affect ranking yet
   - No point implementing cascading if XGBoost is disabled
   - Can't validate if cascading helps without production data
2. **Confidence Calibration Unknown**: Need Phase B data to validate
   - Is `confidence > 0.8` actually correlated with accuracy?
   - Need to plot calibration curve (predicted confidence vs actual accuracy)
3. **Premature Complexity**: Add logic when we have evidence it helps

**Deferred to Phase C**:
- After shadow mode validation shows confidence is calibrated
- After we have evidence that cascading improves metrics (NDCG, CTR)

**When This Might Be Reconsidered**:
- Phase C: After validating confidence calibration
- Config prepared in advance (ready to enable when needed)

**Related Decisions**:
- Issue #8 in `REVIEW_DECISIONS.md` (confidence_threshold未使用)
- Section 4 of `PHASE_A_DESIGN_PRINCIPLES.md` (Confidence Threshold)

---

## 7. Feature Engineering Constraints

### ❌ DO NOT: Add Historical Features (CTR, Dwell Time) in Phase A

**Rejected Alternative**: Implement features 30-35 (historical user behavior) in Phase A

**Why It Seems Appealing**:
- Historical features are powerful (CTR, dwell time are strong signals)
- Complete feature set: 35 features instead of 29
- Review Agent identified this as missing

**Why We Rejected It**:
1. **No Historical Data Yet**: Phase A has empty analytics DB
   - No clicks, no dwell time, no historical interactions
   - Features would all be 0 (no value)
2. **Infrastructure Before Data**: Phase A is about building the pipeline
   - Get infrastructure working with 29 in-memory features first
   - Add historical features after we have data to populate them
3. **Latency Constraint**: Historical features need pre-computed cache
   - Can't query DB in real-time (Section 2 constraint)
   - Need to design caching strategy (Phase B work)

**Deferred to Phase B**:
- After 500+ queries collected (data exists)
- Design pre-computation batch job (daily aggregation)
- Implement cache for fast lookup (< 10ms)

**When This Might Be Reconsidered**:
- Phase B: After data collection complete
- Must implement as pre-computed cache, NOT real-time DB queries

**Related Decisions**:
- Issue #3 in `REVIEW_DECISIONS.md` (Historical Features缺失)
- `algo/REVIEW_TODO.txt` (expand 29 → 35 features in Phase B)

---

### ❌ DO NOT: Compute temporal_boost Separately in Phase A

**Rejected Alternative**: Track `temporal_boost` as separate variable in Qdrant

**Why It Seems Appealing**:
- Feature 18 would have real values instead of 0
- More complete feature set (28/29 valid instead of 27/29)
- Review Agent identified this as issue

**Why We Rejected It**:
1. **Qdrant Code Change Required**: Need to modify `point_scores` dict
   - Adds complexity to Qdrant implementation
   - Risk of breaking existing BM25/keyword boost logic
2. **Low Priority**: Feature 18 is 1 out of 29 (3% of features)
   - Acceptable to have it as 0 for Phase A mock data testing
   - Not worth delaying Phase A integration for 1 feature
3. **Will Be Fixed in Phase B**: Planned enhancement
   - Phase B: Modify `point_scores` to include `temporal_boost`
   - Low risk when done alongside other Phase B changes

**Deferred to Phase B**:
- Modify `retrieval_providers/qdrant.py:978-981`
- Add `'temporal_boost': recency_multiplier - 1.0` to `point_scores`

**When This Might Be Reconsidered**:
- Phase B: As planned
- Earlier: Only if Issue #1 execution reveals it's trivial to add

**Related Decisions**:
- Issue #1 Verification Results in `REVIEW_DECISIONS.md`
- Review Agent recommendation: "Option C → A"

---

## 8. When to Violate These Constraints

### Legitimate Reasons to Reconsider:

1. **Evidence-Based**: Have data showing the constraint is no longer valid
   - Example: "Shadow mode shows XGBoost has 99% agreement with LLM → skip shadow mode for Phase D"

2. **Requirements Changed**: User explicitly requests different approach
   - Example: "Cost exceeded $50/day → must optimize LLM calls"

3. **Technology Changed**: New tools/libraries solve original concern
   - Example: "New Qdrant version has built-in ML re-ranking → use instead of XGBoost"

4. **Phase Transition**: Constraint was phase-specific
   - Example: "Phase A placeholder (temporal_boost=0) → Phase B implementation"

### Process for Violating a Constraint:

1. **Document Why**: Add note to this file explaining why constraint was lifted
2. **Update Design Principles**: Modify `PHASE_A_DESIGN_PRINCIPLES.md` if architecture changes
3. **Ask User**: Get explicit approval before violating constraints
4. **Test Thoroughly**: Constraints exist for safety - removing them increases risk

---

## Document Maintenance

**Add new constraints when**:
- Review discussions identify "tempting but rejected" alternatives
- User asks "why don't we just..." and the answer is "we considered and rejected that"
- Future agent suggests something that violates design principles

**Update constraints when**:
- Phase transitions (Phase A → B → C) lift phase-specific constraints
- Evidence shows constraint is no longer necessary
- User explicitly approves violating a constraint

**Last Updated**: 2025-01-26 (Phase A Week 1 review complete)
**Next Review**: After Phase A Week 2 integration (update based on execution learnings)
