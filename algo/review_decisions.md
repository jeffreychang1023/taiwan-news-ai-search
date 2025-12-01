# Phase A Review Decisions & Implementation Specs
**Status**: Implementation in Progress
**Last Updated**: 2025-01-28

This document records the **final approved specifications** for implementation. Coding Agents should follow these specs exactly.

---

## ✅ APPROVED SPECS (Ready for Implementation)

### Issue #1: RankingResult Object & Qdrant Return Format
**Priority**: 🔴 Critical | **Status**: Approved

*   **Decision**: Standardize data flow using a Dataclass and replace Tuple returns with Dicts.
*   **Component 1: `RankingResult` Class** (`core/ranking.py`)
    *   **Type**: `@dataclass`
    *   **Fields**:
        *   `url`, `title`, `description`, `site` (Str)
        *   `schema_object` (Dict)
        *   `retrieval_scores`: `vector_score`, `bm25_score`, `keyword_boost`, `final_retrieval_score` (Float)
        *   `temporal_boost` (Float, **Default=0.0** for Phase A)
        *   `llm_score` (Float), `llm_snippet` (Str)
        *   `xgboost_score`, `xgboost_confidence` (Optional[Float])
        *   `mmr_score` (Optional[Float]), `detected_intent` (Optional[Str])
        *   `vector` (Optional[List[Float]] - for MMR)

*   **Component 2: Qdrant Return Format** (`retrieval_providers/qdrant.py`)
    *   **Constraint**: Change return type from `List[Tuple]` to `List[Dict]`.
    *   **Structure**:
        ```python
        {
            'url': ...,
            'title': ...,
            'site': ...,
            'schema_json': ...,
            'retrieval_scores': {
                'vector_score': ...,
                'bm25_score': ...,
                'keyword_boost': ...,
                'temporal_boost': 0.0, # Placeholder
                'final_retrieval_score': ...
            },
            'vector': ... # If include_vectors=True
        }
        ```

*   **Component 3: Integration Logic** (`core/ranking.py`)
    *   **Action**: Update `rank_results()` to accept Dict format.
    *   **Action**: Use a factory function `create_ranking_result()` to convert Dicts to `RankingResult` objects immediately after retrieval.
    *   **Action**: Attach MMR scores to `RankingResult` objects after diversity reranking.

---

### Issue #2: Analytics Schema & Logging Strategy
**Priority**: 🔴 Critical | **Status**: Approved

*   **Problem**: Missing `xgboost_confidence` in DB schema; need to decide on INSERT vs UPDATE for logging XGBoost scores.
*   **Decision**: 
    1.  Adopt **Option C (Multiple INSERTs)** to align with existing MMR logging pattern.
    2.  Fix schema migration logic in `query_logger.py` to include `xgboost_confidence`.
    3.  Implement a dedicated `log_xgboost_scores()` method.
    4.  Defer UPDATE mechanism to Phase C.

*   **Spec 1: Schema Migration** (`core/query_logger.py`)
    *   **Action**: Update migration logic (around line 168 & 199) to add `xgboost_confidence` column for existing v1 databases.
    *   **SQL (PostgreSQL)**:
        ```sql
        ALTER TABLE ranking_scores 
        ADD COLUMN IF NOT EXISTS xgboost_confidence DOUBLE PRECISION;
        ```
    *   **SQL (SQLite)**:
        ```sql
        -- Add to the list of columns to check/add
        ("ranking_scores", "xgboost_confidence", "REAL")
        ```

*   **Spec 2: Logging Method** (`core/query_logger.py`)
    *   **Method Name**: `log_xgboost_scores`
    *   **Signature**:
        ```python
        def log_xgboost_scores(
            self,
            query_id: str,
            doc_url: str,
            xgboost_score: float,
            xgboost_confidence: float,
            ranking_position: int
        ) -> None:
        ```
    *   **Implementation Logic**:
        *   Construct a data dictionary.
        *   Set `ranking_method="xgboost_shadow"` (for Phase A).
        *   Set `xgboost_score` and `xgboost_confidence` with actual values.
        *   Set `llm_final_score`, `mmr_diversity_score` to `0` (placeholder).
        *   Put into `self.log_queue` (INSERT operation).

