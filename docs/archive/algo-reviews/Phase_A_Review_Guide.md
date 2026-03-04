# XGBoost Phase A - Review Guide

**目的**: 人機協作檢查 XGBoost ML ranking 基礎架構的完整性和正確性

**審查日期**: 2025-01-26

**當前狀態**: Week 1 核心模組完成（70%），Week 2 整合測試待完成

---

## Review 概覽

### 已完成項目 ✅

1. **文檔 (Documentation)**
   - `algo/XGBoost_implementation.md` (500+ lines)
   - `algo/Week4_ML_Enhancements.md` (updated)
   - `.claude/CLAUDE.md`, `CONTEXT.md`, `PROGRESS.md`, `NEXT_STEPS.md`

2. **配置 (Configuration)**
   - `config/config_retrieval.yaml` (xgboost_params section)
   - `code/python/core/config.py` (CONFIG.xgboost_params)
   - `code/python/requirements.txt` (ML dependencies)

3. **核心模組 (Core Modules)**
   - `training/feature_engineering.py` (448 lines) - 29 features extraction
   - `core/xgboost_ranker.py` (434 lines) - Inference + shadow mode
   - `training/xgboost_trainer.py` (403 lines) - 3 model trainers

### 待完成項目 ⏳

- `core/ranking.py` integration (XGBoost call before MMR)
- `testing/test_xgboost.py` (unit tests)
- `testing/mock_training_data.py` (test data generator)

---

## Part 1: 高層架構檢查 (High-Level Architecture Review)

### 問題 1.1: Pipeline 順序是否合理？

**當前設計**:
```
Retrieval (Qdrant) → LLM Ranking → XGBoost Re-ranking → MMR Diversity → Final 10 Results
```

**檢查點**:
- [ ] XGBoost 為何在 LLM **之後**？（答案: XGBoost 使用 LLM scores 作為 features）
- [ ] XGBoost 為何在 MMR **之前**？（答案: MMR 應該在最終 relevance ranking 上運作）
- [ ] 如果 XGBoost disabled，系統是否仍能運作？（答案: 是，會走 LLM → MMR path）

**需要 Agent 協助的問題**:
```
請檢查 algo/XGBoost_implementation.md 第 60-93 行的 pipeline 架構圖，
確認這個順序在以下情況下都合理：
1. Phase A (XGBoost disabled, shadow mode)
2. Phase C (XGBoost enabled, production mode)
3. XGBoost 載入失敗時的 graceful degradation
```

---

### 問題 1.2: 29 Features 是否完整？

**當前設計**:
- Query features: 6
- Document features: 8
- Retrieval features: 7
- Ranking features: 6
- MMR features: 2
- **Total: 29**

**檢查點**:
- [ ] 是否遺漏關鍵的 ranking signal？
- [ ] Feature 是否過度依賴特定資料來源？（應該是 template-based）
- [ ] LLM scores 是否正確納入為 features？（features 22-27）

**需要 Agent 協助的問題**:
```
請檢查 training/feature_engineering.py 中的 29 個 features：
1. 每個 feature 的定義是否清晰？
2. 是否有重複或高度相關的 features？
3. 是否遺漏了重要的 user behavior signals？
4. Feature 的 value range 是否合理？（例如 recency_days 用 999999 表示無日期）

重點檢查函數:
- extract_query_features() (line 26-81)
- extract_document_features() (line 86-153)
- extract_query_doc_features() (line 158-223)
- extract_ranking_features() (line 228-283)
- extract_mmr_features() (line 288-317)
```

---

### 問題 1.3: Shadow Mode 設計是否足夠？

