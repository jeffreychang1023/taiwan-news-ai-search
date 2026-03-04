# Review Discussion TODO - 討論順序

## 🔴 Critical/Blocking 問題 (必須討論並修復)

### 1. [CRITICAL] 3.1 - RankingResult Object 缺失
**嚴重性**: ❌ Blocking
**發現**: 現有 ranking.py 沒有統一的 RankingResult 結構
**影響**: XGBoost 需要的 retrieval scores (bm25_score, vector_score 等) 無法取得，導致 features 22-27 全部為 0
**後果**: 如果強行整合，XGBoost 模型完全失效

**Review Agent 建議**:
- 實現 RankingResult class
- 修改 qdrant.py 傳遞 retrieval scores
- 修改 ranking.py 使用 RankingResult

**討論重點**:
- [ ] RankingResult class 設計是否合理？
- [ ] 是否會破壞現有系統？
- [ ] 實作工作量評估

---

### 2. [CRITICAL] 3.2 - Analytics Schema 缺 xgboost_confidence
**嚴重性**: ❌ Missing Column
**發現**: `analytics_db.py` schema 只有 `xgboost_score`，缺少 `xgboost_confidence`
**影響**: 無法記錄 confidence scores，無法實現 cascading logic

**Review Agent 建議**:
- 修復 analytics_db.py schema
- 實現 update_xgboost_scores() 方法
- 支援 UPDATE operation (非只有 INSERT)

**討論重點**:
- [ ] 是否需要 UPDATE 還是只要 INSERT？
- [ ] Schema migration 策略？
- [ ] 對 PostgreSQL 和 SQLite 的影響？

---

### 3. [CRITICAL] 1.2 - 缺少 Historical Features (已討論)
**嚴重性**: ❌ High Priority
**發現**: 29 features 缺少最重要的 user behavior signals
**影響**: XGBoost 無法學習用戶偏好

**已記錄**: `algo/REVIEW_TODO.txt`

**討論重點**:
- [ ] 何時修復？(Review 完立即 or Phase C)
- [ ] 29 → 35 features 的影響範圍確認

---

## 🟡 High Priority 問題 (應該討論)

### 4. [HIGH] 2.2 - Feature Index 硬編碼風險
**嚴重性**: ❌ Maintenance Risk
**發現**: `features[:, 23]` 這種硬編碼 index，如果 feature 順序改變就會出錯
**影響**: 當我們加入 historical features (29→35) 時，所有 index 都要手動調整

**Review Agent 建議**:
- 使用 Feature Name Constants
- 例如：`FEATURE_IDX_LLM_SCORE = 23`

**討論重點**:
- [ ] 是否改用 named constants？
- [ ] 或是改用 dict/dataclass 儲存 features？
- [ ] 對效能的影響？

---

### 5. [HIGH] 2.1 - Edge Cases (Division by Zero)
**嚴重性**: ⚠️ Medium
**發現**: `score_percentile` 計算有除零風險
**影響**: 當 only 1 result 時會出錯

**Review Agent 建議**:
```python
# Current
score_percentile = (rank / (len(sorted_scores) - 1)) * 100

# Suggested
score_percentile = (rank / max(len(sorted_scores) - 1, 1)) * 100
```

**討論重點**:
- [ ] 修改方式是否合理？
- [ ] 其他 edge cases 是否也要一起修？

---

### 6. [HIGH] 2.3 - Query Group Split 未實現
**嚴重性**: ❌ Missing
**發現**: LambdaMART 和 XGBRanker 需要 query groups，但函數未實現
**影響**: Phase C2, C3 無法訓練

**Review Agent 建議**:
- 實現 `split_by_query_groups()` 函數

**討論重點**:
- [ ] Phase A 需要實現還是 Phase C 再做？
- [ ] 實現複雜度？

---

## 🟢 Medium Priority 問題 (建議討論)

### 7. [MEDIUM] 2.2 - Thread Safety (Global Cache)
**嚴重性**: ⚠️ Thread-safety Issue
**發現**: `_MODEL_CACHE` 沒有 lock，multi-threading 可能出錯

**Review Agent 建議**:
```python
import threading
_MODEL_CACHE_LOCK = threading.Lock()

# In load_model()
with _MODEL_CACHE_LOCK:
    if self.model_path in _MODEL_CACHE:
        ...
```

**討論重點**:
- [ ] 是否真的需要？（aiohttp 是 async 不是 multi-thread）
- [ ] 還是用 asyncio.Lock？

---

### 8. [MEDIUM] 3.3 - confidence_threshold 未使用
**嚴重性**: ❌ Not Implemented
**發現**: Config 有 `confidence_threshold: 0.8` 但 code 完全沒用
**影響**: Cascading logic 未實現

**Review Agent 建議**:
- 在 `rerank()` 中實現 cascading logic

**討論重點**:
- [ ] Phase A 需要實現還是 Phase C？
- [ ] 如何實現？(high confidence → skip LLM refinement?)

---

### 9. [MEDIUM] 1.2 - Magic Numbers (999999)
**嚴重性**: ⚠️ Minor Issue
**發現**: `recency_days = 999999` 硬編碼

**Review Agent 建議**:
```python
MISSING_RECENCY_DAYS = 999999
```

**討論重點**:
- [ ] 是否值得改？
- [ ] 其他 magic numbers？

---

### 10. [MEDIUM] 1.3 - Shadow Mode Metrics 不足
**嚴重性**: ⚠️ Needs Enhancement
**發現**: Shadow mode 只記錄 avg_score, avg_confidence
**缺少**: Top-10 overlap, position changes 等比較 metrics

**Review Agent 建議**:
- 添加更多 comparison metrics

**討論重點**:
- [ ] 哪些 metrics 真正有用？
- [ ] Phase A 實現還是 Phase B？

---

## 🔵 Low Priority 問題 (可選討論)

### 11. [LOW] 4.3 - Traffic Splitting 缺失
**發現**: 無法做 10% → 50% → 100% gradual rollout
**影響**: Phase C 部署策略受限
**時機**: Phase C 部署前實現即可

### 12. [LOW] 2.1 - Edge Case Warning Logs
**發現**: Edge cases 沒有 warning logs
**影響**: Debug 困難
**時機**: 可選改進

### 13. [LOW] 其他文檔改進
- Cascading 文檔不清
- Rollback 需說明重啟
- Config 註解可以更詳細

---

## 討論策略

### 建議順序
1. **先討論 Critical 問題 (1-3)** - 這些會影響整合
2. **再討論 High Priority (4-6)** - 影響 Week 2 實作
3. **最後討論 Medium/Low (7-13)** - 可選改進

### 每個問題討論流程
1. 我說明 Review Agent 的建議改法
2. 您評估是否合理
3. 決定：
   - ✅ 接受並執行
   - ⚠️ 修改後執行
   - ❌ 不執行 (說明原因)
   - ⏳ 延後到 Phase C

### 預估討論時間
- Critical 問題: 30-45 分鐘
- High Priority: 20-30 分鐘
- Medium/Low: 15-20 分鐘 (optional)

---

## 現在開始

**準備好討論第一個問題嗎？**

👉 **問題 1: [CRITICAL] 3.1 - RankingResult Object 缺失**

請告訴我 Review Agent 給的建議改法 code，我們來評估是否執行。