*   **Spec 3: Legacy Cleanup** (`core/analytics_db.py`)
    *   **Action**: Add `xgboost_confidence` to the unused schema definitions for consistency (low priority).

*   **Spec 4: Integration Point** (`core/xgboost_ranker.py`)
    *   **Action**: Call `query_logger.log_xgboost_scores()` inside the `rerank()` method when `shadow_mode=True`.
---
### **Issue #3: Historical Features (29 → 35)**

**Priority**: 🟡 High | **Status**: ✅ Approved (Phased Implementation)

**Decision**:

- **Phase A**: 保持 29 features，繼續收集 **`user_interactions`** 資料
- **Phase B**: 實作 **`url_stats`** aggregation table + background job
- **Phase C**: 整合 historical features 到 training & inference (29 → 35)

**Rationale**:

1. **`user_interactions`** 資料已在收集中 ✅
2. 使用 **pre-computed aggregation table** 可以符合 Constitution 的「in-memory only」限制
3. 分階段實作降低風險，不影響 Phase A 的基礎建設

**Implementation Specs**:

**Phase B (Week 5-7)**:

- 新增 **`url_stats`** table (schema 見上方)
- 實作 background job: **`jobs/update_url_stats.py`**
- 每日更新一次（2 AM cron job）

**Phase C (Week 7-8)**:

- Training: **`feature_engineering.py`** 加入 **`extract_historical_features()`**
- Inference: **`xgboost_ranker.py`** startup 時 load **`url_stats`** 到 memory
- Config: **`feature_version: 2 → 3`**
- Features: 6 個新 features (ctr_7d, ctr_30d, avg_dwell_time_ms, times_shown, avg_position_when_clicked, days_since_last_interaction)

**6 New Features** (Phase C):

1. **`url_ctr_7d`** - 7 天點擊率
2. **`url_ctr_30d`** - 30 天點擊率
3. **`url_avg_dwell_time_ms`** - 平均停留時間
4. **`url_times_shown_30d`** - 30 天曝光次數
5. **`url_avg_position_when_clicked`** - 點擊時的平均位置
6. **`days_since_last_interaction`** - 距離上次互動的天數

**Cold Start Strategy**:

- 新 URL 無歷史資料 → 使用 default values (ctr=0.05, dwell=0)
- 5 次曝光後開始使用實際統計

---
### **Issue #4: Feature Index 硬編碼風險**

**Priority**: 🟡 High | **Status**: ✅ Approved (Named Constants)

**Decision**:

- 使用 **Named Constants** 定義 feature indices
- **不使用** dict/dataclass（效能考量）
- Constants 定義在 **`training/feature_engineering.py`**
- **`xgboost_ranker.py`** import constants 使用

**Rationale**:

1. 維護性：Phase C 加入 historical features 時自動調整
2. 可讀性：**`FEATURE_IDX_LLM_FINAL_SCORE`** 比 **`23`** 清楚
3. 零效能影響：編譯時常數，無 runtime 開銷
4. 符合 Constitution：不影響 latency < 20ms 要求

**Implementation Spec**:

**File**: **`training/feature_engineering.py`**

- 新增 29 個 feature index constants（檔案開頭）
- 格式：**`FEATURE_IDX_{NAME} = {index}`**
- 分組註解：Query (0-5), Document (6-13), Query-Doc (14-20), Ranking (21-26), MMR (27-28)
- 新增 **`TOTAL_FEATURES_PHASE_A = 29`** constant

**File**: **`core/xgboost_ranker.py`**

