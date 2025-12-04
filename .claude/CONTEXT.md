# NLWeb Project Context

## Current Status: Week 3-4 (XGBoost Infrastructure Phase)

### Current Focus
**Phase A: XGBoost Infrastructure** - Building ML ranking system (feature engineering, training pipeline, inference module)

### Recently Completed
- ✅ Track A: Analytics Infrastructure
- ✅ Track B: BM25 Implementation  
- ✅ Track C: MMR Implementation

---

## Current Work

### 🔄 Phase A: XGBoost Infrastructure (Week 3-4) - IN PROGRESS

**Goal**: Build complete ML ranking infrastructure before data collection.

**Status**: Configuration and documentation complete, implementing modules.

**Completed**:
- Documentation: `algo/XGBoost_implementation.md` (500+ lines)
- Configuration: `config/config_retrieval.yaml` (xgboost_params)
- Architecture: LLM → XGBoost → MMR pipeline

**Remaining Tasks**:
- Implement `training/feature_engineering.py`
- Implement `core/xgboost_ranker.py`
- Implement `training/xgboost_trainer.py`
- Integrate into `core/ranking.py`
- Write unit tests
- Create mock training data

**Key Decisions**: XGBoost uses LLM scores as features, 29 features from analytics schema, shadow mode for validation.

---

## Next Immediate Steps

### Week 3: Integration & LLM Optimization
- Test BM25 + MMR with diverse queries
- Slim down LLM ranking prompts (remove keyword/freshness scoring)
- Set up A/B testing infrastructure
- Gradual production rollout (10% → 100%)

### Week 4-6: Data Collection for XGBoost
- Monitor analytics data collection (target: 10,000+ queries)
- Prepare feature engineering (12-15 features)

See `.claude/NEXT_STEPS.md` for detailed roadmap.

---

## References

- Analytics Dashboard: https://taiwan-news-ai-search.onrender.com/analytics
- Neon Database: https://console.neon.tech
- Render Service: https://dashboard.render.com
- Implementation Plan: See `.claude/NEXT_STEPS.md` and `.claude/PROGRESS.md`
