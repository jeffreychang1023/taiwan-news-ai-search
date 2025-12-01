# Phase A Constitution: XGBoost Infrastructure
**Status**: Active | **Enforced By**: Review Agent

This document outlines the **non-negotiable** architectural constraints and design principles for Phase A. All code changes must strictly adhere to these rules.

## 1. Pipeline Architecture 🏗️
*   **❌ DO NOT** change the execution order.
    *   **Mandatory Order**: Retrieval (Qdrant) → LLM Ranking → XGBoost (Shadow Mode) → MMR.
    *   *Reason*: XGBoost depends on LLM scores (features 22-27); MMR depends on final relevance scores.
*   **❌ DO NOT** run XGBoost in parallel with LLM.
*   **❌ DO NOT** place XGBoost config in `config_llm.yaml`. Use `config_retrieval.yaml`.

## 2. Data Flow & Latency ⚡
*   **❌ DO NOT** query the database during the ranking loop.
    *   **Constraint**: All features must be extracted from **in-memory** objects (latency < 20ms).
*   **❌ DO NOT** implement asynchronous feature extraction in Phase A.
*   **✅ MUST** use **Dict** or **Dataclass** for internal data passing.
    *   *Constraint*: **No Tuples** (fragile) or NamedTuples (immutable).
*   **❌ DO NOT** add historical features (CTR, Dwell Time) in Phase A.
    *   *Action*: Defer to Phase B.

## 3. Implementation Constraints 🛠️
*   **✅ MUST** implement **Shadow Mode** by default.
    *   Logic: Log XGBoost scores/confidence, but return original LLM ranking results to the user.
*   **✅ MUST** use Global Model Cache for the XGBoost model (load once per process).
    *   *Note*: Phase B will address thread locking if needed.
*   **✅ MUST** split training data by `query_id` (Query Group Split), NOT random shuffle.
*   **❌ DO NOT** enable XGBoost as the primary ranker in `config` defaults (keep `enabled: false` or `shadow_mode: true`).

## 4. Phase A Scope Boundaries 🚧
*   **Feature Count**: Strictly **29 features**. (No historical features).
*   **Integration**: Infrastructure setup & Shadow mode logging only.
*   **Optimization**: Accuracy > Speed > Cost. Do not optimize for cost if it sacrifices feature completeness.