- Import constants: **`from training.feature_engineering import FEATURE_IDX_LLM_FINAL_SCORE, TOTAL_FEATURES_PHASE_A`**
- 修改 line 256: **`features[:, 23]`** → **`features[:, FEATURE_IDX_LLM_FINAL_SCORE]`**
- 新增 validation: **`assert features.shape[1] == TOTAL_FEATURES_PHASE_A`**

**Phase C Extension**:

- 當加入 historical features 時，只需更新 constants 檔案
- 所有使用 constants 的程式碼自動正確
---
### **Issue #5: Edge Cases (Division by Zero)**

**Priority**: 🟡 High | **Status**: ❌ Rejected (Not a Real Issue)

**Decision**:

- **不修改** 現有程式碼
- 所有除法操作都有適當的保護
- Review Agent 建議的修改沒有實際必要性

**Rationale**:

1. **現有程式碼已經安全**：
    - **`score_percentile`** 計算有 **`if len(all_llm_scores) > 1`** 保護
    - **`relative_score_to_top`** 有 **`if max(all_llm_scores) > 0`** 保護
    - **`keyword_overlap_ratio`** 有 **`if len(query_keywords) > 0`** 保護
2. **Review Agent 建議語意不清**：
    - **`max(len(sorted_scores) - 1, 1)`** 會讓單一結果的 percentile 變成 **`(0/1)*100 = 0`**
    - 現有的 fallback value **`50.0`** 更合理（代表中位數）
3. **可讀性優先**：
    - 明確的 if-else 比隱式的 max() 更容易維護

**Identified Minor Issue** (Deferred to Phase C):

- **`sorted_scores.index()`** 在重複分數時不準確
- 影響很小，不是 Phase A 重點
- 可在 Phase C 優化時一併處理
---
### **Issue #6: Query Group Split 未實現**

**Priority**: 🟡 High | **Status**: ⏳ Deferred to Phase C

**Decision**:

- **不在 Phase A 實作** query group splitting logic
- **保留現有 interface**（function signature 和 error checking）
- **Phase C 實作時**從 analytics DB 計算 query groups

**Rationale**:

1. **Phase A 沒有實際訓練**：Shadow mode 只做 inference，不需要 training data
2. **Constitution 針對 Phase C**："split training data" 的前提是有真實資料
3. **Interface 已完整**：Function signatures 已預留 **`query_groups`** 參數
4. **Error handling 已存在**：主程式會檢查 **`query_groups is None`** 並報錯

**Phase C Implementation Requirements**:

**High-level Logic**:

1. Query analytics DB，JOIN 4 張表（queries, retrieved_documents, ranking_scores, user_interactions）
2. Extract 29 features for each (query_id, doc_url) pair
3. **Critical**: Sort all rows by **`query_id`**（XGBoost 要求同 query 文件連續）
4. Build query_groups list: **`[n_docs_query1, n_docs_query2, ...]`**
5. Train/Test split **by query**（不能 random shuffle）

**Key Constraints**:

- Query group format: **`[10, 12, 8]`** = "query 1 有 10 docs, query 2 有 12 docs, query 3 有 8 docs"
- Documents from same query MUST be consecutive in feature matrix
- Split validation sets by query, not by individual documents

**Optional Phase A Enhancement**:

- Add detailed docstring to **`load_training_data()`** explaining Phase C implementation plan
---
### **Issue #7: Thread Safety (Global Cache)**

**Priority**: 🟢 Medium | **Status**: ⏳ Deferred to Phase B

**Decision**:

- **不在 Phase A 加 lock**
- 符合 Constitution 規定（"Phase B will address thread locking if needed"）
- 目前架構不需要 threading lock

**Rationale**:

1. **Constitution 明確延後**：
    - §3: "Phase B will address thread locking if needed"
2. **架構是 async，不是 multi-threading**：
    - aiohttp 使用 single-threaded event loop
    - Cooperative multitasking (async/await)
    - 不是 preemptive multi-threading
