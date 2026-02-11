# 下一步 - Production 優化

## 目前重點（2026-01）

### 🔄 進行中：效能優化

**目標**：優化 Reasoning 系統的延遲、成本、品質

**已完成基礎**：
- ✅ Reasoning 模組（orchestrator + 4 agents）
- ✅ Deep Research Method（SSE 串流）
- ✅ XGBoost ML Ranking（Phase A/B/C）
- ✅ Time Range & Clarification
- ✅ BM25, MMR, Analytics 基礎設施
- ✅ Tier 6 API 整合（Stock, Weather, Wikipedia）

**目前優化任務**：

1. **降低 Reasoning 延遲**
   - 分析迭代時間（Analyst/Critic/Writer 階段）
   - 找出 LLM 呼叫瓶頸
   - 優化 prompt token 使用量
   - 考慮並行 agent 執行

2. **改善引用品質**
   - 測試幻覺防護邊界案例
   - 根據實際使用調整來源分層規則
   - 增加引用格式選項
   - 驗證引用連結正確性

3. **提升使用者體驗**
   - 改善澄清問題品質
   - 加入長查詢進度指示器
   - 實作使用者回饋迴圈
   - 更好的錯誤訊息

4. **成本優化**
   - 分析各 agent token 使用量
   - 精簡 prompt 但維持品質
   - 實作智慧快取策略
   - 考慮非關鍵 agent 降級模型

---

## 短期任務（2-4 週）

### 1. Reasoning 系統精煉
**優先級**：高

**任務**：
- 使用 20+ 多樣查詢分析效能
- 測量迭代時間、token 使用、每查詢成本
- 找出優化機會
- 實作前 3 項優化

**成功指標**：
- 平均延遲降低 20-30%
- 每查詢成本降低 15-25%
- 維持或改善引用品質

### 2. 澄清流程 UI
**優先級**：中

**任務**：
- 設計澄清問題 UI
- 實作使用者回應捕捉
- 整合回應與重新查詢流程
- 測試模糊查詢

**需修改檔案**：
- `static/news-search-prototype.html`
- `webserver/routes/api.py`
- `methods/deep_research.py`

### 3. 幻覺防護測試
**優先級**：高

**任務**：
- 建立 10+ 邊界案例測試套件
- 測試引用驗證邏輯
- 驗證集合操作（writer sources ⊆ analyst sources）
- 記錄失敗模式與緩解方案

### 4. A/B 測試基礎設施
**優先級**：中

**任務**：
- 實作 reasoning vs 標準搜尋 feature flag
- 加入查詢路由邏輯（10% → 50% → 100%）
- 設定比較指標儀表板
- 定義成功標準（CTR、停留時間、品質評分）

---

## 中期任務（1-2 月）

### 1. 模型重訓練管道
**目標**：XGBoost ranker 持續學習

**任務**：
- 設定自動每週/月重訓練
- 納入最新使用者互動資料
- 評估模型效能趨勢
- 以 A/B 測試部署新模型

### 2. 進階 Reasoning 功能
**目標**：增強推論能力

**任務**：
- 多輪研究（後續查詢）
- 交叉參考偵測（矛盾、確認）
- 時間分析（趨勢偵測、時間線建構）
- 比較研究（並列分析）

### 3. 使用者個人化
**目標**：依使用者偏好調整結果

**任務**：
- 追蹤使用者互動模式
- 建立使用者偏好檔案
- 個人化來源分層權重
- MMR 自適應 λ 調整

---

## 長期願景（3-6 月）

### 1. 多目標優化
- 平衡相關性、多樣性、新鮮度、可信度
- 納入商業指標（參與度、營收）
- 依查詢類型動態目標權重

### 2. 線上學習
- 以新資料增量更新模型
- 更快適應變化模式
- 即時回饋迴圈

### 3. 擴展來源覆蓋
- 增加更多 tier 1-2 來源（擴展至 20+ 來源）
- 改善未知來源處理
- 多語言支援（英文、日文）

---

## 已完成

### ✅ Track A：Analytics 基礎設施
- PostgreSQL via Neon.tech
- 查詢日誌與 parent_query_id 連結
- 多點擊追蹤
- 儀表板與 CSV 匯出

### ✅ Track B：BM25 實作
- 自訂 BM25 實作
- Intent 偵測（EXACT_MATCH, SEMANTIC, BALANCED）
- 混合評分（α * vector + β * bm25）

### ✅ Track C：MMR 實作
- 經典 MMR 公式與 intent-based λ 調整
- Cosine similarity 多樣性測量

### ✅ Track D：Reasoning 系統
- Actor-Critic orchestrator
- 4 個專門 agent
- 來源分層過濾
- 幻覺防護與引用驗證

### ✅ Track E：Deep Research Method
- 與 NLWeb 管道整合
- 時間範圍抽取
- 澄清流程
- SSE 串流與引用

### ✅ Track F：XGBoost ML Ranking
- Phase A/B/C 完整部署
- Shadow mode → Rollout

### ✅ Track G：Tier 6 API 整合
- Stock, Weather, Wikipedia APIs
- 知識增強 Gap Resolution

### ✅ Track H：Reasoning 系統強化
- Free Conversation Mode（Deep Research 後續 Q&A）
- Phase 2 CoV（Chain of Verification 事實查核）

### ✅ Track I：M0 Indexing 資料工廠
- Crawler 系統（7 個 Parser）
- Indexing Pipeline（完整模組）
- CLI 工具

### ✅ Track J：E2E 驗證與搜尋優化
- MCP Wrapper 實作
- Streaming 改進
- E2E 測試框架
- 搜尋模式統一化
- Qdrant 連線修復

### ✅ Track K：Subprocess Per Crawler（B1）
- 每個 crawler 獨立 subprocess（GIL 隔離）
- JSON lines IPC protocol
- Signal file 停止機制
- Chinatimes 設定同步（7 個 Parser）

### ✅ Track L：Crawler Fixes & Dashboard Enhancement
- UTF-8 decode 修復
- Dashboard Clear by Error Type
- Tasks.json 清理

### ✅ Track M：Scrapy/Trafilatura 最佳模式整合
- AutoThrottle（Scrapy 風格自適應延遲）
- htmldate/trafilatura 通用 fallback（engine 層級）
- Response latency 追蹤
- charset_normalizer 編碼偵測

### ✅ Track N：Code Review 修復 + C3 Qdrant UUID5
- CancelledError unpack 修復（BaseException）
- `_ensure_date()` log 加 URL
- C3 Qdrant Point ID → UUID5（零成本遷移）

### ✅ Track O：UDN Sitemap Backfill + curl_cffi 清理
- UDN sitemap mode 串接（subprocess_runner + dashboard_api）
- curl_cffi fail fast（移除 silent fallback + 4 parser 兼容 shim）
- MOEA 加入 CURL_CFFI_SOURCES
- Dead code bug 修正（_create_session CurlSession 縮排）
- 全量 backfill 啟動（7 source，2024-02 起）

### ✅ Track P：Qdrant Profile 切換系統
- QDRANT_PROFILE=online|offline 環境變數
- Profile manager + dimension validation
- 線上/線下安全切換

### ✅ Track Q：Dashboard Bug Fixes + Full Scan 穩定性
- MOEA rate limiting 修復（concurrent=2, delay=2-4s）
- `null -> null` 顯示 bug 修復（3 層：start_crawler + progress + engine stats）
- Task cleanup（124→13 tasks）
- indexing-spec.md 全面更新

---

*更新：2026-02-12*