**當前設計**:
- Phase A/B: `use_shadow_mode: true` (log predictions, don't change ranking)
- Phase C: `use_shadow_mode: false` (use XGBoost scores)

**檢查點**:
- [ ] Shadow mode 是否記錄足夠的 metadata？（avg_score, avg_confidence, num_results）
- [ ] Log level 是否適當？（用 logger.info 而非 print）
- [ ] 如何從 shadow mode 切換到 production？（config flag）

**需要 Agent 協助的問題**:
```
請檢查 core/xgboost_ranker.py 的 rerank() 方法 (line 270-337)：
1. Shadow mode 是否正確實作？（line 307-314）
2. Metadata 是否包含所有需要的驗證資訊？
3. 如果 shadow mode 發現問題，rollback 機制是否清楚？

參考 algo/XGBoost_implementation.md 的 "Rollback Procedures" 章節 (line 470-510)
```

---

## Part 2: 模組功能檢查 (Module Functionality Review)

### 問題 2.1: Feature Engineering 正確性

**測試結果**:
```
✓ 提取了 29 features
✓ 測試 query: "如何使用 XGBoost 進行排序？"
✓ All feature extraction functions passed
```

**檢查點**:
- [ ] 中文和英文 query 都能正確處理嗎？
- [ ] Missing data 處理是否合理？（例如無 author → has_author=0）
- [ ] Edge cases 是否考慮？（例如 query_length=0, all_llm_scores 為空）

**需要 Agent 協助的問題**:
```
請分析 training/feature_engineering.py 的 edge case handling：

Test cases:
1. Empty query (query_text = "")
2. No published_date (published_date = None)
3. All LLM scores are 0 (all_llm_scores = [0, 0, 0])
4. Only 1 result (percentile calculation)

檢查每個 extract_*_features() 函數是否有 defensive programming:
- Division by zero checks
- None value handling
- Empty list handling
```

---

### 問題 2.2: XGBoost Ranker 架構

**測試結果**:
```
✓ Ranker initialized: enabled=False, shadow_mode=True
✓ Feature extraction: (5, 29) shape ✓
✓ Metadata returned correctly
```

**檢查點**:
- [ ] Global model cache 設計是否正確？（`_MODEL_CACHE` dictionary）
- [ ] Model not found 時是否優雅處理？（disable XGBoost, log warning）
- [ ] Feature extraction 是否與 feature_engineering.py 一致？

**需要 Agent 協助的問題**:
```
請檢查 core/xgboost_ranker.py 的設計模式：

1. Global model cache (line 21):
   - Thread-safe 嗎？（多 query 同時執行）
   - Memory leak 風險？（cache 何時清除）

2. extract_features() (line 84-195):
   - 是否正確使用 getattr() 處理不同 object types？
   - Feature order 是否與 training 時一致？（重要！）

3. predict() placeholder (line 197-232):
   - Phase A dummy predictions 合理嗎？（用 LLM scores）
   - Phase C 的 TODO comments 清楚嗎？
```

---

### 問題 2.3: Training Pipeline 完整性

**測試結果**:
```
✓ Binary classifier placeholder
✓ Model metadata saving
✓ Command-line interface defined
```

**檢查點**:
- [ ] 三種模型的 hyperparameters 是否合理？（BINARY, LAMBDAMART, XGBRANKER）
- [ ] Train/test split 設計是否考慮？（test_size=0.2）
- [ ] Evaluation metrics 是否對應模型類型？（AUC for binary, NDCG for ranking）

**需要 Agent 協助的問題**:
```
請檢查 training/xgboost_trainer.py 的 hyperparameters (line 24-53)：

對於每種模型：
1. objective 是否正確？
   - binary:logistic vs rank:pairwise vs rank:ndcg
2. max_depth, learning_rate 是否合理？
   - 是否有 overfitting 風險？
3. eval_metric 是否匹配 objective？

參考 XGBoost documentation:
https://xgboost.readthedocs.io/en/stable/parameter.html
```

---

## Part 3: 整合考量檢查 (Integration Considerations)

### 問題 3.1: 與現有系統的兼容性

**需要整合的位置**:
- `core/ranking.py` (after LLM ranking, before MMR)

**檢查點**:
- [ ] Ranking result objects 有哪些 attributes？（title, description, url, llm_score, etc.）
- [ ] XGBoost 需要哪些 attributes？（全部 29 features 需要的）
- [ ] 如果某些 attributes 缺失，是否有 fallback？（getattr with default）

**需要 Agent 協助的問題**:
```
請幫我檢查 core/ranking.py 的 RankingResult object 定義：

1. 找出 ranking result 的 data structure (可能是 dict or class)
2. 列出所有可用的 attributes
3. 對比 xgboost_ranker.py extract_features() 需要的 attributes (line 107-125)
4. 確認是否有缺失或不匹配

如果找不到明確定義，請搜尋 "class.*Result" 或檢查 ranking.py 的 return statements
```

---

### 問題 3.2: Analytics Logging 整合

**當前狀態**:
- Analytics database 已有 `ranking_scores` table
- 需要 log `xgboost_score`, `xgboost_confidence` columns

**檢查點**:
- [ ] `ranking_scores` table 是否已有這兩個 columns？
- [ ] 如果沒有，需要 schema migration 嗎？
- [ ] Log timing 是否正確？（XGBoost 執行後立即 log）

**需要 Agent 協助的問題**:
```
請檢查 analytics schema:

1. 查看 .claude/CLAUDE.md 中的 "Analytics Database Schema" 部分
2. 確認 ranking_scores table 是否包含:
   - xgboost_score DOUBLE PRECISION
   - xgboost_confidence DOUBLE PRECISION
3. 如果缺失，建議 migration strategy

參考位置: .claude/CLAUDE.md line 151-155
```

---

### 問題 3.3: Configuration 管理

**當前配置**:
```yaml
xgboost_params:
  enabled: false
  model_path: "models/xgboost_ranker_v1_binary.json"
  confidence_threshold: 0.8
  feature_version: 2
  use_shadow_mode: true
```

**檢查點**:
- [ ] Phase A → Phase C 的 config 切換步驟是否清楚？
- [ ] `feature_version` 如何與 analytics schema 對應？
- [ ] `confidence_threshold` 的意義是什麼？（目前似乎未使用）

**需要 Agent 協助的問題**:
```
請檢查 configuration 的一致性：

1. config/config_retrieval.yaml 中的 xgboost_params
2. core/config.py 中的 default values (line 347-353)
3. core/xgboost_ranker.py 中的使用方式 (line 47-52)

確認：
- Default values 是否一致？
- confidence_threshold 是否在 ranker 中使用？（目前看起來沒有）
- feature_version 驗證邏輯在哪裡？
```

---

## Part 4: Phase C 準備度檢查 (Phase C Readiness)

### 問題 4.1: Data Collection 要求

**Phase C 觸發條件**:
- 500+ clicks → Phase C1 (Binary)
- 2,000+ clicks → Phase C2 (LambdaMART)
- 5,000+ clicks → Phase C3 (XGBRanker)

**檢查點**:
- [ ] Analytics system 是否正在收集所有需要的 features？
- [ ] Click data 品質如何？（CTR, dwell time）
- [ ] 如何監控 data volume？（dashboard or API）

**需要 Agent 協助的問題**:
```
請確認 data collection pipeline 完整性：

1. 檢查 .claude/CLAUDE.md "Analytics Database Schema" 章節
2. 確認 feature_vectors table 是否已建立
3. 確認 user_interactions table 是否正在收集 clicks
4. 找出 data volume monitoring 的方法（可能在 analytics_handler.py）

關鍵問題：
- 如果現在開始收集數據，何時能達到 500 clicks？
- 數據品質檢查機制在哪裡？（validate_feature_quality function）
```

---

### 問題 4.2: Training Data Pipeline

**當前狀態**:
- `populate_feature_vectors()` 是 placeholder (Phase A)
- `load_training_data()` 是 placeholder (Phase A)

**檢查點**:
- [ ] 從 4 張 analytics tables JOIN 的 SQL logic 是否設計好？
- [ ] Batch processing 策略是否考慮？（batch_size=100）
- [ ] Label generation 邏輯是否明確？（clicked, dwell_time, relevance_grade）

**需要 Agent 協助的問題**:
```
請設計 Phase C 的 SQL query structure：

Tables to JOIN:
- queries (query_id, query_text, timestamp)
- retrieved_documents (query_id, doc_url, bm25_score, vector_score)
- ranking_scores (query_id, doc_url, llm_final_score, ranking_position)
- user_interactions (query_id, doc_url, clicked, dwell_time_ms)

Output:
- 每個 query-document pair 的 29 features
- Label: clicked (0/1) for binary, relevance_grade (0-4) for ranking

請提供 pseudo-SQL 或建議 JOIN strategy
```

---

### 問題 4.3: Model Deployment Strategy

**Rollout Plan**:
1. Shadow mode (1-2 days)
2. 10% traffic (1-2 days)
3. 50% traffic (2-3 days)
4. 100% traffic

**檢查點**:
- [ ] Traffic splitting 機制在哪裡？（目前 code 中沒看到）
- [ ] A/B testing metrics 如何收集？（analytics dashboard）
- [ ] Rollback 是否能在 5 分鐘內完成？（只改 config）

**需要 Agent 協助的問題**:
```
請評估 deployment strategy 的可行性：

1. 檢查是否有 traffic splitting 基礎設施
   - Feature flags?
   - User sampling mechanism?
2. Rollback procedure 是否完整？
   - algo/XGBoost_implementation.md line 470-510
   - 是否遺漏步驟？
3. Monitoring dashboard 是否足夠？
   - 需要哪些 real-time metrics？
   - 現有 analytics dashboard 是否支援？
```

---

## Part 5: 風險與改進建議 (Risks & Improvements)

### 問題 5.1: 已知風險評估

**高風險項目** (from XGBoost_implementation.md):
1. Cache 不同步 (Generate mode)
2. MMR 破壞 XGBoost 排序

**檢查點**:
- [ ] Cache issue 的緩解策略是否清楚？
- [ ] MMR 在 XGBoost 之後執行是否真的合理？

**需要 Agent 協助的問題**:
```
請深入分析這兩個高風險項目：

Risk 1: Cache 不同步
- Generate mode 使用 cached results 時會發生什麼？
- XGBoost 是否會重新執行？
- 如果不會，如何修復？（提示：可能在 ranking.py 的 cache logic）

Risk 2: MMR 破壞排序
- MMR 的 diversity re-ranking 是否會打亂 XGBoost 的優化？
- 如果會，有什麼替代方案？
  a) XGBoost features 包含 diversity signal？
  b) MMR 使用 constrained optimization？
- NDCG 評估時如何處理這個問題？
```

---

### 問題 5.2: 效能考量

**Target**:
- Inference latency < 100ms (P95)
- No degradation in total query time

**檢查點**:
- [ ] Feature extraction 是否有瓶頸？（29 features from 50 results）
- [ ] Model loading 延遲是否可接受？（global cache）
- [ ] 如何 profile performance？

**需要 Agent 協助的問題**:
```
請估算 worst-case latency：

Scenario: 50 results, 29 features per result
1. Feature extraction time (Python loops)
2. XGBoost inference time (50 docs)
3. Re-sorting time (50 docs)

Assumptions:
- No I/O (model already loaded)
- Pure computation
- Single-threaded

是否有 optimization opportunities？
- Vectorization?
- Caching intermediate results?
- Parallel processing?
```

---

### 問題 5.3: 改進建議

**需要 Agent 腦力激盪的問題**:

```
基於當前實作，請提供改進建議：

1. Feature Engineering:
   - 是否有更好的 feature normalization 策略？
   - 是否應該加入 user history features？（需要 user_id tracking）
   - Temporal features 是否足夠？（目前只有 recency_days）

2. Model Architecture:
   - 是否應該考慮 ensemble models？（XGBoost + LLM ensemble）
   - Confidence calculation 方法是否合理？（目前很簡單）
   - 是否需要 model versioning beyond file names？

3. Training Pipeline:
   - Cross-validation strategy?
   - Hyperparameter tuning automation?
   - Model drift detection?

4. Production Monitoring:
   - 需要哪些 real-time alerts？
   - Feature drift detection?
   - Model performance degradation detection?

請針對每個類別提供 2-3 個具體建議
```

---

## Review Checklist Summary

### 必須回答的問題 (Must Answer)

- [ ] 1.1 Pipeline 順序合理性
- [ ] 1.2 29 Features 完整性
- [ ] 1.3 Shadow Mode 設計
- [ ] 2.1 Feature Engineering 正確性
- [ ] 2.2 XGBoost Ranker 架構
- [ ] 3.1 與現有系統兼容性
- [ ] 3.2 Analytics Logging 整合

### 應該回答的問題 (Should Answer)

- [ ] 2.3 Training Pipeline 完整性
- [ ] 3.3 Configuration 管理
- [ ] 4.1 Data Collection 準備度
- [ ] 5.1 已知風險評估

### 可選回答的問題 (Nice to Have)

- [ ] 4.2 Training Data Pipeline 設計
- [ ] 4.3 Model Deployment Strategy
- [ ] 5.2 效能估算
- [ ] 5.3 改進建議

---

## 使用建議

**For Human Reviewer**:
1. 先閱讀 Part 1（高層架構）理解整體設計
2. 把感興趣的問題複製給 Agent
3. Agent 回答後，追問細節或提出疑慮

**For Claude Agent**:
1. 優先處理 "必須回答" 的問題
2. 提供具體的 line numbers 和 code snippets
3. 如果發現問題，提供 fix 建議（但不要直接修改 code）

**Review Output Format**:
建議 Agent 用以下格式回答：
```
## 問題 X.X 回答

### 檢查結果
- ✓/✗ Checkpoint 1
- ✓/✗ Checkpoint 2

### 發現的問題
1. [Severity: High/Medium/Low] 問題描述
2. ...

### 建議修改
1. File: xxx, Line: xxx
   Current: ...
   Suggest: ...

### 額外觀察
...
```

---

## 附錄: 檔案清單

**Documentation**:
- `algo/XGBoost_implementation.md` (500+ lines)
- `algo/Week4_ML_Enhancements.md`
- `.claude/CLAUDE.md` (ML section)
- `.claude/CONTEXT.md` (Phase A section)

**Code**:
- `training/feature_engineering.py` (448 lines)
- `core/xgboost_ranker.py` (434 lines)
- `training/xgboost_trainer.py` (403 lines)

**Configuration**:
- `config/config_retrieval.yaml` (xgboost_params)
- `core/config.py` (CONFIG.xgboost_params)

**Not Yet Created**:
- `core/ranking.py` integration (TODO)
- `testing/test_xgboost.py` (TODO)
- `testing/mock_training_data.py` (TODO)

---

**Review 完成後的下一步**:

1. **如果發現重大問題** → 修復後再繼續 Week 2
2. **如果只有小問題** → 記錄下來，繼續 Week 2，之後一起修復
3. **如果沒有問題** → 直接進行 Week 2 整合與測試

**預估 Review 時間**: 1-2 小時（與 Agent 協作）