3. **錯誤的 lock 類型**：
    - Review Agent 建議 **`threading.Lock()`**
    - 但 aiohttp 環境應該用 **`asyncio.Lock()`**（如果真的需要）
4. **實際風險很低**：
    - Model loading 發生在 startup（sequential）
    - 後續 requests 都從 cache 讀取
    - Python dict read 是 atomic（safe for concurrent reads）
5. **最壞情況可接受**：
    - 即使 race condition，只是重複 load model
    - 不會造成 crash 或 data corruption

**Phase B Consideration**:

- 如果發現需要 lock，使用 **`asyncio.Lock()`**
- 或改用 eager loading（app startup 時 preload model）
- 目前保持簡單
---
### **Issue #8: confidence_threshold 未使用**

**Priority**: 🟢 Medium | **Status**: ⏳ Deferred to Phase C

**Decision**:

- **不在 Phase A 實作** cascading logic
- 保留 config 參數（為 Phase C 預留）
- Shadow mode 下 cascading 不適用

**Rationale**:

1. **Constitution 禁止影響排序**：
    - §3: "Shadow mode logging only"
    - Cascading 的目的是讓 XGBoost 取代 LLM → 違反 shadow mode 原則
2. **Cascading 是 Production 優化策略**：
    - 目標：High confidence queries 只用 XGBoost（省 80% 成本）
    - 前提：模型已驗證、準確度足夠
    - Phase A 目標是收集資料，不是優化成本
3. **Shadow mode 需要完整對照資料**：
    - 所有 queries 都要同時記錄 LLM scores 和 XGBoost predictions
    - 如果用 cascading，部分 queries 沒有 LLM scores → 無法驗證準確度
    - 完整資料才能評估 XGBoost 是否可信
4. **Config 保留合理**：
    - 為 Phase C 預留 interface
    - 讓架構設計完整
    - 文檔化未來 feature

**Phase C Implementation Plan**:

**Cascading Decision Logic**:

```
avg_confidence = mean(xgboost_confidences)

if avg_confidence >= confidence_threshold:
    Use XGBoost ranking (save cost/latency)
else:
    Fallback to LLM ranking (ensure quality)

```

**Confidence Calculation Options**:

- Prediction variance（variance 低 = 信心高）
- Prediction margin（top-1 與 top-2 差距大 = 信心高）
- Model calibration scores

**Threshold Tuning**:

- Initial: 0.8（保守策略）
- Monitor: 準確度下降 < 5%
- Goal: 降到 0.75（更多 queries 用 XGBoost）

**Analytics Tracking**:

- Log cascading decisions (xgboost vs llm_fallback)
- Log avg_confidence per query
- Monitor accuracy by confidence bucket
---
### **Issue #9: Magic Numbers (999999)**

**Priority**: 🟢 Medium | **Status**: ✅ Approved (Optional, Low Priority)

**Decision**:

- **可選改進**：將 **`999999`** 改為 **`MISSING_RECENCY_DAYS`** constant
- 其他 magic numbers 保持原樣（**`50.0`**, **`1.0`**）
- 非 critical，可延後或跳過

**Rationale**:

1. **輕微改善可讀性**：
    - **`MISSING_RECENCY_DAYS`** 比 **`999999`** 更 self-documenting
    - 統一 2 處使用（invalid date, no date）
2. **不是 critical issue**：
    - Code style 問題，不影響功能
    - Phase A 重點是基礎建設，不是 code polish
3. **其他 magic numbers 合理**：
    - **`50.0`**：Percentile fallback（中位數），語意清楚
    - **`1.0`**：Relative score fallback（100%），語意清楚
    - 只出現 1 次，改成 constant 意義不大
4. **實作成本低**：
    - 加 1 行 constant
    - 替換 2 處使用

**Implementation (if executed)**:

**File**: **`training/feature_engineering.py`**

**Change**:

- Add constant at top: **`MISSING_RECENCY_DAYS = 999999`**
- Replace Line 126: **`recency_days = MISSING_RECENCY_DAYS`**
- Replace Line 128: **`recency_days = MISSING_RECENCY_DAYS`**

**Not Changing** (explicit decision):

- **`50.0`**：Single-result percentile fallback（語意清楚）
- **`1.0`**：Relative score fallback（語意清楚）
- **`100`**：Unit conversion for percentile（不是 magic number）
---
### **Issue #10: Shadow Mode Metrics 不足**

**Priority**: 🟢 Medium | **Status**: ⏳ Deferred to Phase B

**Decision**:

- **Phase A**：保持現有簡單 metrics（avg_score, avg_confidence）
- **Phase B**：加入 comparison metrics（top-10 overlap, rank correlation, position changes）
- **Phase C**：用這些 metrics 做上線決策和監控

**Rationale**:

1. **Phase A 的 XGBoost 是 dummy model**：
    - 目前回傳 normalized LLM scores（placeholder）
    - Comparison metrics 沒有意義（比較自己和自己）
2. **Phase B 才有真實預測**：
    - Binary Classifier 訓練完成後，predictions 才有意義
    - 可以開始分析 XGBoost vs LLM 的差異
3. **現有 metrics 足夠 Phase A**：
    - **`avg_score`**, **`avg_confidence`** 驗證「系統有在跑」
    - Logging 正常、沒有 crash 就是 Phase A 的成功
4. **避免過早優化**：
    - Comparison metrics 增加計算複雜度
    - Phase A 沒有實際用途

**Phase B Implementation Plan**:

**Comparison Metrics to Add**:

1. **top10_overlap**：XGBoost top-10 vs LLM top-10 重疊率（0-1）
2. **rank_correlation**：Kendall's Tau 或 Spearman's rho（-1 to 1）
3. **avg_position_change**：平均位置變化（documents 在兩個 ranking 中的位置差）
4. **max_position_change**：最大位置變化（找出最不穩定的結果）
5. **score_std**：XGBoost scores 的標準差（分數分佈）
6. **confidence_std**：Confidence scores 的標準差

**Implementation Location**:

- File: **`core/xgboost_ranker.py`**
- Method: **`rerank()`** 內計算 comparison metrics
- Update **`metadata`** dict with new metrics

**Analytics Schema** (Optional):

- 新增 **`shadow_mode_metrics`** table（推薦）
- 或擴充 **`queries`** table（簡單但混雜）

**Usage in Phase C**:

- **Go/No-Go Decision**: top10_overlap > 0.7 且 CTR 不下降 → 上線
- **Monitoring**: rank_correlation 下降 → XGBoost 可能 drift
- **Debug**: max_position_change 分析哪些 query 最不穩定
---
### **Issue #11: Traffic Splitting 缺失**

**Priority**: 🔵 Low | **Status**: ⏳ Deferred to Phase C (Week 7)

**Decision**:

- **不在 Phase A/B 實作**
- Phase C Week 7 實作（部署前準備）
- 推薦 **Hash-based Bucketing** 方案

**Rationale**:

1. **Phase A/B 不需要**：
    - 100% shadow mode，沒有流量切換需求
    - Traffic splitting 是 production deployment feature
2. **實作時機明確**：
    - Phase C Week 7 開始部署準備
    - 有充足時間設計、測試、監控
    - 不影響 Phase A/B 的 ML pipeline 建設
3. **避免過早優化**：
    - Phase A 重點是基礎建設，不是部署策略
    - 保持程式碼簡單

**Phase C Implementation Plan** (Week 7):

**Architecture**: Hash-based Bucketing with Config Control

**Config Addition**:

```yaml
xgboost_params:
  traffic_percentage: 10  # 0-100
  bucketing_strategy: "query_id"  # Deterministic bucketing

```

**Bucketing Logic**:

- Deterministic hash-based: **`md5(query_id) % 100 < traffic_percentage`**
- 同一個 query 總是走同一條路徑（xgboost 或 control）
- Stateless，不需外部 feature flag service

**Gradual Rollout SOP**:

- Day 1-2: 10% traffic → 監控 error rate, latency, CTR
- Day 3-4: 50% traffic → 確認 scaling
- Day 5+: 100% traffic → Full rollout

**Rollback Strategy**:

- Config change: **`traffic_percentage: 0`**
- Hot reload（不需重啟）或快速重啟（< 30s）
- 自動 rollback triggers: error rate > 5%, p99 latency > 10s

**Analytics**:

- 新增 **`traffic_bucket`** 欄位（'xgboost' vs 'control'）
- A/B test 分析：CTR, latency, error rate by bucket
---
### **Issue #12: Edge Case Warning Logs**

**Priority**: 🔵 Low | **Status**: ✅ Approved (Optional)

**Decision**:

- **可選改進**，非必要
- 如果實作，只加 warning logs 給**異常** edge cases
- 不 log **預期內**的 edge cases（避免噪音）

**Rationale**:

1. 有助於 debug 和監控
2. 實作成本低（只加 logger.warning）
3. 但不是 Phase A 重點
4. 可延後到遇到問題時再加

**Should Log** (異常情況):

- Feature extraction 失敗（exception）
- 所有 LLM scores = 0（可能系統問題）
- Model loading 失敗

**Should NOT Log** (正常情況):

- 只有 1 個結果（使用者 query 具體）
- 沒有發布日期（很多網頁正常沒日期）
- Query keywords 為空（短 query 正常）

---

### **Issue #13: 其他文檔改進**

**Priority**: 🔵 Low | **Status**: ✅ Approved (Documentation)

**Decision**:

- **同意改進文檔**
- Phase A 結束時統一更新
- 不是 blocking issue

**Documentation Improvements**:

1. **XGBoost_implementation.md**:
    - 補充 cascading logic 流程圖和範例
    - 說明 confidence 計算方法（Phase C 待定）
2. **Rollback SOP** (CLAUDE.md 或新增 DEPLOYMENT.md):
    - Quick rollback 步驟（改 config + 重啟）
    - Decision criteria（error rate, latency, CTR）
    - Emergency procedures
3. **Config 詳細註解** (config_retrieval.yaml):
    - 每個參數的用途和影響
    - Phase A/B/C 的不同設定值
    - 範例值和建議值

**Timing**:

- 不需要在 Phase A 實作前完成
- Code review 時一起改
- 或 Phase A 結束時統一更新

---

## **🎉 所有 13 個 Issues 討論完畢！**

讓我總結一下決策：

**✅ APPROVED (需實作)**:

- Issue #1: RankingResult Object ✅ (已討論)
- Issue #2: Analytics Schema ✅ (已討論)
- Issue #4: Feature Index Constants ✅
- Issue #9: Magic Numbers → Constant ✅ (optional)
- Issue #10: Shadow Mode Metrics ⏳ (Phase B)
- Issue #12: Edge Case Logs ✅ (optional)
- Issue #13: Documentation ✅

**❌ REJECTED**:

- Issue #5: Division by Zero（false positive，程式碼已安全）

**⏳ DEFERRED**:

- Issue #3: Historical Features → Phase B/C
- Issue #6: Query Group Split → Phase C
- Issue #7: Thread Safety → Phase B
- Issue #8: Confidence Threshold → Phase C
- Issue #11: Traffic Splitting → Phase C

## 🗑️ REJECTED / DEFERRED (Do Not Implement)
*   **Tuple Modification**: Rejected. Do not modify the existing Tuple structure; switch to Dict instead.
*   **Real-time DB Query**: Rejected. No querying Analytics DB during ranking.
*   **Traffic Splitting**: Deferred to Phase C.