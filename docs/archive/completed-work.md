# 已完成工作記錄

本文件包含已完成 tracks 的詳細實作歷史。僅在需要過去實作詳細上下文時參考。

---

## ✅ Track AF：Analytics 系統完整清理（2026-03-16）

**目標**：修復 analytics 系統技術債 — 兩套不同步 schema、16 個幽靈欄位、data collection 缺口、B2B 欄位缺失。

- **Phase 0**: Schema 統一 — 新建 `schema_definitions.py`（7 表、101 欄位、18 index），刪除 ~586 行重複
- **Phase 1**: 3 Critical + 3 High + 2 Medium bugs 修復（export 壞掉、event loop blocking、JOIN 膨脹）
- **Phase 2**: 幽靈欄位清理、`postgres_client.py` 補 analytics logging、ranking_position 修正
- **Phase 3**: B2B 欄位對齊、feature_vectors 重建
- **Phase 4**: AnalyticsDB singleton 統一、Worker busy-wait 修正
- **Phase 5**: VPS migration + 線上驗證通過
- **Code Review x2**: 21 + 8 issues 全部修復
- **新建**: `docs/specs/analytics-spec.md`

---

## ✅ Track Y：SEC-6 Lossless Agent Isolation Phase 1（2026-02-23）

**目標**：防止 `reasoning/orchestrator.py` gap resolution 迴圈中 `current_context` 無限增長，超出 LLM token 上限。每個 agent 只注入它需要的 context，零 LLM 行為變更。

### 修改檔案

| 檔案 | 改動摘要 |
|------|----------|
| `config/config_reasoning.yaml` | Feature flag `agent_isolation: false` + 配置區塊（thresholds） |
| `reasoning/orchestrator.py` | `_format_context_shared()` +`start_id` 參數；`_build_critic_reference_sheet()` 新方法；gap loop context 路由；critic reference sheet；writer draft 長度監控；citation 驗證 |
| `reasoning/agents/analyst.py` | `research()` +`previous_draft` 參數 |
| `reasoning/prompts/analyst.py` | `build_research_prompt()` +`previous_draft` 參數，注入先前草稿 |

### 核心設計

1. **Feature Flag 控制**：`reasoning.features.agent_isolation`（預設 false）
   - Flag off = 完全保持既有行為（所有 `else` branch 為原始碼）
   - Flag on = context 路由隔離

2. **Gap Search 隔離**（SEARCH_REQUIRED 路徑）
   - `_format_context_shared(new_context, start_id=N)` 只格式化新文件
   - `source_map.update()` 累積全部 source，`formatted_context` 只有新批次
   - ID collision 檢查在 merge 前執行

3. **Gap Resolution 隔離**（Stage 5 enriched re-run）
   - 只傳新 context items + `previous_draft`（讓 Analyst 知道前幾輪分析了什麼）
   - Prompt 注入：「你之前的分析草稿（參考用）」

4. **Critic Reference Sheet**
   - `_build_critic_reference_sheet(citations_used)` 只取被引用的 source
   - 安全閥：ref_sheet < 1000 chars 或 citations < 2 → fallback full context（從 `current_context` 重建）
   - Log reduction %

5. **監控**
   - Citation 驗證：`citations_used` vs `source_map`，invalid → error log
   - Writer draft 長度超過 20K → warning
   - SEC-6 prefix 的 structured log

### Code Review 修復（同 session）

| Bug | 嚴重度 | 修復 |
|-----|--------|------|
| Critic fallback 用 stale `self.formatted_context`（isolation mode 下只有最新 batch） | High | 改為從 `current_context` 重建 full context |
| Dict keys 永遠唯一的 tautological assertion | Medium | 改為 merge 前 overlap 檢查 |
| `_build_critic_reference_sheet` bare except 無 log | Low | 新增 warning log |

### 注意事項

- **Phase 2 待做**：`ExtractedFact` schema + accumulated_knowledge 累積邏輯（Phase 1 驗證有效後）
- **`seen_citation_ids`** 已追蹤但未使用（Phase 2 prep）
- **驗證方式**：啟用 `agent_isolation: true` 後，觀察 SEC-6 開頭的 log

---

## ✅ Track X：全專案 Code Review 修復（2026-02-23）

**目標**：修復 code review 報告中的 47 項 Security、Bug、效能問題

### 修改檔案

| 檔案 | 修復 ID | 改動摘要 |
|------|---------|----------|
| `crawler/core/engine.py` | ENG-1,4,5,7,8,9,10,11 | save 狀態修正、double count、asyncio deprecated、parse≠blocked、_ensure_date、crawled_ids→SQLite、FileHandler cleanup、Big5 fallback |
| `crawler/core/crawled_registry.py` | IDX-6,7,10,15,16 | RLock SQL 保護、atomic upsert、buffer swap、precise LIKE、close flush |
| `crawler/subprocess_runner.py` | ENG-12 | engine.close() try/except |
| `indexing/dashboard_api.py` | IDX-1,3,8,9,11,12,18,19 | Qdrant close、atomic save、WebSocket set、task prune、fd leak、int validation、asyncio fix |
| `indexing/pipeline.py` | IDX-4,13,14 | resumable flush、buffer rotate、checkpoint off-by-one |
| `indexing/qdrant_uploader.py` | IDX-5,17,21 | embed retry、len check、docstring |
| `webserver/middleware/cors.py` | SEC-2 | CORS origin 白名單 + Render pattern |
| `webserver/routes/oauth.py` | SEC-13,20 | state TTL 600s、URL encode |
| `core/query_logger.py` | SEC-3,24 | SQL 白名單、connection cleanup |
| `core/retriever.py` | RNK-1,9,11,12 | cache 分離、params key、移除 pip install、移除讀 lock |
| `core/ranking.py` | RNK-4,10,14,15 | gather return、name init、off-by-one、get() |
| `core/mmr.py` | RNK-2,5 | 預計算 similarity matrix、dimension warning |
| `core/xgboost_ranker.py` | RNK-3,8 | dict attribute、NaN handling |
| `core/bm25.py` | RNK-7 | title boost multiplier（不膨脹 doc_length） |
| `training/feature_engineering.py` | RNK-20 | bare except → except Exception |
| `reasoning/orchestrator.py` | SEC-5,RSN-1,5,7,10,11,12 | citation 驗證、空 draft 攔截、hints rebuild、response init、tracer safe、no-results、div-by-zero |
| `reasoning/agents/base.py` | RSN-2 | inner timeout < outer |
| `reasoning/agents/writer.py` | RSN-8 | 統一用 PromptBuilder |
| `reasoning/agents/critic.py` | RSN-4 | CoV 失敗 → verification_status alert |
| `static/news-search.js` | SEC-10 | DOMPurify.sanitize() × 4 處 |
| `static/news-search-prototype.html` | SEC-10 | DOMPurify CDN script tag |

### 延後項目

| ID | 原因 |
|----|------|
| SEC-1 + SEC-9 + SEC-18 + SEC-19 | JWT 認證尚未設定，等登入系統 |
| SEC-6 | Lossless Agent Isolation 架構重構，獨立任務 |

### 注意事項

- **RNK-7**：BM25 `calculate_corpus_stats()` 不再 3x 重複 title → `avg_doc_length` 改變，需重建 corpus stats
- **RSN-4**：前端需讀取 `verification_status` / `verification_message` 顯示未驗證提示
- **SEC-2**：可透過 `CORS_ALLOWED_ORIGINS` 環境變數擴充允許的 origin
- **ENG-9**：crawled_ids 從記憶體 set 改為 SQLite 查詢，full_scan 每筆 +0.3ms overhead

---

## ✅ Track T：Chinatimes 雙機協作 + Date Filter 修復（2026-02-15）

**目標**：桌機+GCP 雙機夾擊加速 Chinatimes sitemap backfill

### 修改檔案

| 檔案 | 改動 |
|------|------|
| `crawler/core/engine.py` | `run_sitemap()` +`sitemap_offset`/`sitemap_count` 參數 + date filter 修復 |
| `crawler/subprocess_runner.py` | Forward 2 新參數 |
| `scripts/gcp-chinatimes-sitemap.sh` | GCP 自管理腳本（新建） |
| `docs/gcp-crawler-spec.md` | 工作分配更新 |

### Date Filter Bug 修復

- **根因**：`_filter_article_urls_by_date()` 優先使用 lastmod 日期
- Chinatimes lastmod = sitemap 重新產生日期（2024-02-27），非文章發布日期
- 2010 年文章的 lastmod=2024 → 通過 `date_from=202401` filter
- **修復**：改為 URL 日期優先（提取 YYYYMMDD），lastmod 僅作 fallback
- **驗證**：5 個 2010-era sub-sitemap 正確 exclude 44,364 篇

### GCP 腳本設計

- 從 sub-sitemap #980 往回跑（桌機從 #1 往前）
- 適應性批次：空區間 x3（max 200）、密集區 /2（min 5）
- State file crash recovery（`chinatimes_gcp_state.json`）
- 停止條件：距桌機 50 sub-sitemap 或連續 3 次 failed
- Coverage 報告（每批次查詢 registry 月份分佈）

---

## ✅ Track A：Analytics 日誌基礎設施

**成就**：完整 analytics 系統部署至 production，含 PostgreSQL 後端、Schema v2、parent query ID 連結。

**已實作元件**：

1. **資料庫 Schema v2**（`core/analytics_db.py`、`core/query_logger.py`）
   - 4 核心表：queries、retrieved_documents、ranking_scores、user_interactions
   - 1 ML 表：feature_vectors（35 欄位）
   - 雙資料庫支援：SQLite（本地）+ PostgreSQL（production via Neon.tech）
   - 透過 `ANALYTICS_DATABASE_URL` 環境變數自動偵測

2. **Query Logger**（`core/query_logger.py`）
   - 同步 parent table 寫入：`log_query_start()` 直接寫入防止 race conditions
   - 子表使用 async queue
   - 追蹤完整查詢生命週期
   - 使用者互動追蹤：點擊（左/中/右）、停留時間、滾動深度
   - Parent Query ID：連結 generate 請求至其 parent summarize 請求

3. **Analytics API**（`webserver/analytics_handler.py`）
   - 儀表板端點：`/api/analytics/stats`、`/api/analytics/queries`
   - CSV 匯出：含 UTF-8 BOM 支援中文字元

4. **儀表板**（`static/analytics-dashboard.html`）
   - 即時指標：總查詢數、平均延遲、CTR、錯誤率
   - 訓練資料匯出功能

5. **前端 Analytics Tracker**
   - 使用 SSE（非 WebSocket）
   - 多點擊追蹤

---

## ✅ Track B：BM25 實作

**目標**：以 BM25 演算法取代 LLM 關鍵字評分，提供一致、快速的關鍵字相關性。

**已建置**：

1. **BM25 Scorer**（`core/bm25.py`）
   - 自訂 BM25 實作（無外部 library）
   - Tokenization：中文 2-4 字元序列、英文 2+ 字元詞
   - 參數：k1=1.5、b=0.75

2. **Intent 偵測**（`retrieval_providers/qdrant.py`）
   - **EXACT_MATCH**（α=0.4, β=0.6）：優先 BM25
   - **SEMANTIC**（α=0.7, β=0.3）：優先向量
   - **BALANCED**：預設 α/β

3. **Qdrant 整合**
   - 混合評分：`final_score = α * vector_score + β * bm25_score`

---

## ✅ Track C：MMR 實作

**目標**：以 MMR 演算法取代 LLM 多樣性重排序。

**已建置**：

1. **MMR 演算法**（`core/mmr.py`）
   - 經典 MMR 公式：`λ * relevance - (1-λ) * max_similarity`
   - Intent-based λ 調整：
     - SPECIFIC（λ=0.8）
     - EXPLORATORY（λ=0.5）
     - BALANCED（λ=0.7）

2. **整合**（`core/ranking.py`）
   - LLM ranking 後執行一次
   - 記錄 MMR 分數至 analytics database

---

## ✅ Track D：Reasoning 系統

**目標**：建構多 Agent 推論系統，具 Actor-Critic 架構用於深度研究

**已建置**：

1. **Reasoning Orchestrator**（`reasoning/orchestrator.py`）
   - Actor-Critic 迴圈（max 3 iterations）
   - 4 階段管道：Filter → Analyst → Critic → Writer
   - 幻覺防護：驗證 writer citations ⊆ analyst citations
   - 統一上下文格式化
   - 優雅降級
   - Token 預算控制（MAX_TOTAL_CHARS = 20,000）

2. **四個專門 Agent**
   - **Analyst**：研究與合成、引用追蹤
   - **Critic**：品質審查（5 criteria）、PASS/REJECT
   - **Writer**：最終格式化、markdown 引用
   - **Clarification**：歧義偵測、問題生成

3. **來源分層過濾**（`reasoning/filters/source_tier.py`）
   - 3 模式：strict、discovery、monitor
   - 10 個來源知識庫

4. **除錯工具**
   - ConsoleTracer：即時事件視覺化
   - IterationLogger：JSON 事件流日誌

---

## ✅ Track E：Deep Research Method

**目標**：整合 Reasoning Orchestrator 與 NLWeb 搜尋管道

**已建置**：

1. **Deep Research Handler**（`methods/deep_research.py`）
   - Retrieval 後呼叫 Reasoning Orchestrator
   - SSE 串流整合
   - NLWeb Item 格式輸出

2. **時間範圍抽取**（`core/query_analysis/time_range_extractor.py`）
   - 3 層解析：Regex → LLM → Keyword fallback
   - 絕對日期轉換

3. **澄清流程**
   - 透過 Clarification Agent 偵測模糊查詢
   - 回傳澄清問題至前端

---

## ✅ Track F：XGBoost ML Ranking

**目標**：以 ML 模型部分取代 LLM ranking，降低成本/延遲

**已建置**：

**Phase A：基礎設施** ✅
- Feature Engineering 模組
- XGBoost Ranker 模組
- Training Pipeline

**Phase B：訓練管道** ✅
- Binary classification trainer
- LambdaMART trainer
- XGBRanker trainer
- 模型評估（NDCG@10, Precision@10, MAP）

**Phase C：Production 部署** ✅
- 與 `core/ranking.py` 整合（LLM → XGBoost → MMR）
- Shadow mode 驗證
- 模型 registry 與版本控制

**關鍵功能**：
- 29 features 從 analytics schema
- XGBoost 使用 LLM 分數作為 features（features 22-27）
- Global model caching
- Confidence score 計算

---

## ✅ Track G：Tier 6 API 整合（2026-01）

**目標**：為 Gap Resolution 新增外部知識 API

**已建置**：
- `llm_knowledge`：問 LLM
- `web_search`：Bing/Google Search
- `stock_tw`：Yahoo Finance Taiwan
- `stock_global`：Yahoo Finance
- `wikipedia`：Wikipedia API
- `weather_*`：Weather APIs
- `company_*`：Company APIs

---

## ✅ Track H：Reasoning 系統強化（2026-01-28）

**目標**：強化 Reasoning 系統的多輪對話與事實查核能力

**已建置**：

1. **Free Conversation Mode**（`methods/generate_answer.py`）
   - 注入之前的 Deep Research 報告進行後續 Q&A
   - 支援多輪對話延續研究上下文
   - 自動偵測並載入相關報告

2. **Phase 2 CoV（Chain of Verification）**
   - 事實查核機制整合於 Critic Agent
   - 驗證 Analyst 輸出的事實準確性
   - 實作於 `reasoning/agents/critic.py`
   - Prompt 定義於 `reasoning/prompts/cov.py`

---

## ✅ Track I：M0 Indexing 資料工廠（2026-01-28）

**目標**：建構完整 Data Pipeline - Crawler → Indexing → Storage

### Crawler 系統（`code/python/crawler/`）

**7 個 Parser**：
| Parser | 來源 | 爬取模式 | HTTP Client |
|--------|------|----------|-------------|
| `ltn` | 自由時報 | Sequential ID | AIOHTTP |
| `udn` | 聯合報 | Sequential ID + **Sitemap** | AIOHTTP |
| `cna` | 中央社 | Date-based ID | CURL_CFFI |
| `chinatimes` | 中時新聞 | Date-based ID | CURL_CFFI |
| `moea` | 經濟部 | List-based | CURL_CFFI |
| `einfo` | 環境資訊中心 | Sequential + Binary Search | CURL_CFFI |
| `esg_businesstoday` | 今周刊 ESG | Sitemap / Date-based | CURL_CFFI |

**核心模組**：
- `core/engine.py` - 爬蟲引擎（async 支援）
- `core/interfaces.py` - 抽象介面（BaseParser, TextProcessor）
- `core/pipeline.py` - 處理管線
- `core/settings.py` - 配置常數（rate limits, timeouts）
- `parsers/factory.py` - Parser 工廠模式

**特色**：
- Binary Search 自動偵測最新 ID
- Sitemap 模式批量取得
- 34 個單元測試 + E2E 測試

### Indexing Pipeline（`code/python/indexing/`）

**模組**：
- `source_manager.py` - 來源分級（Tier 1-4）
- `ingestion_engine.py` - TSV → CDM 解析
- `quality_gate.py` - 品質驗證（長度、HTML、中文比例）
- `chunking_engine.py` - 170 字/chunk + Extractive Summary
- `dual_storage.py` - SQLite + Zstd 壓縮（VaultStorage）
- `rollback_manager.py` - 遷移記錄、payload 備份
- `pipeline.py` - 主流程 + 斷點續傳
- `vault_helpers.py` - Async 介面

**CLI**：
```bash
# Crawler
python -m crawler.main --source ltn --auto-latest --count 100

# Indexing
python -m indexing.pipeline data.tsv --site udn --resume
```

---

## ✅ Track J：E2E 驗證與搜尋優化（2026-02-04）

**目標**：完善端到端測試基礎設施，優化搜尋體驗

### E2E 驗證基礎設施

**MCP Wrapper**：
- 統一 Model Context Protocol 封裝
- 支援多種 LLM 後端整合

**Streaming 改進**：
- SSE 串流效能優化
- 前端接收處理修復
- 穩定性改善

**E2E 測試框架**：
- 端到端測試基礎設施
- 整合測試覆蓋率提升

### 搜尋模式優化

**統一搜尋 UX 重構**：
- 搜尋模式統一化（list/summarize/generate）
- 前端 UI/UX 改進
- 多項 Bug 修復

**Qdrant 連線修復**：
- 修復遠端連線逾時問題
- 改善連線穩定性

---

## ✅ Track N：Code Review 修復 + C3 Qdrant UUID5（2026-02-10）

**目標**：Code review 發現的 bug 修復 + Qdrant Point ID 安全性提升

**已建置**：

1. **CancelledError unpack 修復**（`engine.py:767`）
   - `_evaluate_batch_results()`: `isinstance(result, Exception)` → `BaseException`
   - 根因：Python 3.9+ `CancelledError` 繼承 `BaseException`，`asyncio.gather(return_exceptions=True)` 回傳 CancelledError 時判斷不到

2. **`_ensure_date()` log 改善**（`engine.py`）
   - 新增 `url` 參數，5 個呼叫點全部傳入
   - 丟棄文章時 warning log 包含 URL，便於 debug

3. **`_adaptive_delay()` jitter 上限 clamp**（`engine.py`）
   - `actual = max(min_delay, min(actual, max_delay))`

4. **C3 Qdrant Point ID → UUID5**（`qdrant_uploader.py`）
   - `hashlib.md5` 截斷 64-bit int → `uuid.uuid5()` string
   - 碰撞風險從 Birthday Paradox 等級降至趨近零
   - Qdrant 無資料，零成本遷移

---

## ✅ Track M：Scrapy/Trafilatura 最佳模式整合（2026-02-10）

**目標**：將 Scrapy/Trafilatura 的架構模式提升到 engine 層級，讓所有 7 個來源受益

**背景**：A/B 測試結論 — Custom parser 在已知來源大勝（20/20 vs 1/20 vs 0/20），但框架的**架構模式**值得學習。

**已建置**：

1. **AutoThrottle**（`engine.py` + `settings.py`）
   - Scrapy 風格 EWMA 自適應延遲：`new_delay = (old + avg_latency/target) / 2`
   - 取代 4 處固定 `random.uniform(min_delay, max_delay)` 呼叫
   - `_throttle_backoff()`: 錯誤回應加倍 delay
   - `AUTOTHROTTLE_ENABLED` 開關，可隨時回退到固定延遲

2. **htmldate 通用 Fallback**（`engine.py`）
   - `_ensure_date(data, html)`: 3 個 parse 成功路徑全部加入
   - parser 漏掉 datePublished → htmldate 自動補上
   - 無日期 → 丟棄文章

3. **Trafilatura 通用 Fallback**（`engine.py`）
   - `_trafilatura_fallback(html, url)`: custom parser → None 後最後嘗試
   - `bare_extraction(favor_precision=True)` + 品質檢查
   - `stats['trafilatura_fallbacks']` 追蹤勝率
   - 標記 `_source: "trafilatura_fallback"` 便於溯源

4. **Response Latency 追蹤**（`engine.py`）
   - rolling window 50 筆，`_avg_latency` 滾動平均
   - `_fetch()` HTTP request 前後 `time.monotonic()` 計時
   - Dashboard 自動顯示 `avg_latency` / `current_delay`

**設計決策**：
- htmldate/trafilatura 放 engine 而非 BaseParser：engine 是同時持有 html + data 的唯一地方
- per-source `min_delay`/`max_delay` 作為硬邊界不變（NEWS_SOURCES 不動）
- einfo parser 已內建 trafilatura，engine fallback 不會重複觸發

---

## ✅ Track L：Crawler Fixes & Dashboard Enhancement（2026-02-10）

**目標**：修復 crawler 穩定性問題，完善 Dashboard 操作對稱性

**已建置**：

1. **UTF-8 Decode Error 修復**（`crawler/core/engine.py`）
   - curl_cffi `response.text` 遇 Big5/cp950 content 會拋 UnicodeDecodeError
   - 新增 try/except fallback: `response.content.decode('utf-8', errors='replace')`
   - 修復 CNA/einfo subprocess crash 問題

2. **Tasks.json 清理**
   - 累積 140 筆（71% failed）→ 3 筆 zombie tasks（標記 failed）
   - `crawled_registry.db` 不受影響（393K articles 去重正常）

3. **Dashboard Clear by Error Type**
   - `crawled_registry.py` `clear_failed()`: 新增 `error_types: Optional[List[str]]` 參數
   - `dashboard_api.py` `clear_errors()`: 傳遞 `error_types` 到 registry
   - `indexing-dashboard.html` `clearErrors()`: 與 `retryAllErrors()` 對齊，使用相同過濾邏輯

---

## ✅ Track K：Subprocess Per Crawler（2026-02-09）

**目標**：每個 crawler 在獨立 subprocess 中執行，實現 GIL 隔離與獨立 event loop

### Subprocess Architecture

**新檔案**：
- `crawler/subprocess_runner.py` — subprocess 入口點，接收 CLI 參數，輸出 JSON lines

**修改檔案**：
- `indexing/dashboard_api.py` — 新增 `_run_crawler_subprocess()`，替換所有 `asyncio.create_task` 為 `create_subprocess_exec`
- `crawler/core/engine.py` — 新增 `stop_check` callback 參數
- `crawler/core/settings.py` — 新增 chinatimes FULL_SCAN_OVERRIDES

**IPC Protocol**（stdout JSON lines）：
```jsonl
{"type": "progress", "stats": {...}}
{"type": "completed", "stats": {...}}
{"type": "error", "error": "message"}
```

**Stop Mechanism**：
1. Signal file: `data/crawler/signals/.stop_{task_id}`
2. Engine `_report_progress()` 檢查 → `CancelledError`
3. 10 秒 timeout → `proc.terminate()`

**CrawlerTask 資料結構變更**：
- `_asyncio_task` → `_process` (subprocess handle) + `_reader_task` (stdout reader) + `_pid` (PID 持久化)

### Chinatimes 設定同步

- `dashboard_api.py` FULL_SCAN_CONFIG 新增 chinatimes（date_based）
- `settings.py` FULL_SCAN_OVERRIDES 新增 chinatimes（concurrent=6, delay=0.3-0.8s）

### Windows UnicodeDecodeError 修復

- **根因**：`CrawlerEngine._setup_logger()` 預設將 StreamHandler 輸出到 stdout，Windows cp950 編碼的中文 log 破壞 JSON protocol
- **修復 1**（根因）：`subprocess_runner.py` monkey-patch `_setup_logger`，將所有 StreamHandler 重導到 stderr
- **修復 2**（防禦）：`dashboard_api.py` stdout 解碼改用 `decode("utf-8", errors="replace")`

### Zombie/Orphan Subprocess 清理

- **問題**：Server 重啟時 subprocess 孤兒繼續存活，auto-resume 產生重複 crawler
- **PID 持久化**：`CrawlerTask._pid` + `_task_to_dict()` 寫入 JSON + `_load_tasks()` 讀回
- **3 步清理**（`_load_tasks()`）：
  1. 建立 signal file（讓 subprocess graceful stop）
  2. `_kill_orphan_process(pid)`（Windows: `taskkill /F /PID`, Unix: `SIGTERM`）
  3. 標記 failed → 收集 auto-resume 候選
- **結果**：重啟後先 kill 舊 subprocess，再從 checkpoint 啟動新的，不會重複

---

## ✅ Track U：三機協作 + merge_registry 強化（2026-02-12）

**目標**：規劃三機分工 backfill，強化跨機器資料合併工具

**已建置**：

1. **三機分工規劃**（`docs/crawler-deployment-prompt.md`）
   - 桌機：LTN/CNA/einfo 收尾 → Chinatimes 全力
   - 筆電：UDN sitemap（65K gap）+ MOEA backfill（500 篇）
   - GCP：暫緩（einfo 已在桌機用 proxy pool 處理）
   - 完整部署指南含環境設定、API 指令、監控與異常排除

2. **merge_registry.py 支援 failed_urls**（`crawler/remote/merge_registry.py`）
   - 新增 `failed_urls` 表合併：`INSERT OR IGNORE ... WHERE url NOT IN (SELECT url FROM crawled_articles)`
   - 表存在性檢查（`sqlite_master`），相容無 `failed_urls` 表的舊 DB
   - pre-merge stats 顯示 failed_urls 數量
   - 遠端 transient failures 統一收回桌機 retry

3. **Tasks 清理**
   - 移除 UDN/Chinatimes/ESG_BT 歷史 tasks
   - 重建乾淨 tasks.json，watermarks 不受影響

---

## ✅ Track S：Dashboard 穩定性 + Watermark Skip Bug 修復（2026-02-12）

**目標**：修復 Dashboard event loop 阻塞、watermark skip 誤殺 blocked URLs、sitemap OOM

**已建置**：

1. **Watermark Skip Bug 修復**（`engine.py`, `crawled_registry.py`）
   - `load_blocked_ids(source_id)`: 從 `failed_urls` 提取 blocked article IDs（通用 URL regex 支援全 7 source）
   - `load_blocked_dates(source_id)`: 提取 blocked URLs 的日期集合（date-based sources）
   - Sequential skip 條件加入 `AND current_id NOT IN blocked_ids`
   - Date-based skip 條件加入 `AND current_day NOT IN blocked_dates`
   - 影響：4,581 blocked URLs 不再被誤跳過

2. **stderr→file Event Loop 修復**（`dashboard_api.py`）
   - `stderr=asyncio.subprocess.PIPE` → `stderr=stderr_log_file`（file redirect）
   - 12 concurrent pipe readers → 6（只保留 stdout），全部低頻
   - Dashboard 穩定 4+ 小時、6 concurrent subprocesses

3. **Adaptive Throttle Backoff Ceiling**（`engine.py`）
   - `_throttle_backoff()`: 上限從 `max_delay` 提升至 `max_delay * 4`
   - `_adaptive_delay()`: effective_max = max(max_delay, current_delay)
   - 解決 MOEA 429 無效 backoff 迴圈

4. **Sitemap Incremental Processing**（`engine.py`）
   - `run_sitemap()` 重構：逐 sub-sitemap 處理（download → crawl → discard）
   - 記憶體從 870MB crash 降至 ~130MB

5. **Windows Force Kill Pipe Fix**（`dashboard_api.py`）
   - `_force_kill_after()` 在 `proc.kill()` 後 cancel `task._reader_task`

6. **Qdrant Stats Non-blocking**（`dashboard_api.py`）
   - `_get_qdrant_stats()` 移至 `run_in_executor()`

---

## ✅ Track R：整夜監控 + Subprocess 穩定性 + Auto-Restart（2026-02-12）

**目標**：自動化監控整夜 backfill + 修復穩定性問題

**已建置**：

1. **stderr Pipe Buffer 死鎖修復**（`dashboard_api.py`）
   - **根因**：`_run_crawler_subprocess()` 建立 subprocess 時 `stderr=asyncio.subprocess.PIPE` 但從未讀取 stderr
   - 快速爬蟲（LTN/CNA）log 填滿 Windows 65KB pipe buffer → subprocess 阻塞在 write → stdout 同步停止 → parent 看到計數器凍結
   - **修復**：新增 `_drain_stderr()` async task，與 stdout reader loop 並行：
   ```python
   async def _drain_stderr():
       async for line in proc.stderr:
           logger.debug(f"[{task.task_id}] {line.decode()[:300]}")
   stderr_task = asyncio.create_task(_drain_stderr())
   ```
   - 修復後連續 72+ 分鐘零凍結

2. **MOEA Auto-Restart 機制**（`dashboard_api.py`）
   - `AUTO_RESTART_DELAY = {"moea": 900}` — early_stop 後 15 分鐘自動從 checkpoint 重啟
   - `_delayed_restart()`: `asyncio.sleep(delay)` → 檢查無同 source running → `_auto_resume_task()`
   - 解決 MOEA 因政府網站 rate limit 導致 early_stop 後需人工重啟的問題

3. **自動化監控迴圈**（`scripts/crawler-monitor/`）
   - `monitor-loop.sh`: 外部 bash loop，每 30 分鐘啟動新 Claude CLI session（Ralph Wiggums pattern）
   - `monitoring-plan.md`: 完整 monitoring prompt（356 行）
   - `monitoring-log.md`: 持久化跨 session log
   - 整夜執行 12 次 check（01:04→09:48），自主修復 9 次凍結

4. **trafilatura 2.0 相容修復**（`engine.py`）
   - `bare_extraction()` 在 trafilatura 2.0+ 回傳 `Document` 物件而非 dict
   - 修復：`if hasattr(result, 'as_dict'): result = result.as_dict()`

---

## ✅ Track Q：Dashboard Bug Fixes + Full Scan 穩定性（2026-02-11）

**目標**：修復 Full Scan dashboard 顯示問題與 MOEA 限速

**已建置**：

1. **MOEA Rate Limiting 修復**（`settings.py`）
   - `FULL_SCAN_OVERRIDES["moea"]`: concurrent 5→2, delay (0.5-1.5)→(2.0-4.0)s
   - MOEA 政府網站需要低並發、長延遲，否則 429 封鎖

2. **`null -> null` 顯示 Bug 修復**
   - **根因**：`start_crawler` endpoint（通用）與 `start_full_scan`（專用）不同，未初始化 `scan_start`/`scan_end`
   - **修復 1**（`dashboard_api.py`）：`start_crawler` 當 mode=="full_scan" 時從 config 初始化掃描範圍
   - **修復 2**（`dashboard_api.py`）：progress handler 從 engine stats backfill 缺失的掃描範圍
   - **修復 3**（`engine.py`）：`_reset_stats()` 在兩種 full_scan 方法中加入 `scan_start`/`scan_end`

3. **Task Cleanup 最佳化**
   - 累積 124 筆（zombie cycle 造成）→ 13 筆
   - 清理邏輯：每個 source 保留最新 running + 最新 non-running
   - 將 running 改為 failed 以避免 auto-resume 再膨脹

4. **indexing-spec.md 全面更新**
   - MOEA session type、UDN sitemap 推薦、Sitemap Mode 文件、CURL_CFFI_SOURCES 文件

---

---

## ✅ Track W：Chinatimes Multi-Category 修復 + TimeoutError Bug Fix（2026-02-23）

**目標**：解決 Chinatimes full_scan 覆蓋率極低（~3K/月 vs sitemap ~50K/月）的根因

### 根因調查

**關鍵發現**：260402 category code 不是萬用路徑。每篇文章只有其正確 category code 能存取。

| 測試 | 結果 |
|------|------|
| 同 100 篇文章，260402 URL | 12% 成功 |
| 同 100 篇文章，正確 category URL | 96% 成功 |
| `?chdtv` 參數 | 零影響 |
| Session rotation | 零影響（IP 級，非 session 級） |
| Category rotation top 10 | 31%（從 16% 提升，但遠不夠） |

**Category 分佈**：136 個唯一 category。Top 40 = 95.6%，Top 10 僅 66.5%。

### 修改檔案

| 檔案 | 改動 |
|------|------|
| `crawler/parsers/chinatimes_parser.py` | `REALTIMENEWS_CATEGORY_CODES` 擴展至 40 個（含百分比註釋）；`get_candidate_urls()` 回傳 39 個候選 |
| `crawler/core/settings.py` | Chinatimes overrides: `max_candidate_urls=39`, `concurrent_limit=5`, `delay_range=(0.8, 2.0)` |
| `crawler/core/engine.py` | TimeoutError 修復（移除 `return NOT_FOUND`）+ per-source blocked tolerance |

### TimeoutError → NOT_FOUND Bug 修復

- **根因**：`engine.py:507` 的 `asyncio.TimeoutError` handler 直接 return `(None, CrawlStatus.NOT_FOUND)`
- NOT_FOUND 是永久跳過（寫入 `not_found_articles` 表），不會 retry
- **修復**：移除 return，讓 timeout 像其他 exception 一樣進入 retry 迴圈
- 影響：所有 7 source 的 timeout 文章不再被永久跳過

### GCP 部署

- SCP 3 檔案至 GCP（parser + settings + engine）
- 清除 1,069,846 筆舊 not_found（全是 260402-only 結果）
- Watermark 重設至 2025-06-30（sitemap 已覆蓋之前的日期）
- 新 task: `fullscan_chinatimes_29_1771827084`
- 初步驗證：15 秒 11 success（舊版同時段 1-2）

### 教訓

- **「260402 是萬用路徑」是錯的** — 來自早期少量測試的錯誤結論，影響數週的 full_scan 效率
- 每個假設都需要控制變量的 A/B 測試驗證

---

## ✅ Track V：Registry 合併 + daily-news-collector 平行化（2026-02-23）

**目標**：整合筆電爬取資料、優化每日新聞收集效率

### 修改檔案

| 檔案 | 改動 |
|------|------|
| `scripts/daily-news-collector.py` | `main()` 改為 `asyncio.gather` + `_safe_run()` wrapper |

### Registry 合併

- 筆電 `crawled_registry.db`（20MB）SCP 至桌機
- 合併方式：`ATTACH DATABASE` + `INSERT OR IGNORE`（crawled_articles、failed_urls、not_found_urls 三表）
- 結果：+36,631 crawled_articles（MOEA +5,805、UDN +30,752）、+13,975 failed_urls、+8 not_found
- 桌機 registry 總計：**1,910,520 筆**

### daily-news-collector 平行化

- **原始**：`for source in SOURCES: await run_source(source)`（串列，~60 分鐘）
- **修改**：`asyncio.gather(*[_safe_run(s) for s in SOURCES])`（並行，~20 分鐘）
- `_safe_run()` wrapper：每個 source 獨立 try/except，單一 source 失敗不影響其他 source
- 今日執行結果：ltn=1,407、chinatimes=986、udn=899、cna=53、moea=4、esg_bt=3、einfo=1（合計 3,353 篇）

---

*更新：2026-02-23*

---

## ✅ Track Z：UX Issues #1-11 修復（2026-02-24）

**目標**：修復 UX 測試回報的 11 個問題 + 前端 polish。

### 主要修改

| 變更 | 說明 |
|------|------|
| QueryUnderstanding 統一模組 | `core/query_analysis/query_understanding.py` — 取代 3 個獨立 pre-checks |
| Qdrant LLM-based boost | `retrieval_providers/qdrant.py` — domain filter 改為 LLM 動態 boost scoring |
| 年份推論規則 | `reasoning/prompts/clarification.py` — 防止未來日期誤判 |
| zh-TW 錯誤訊息 | `methods/generate_answer.py` — 英文 → 繁中 |
| datePublished 注入 | `reasoning/orchestrator.py` — Analyst formatted_context 包含發布日期 |
| Author search strict filter | `retrieval_providers/qdrant.py` — 精確 author 過濾 |
| Frontend polish | `static/news-search.js` — session history、feedback buttons、state cleanup |

## ✅ Track AB：GitHub Actions CI/CD Pipeline（2026-03-13）

**目標**：Push to `main` 自動部署至 Hetzner VPS + LINE Bot 通知

### 架構

```
Push to main → GitHub Actions → SSH to VPS → git pull + docker compose rebuild → Health check → LINE notify
```

### 修改檔案

| 檔案 | 改動 |
|------|------|
| `.github/workflows/deploy.yml` | 完整 CI/CD workflow（new） |
| `nginx.conf` | 註解微調（觸發 path filter） |

### 關鍵設計

1. **Path Filter**：只有 `code/**`, `static/**`, `config/**`, `Dockerfile`, `docker-compose.production.yml`, `nginx.conf`, `infra/**` 變更才觸發
2. **SSH Deploy**：`appleboy/ssh-action@v1`，Deploy-only ed25519 key
3. **VPS 操作**：`git fetch + reset --hard` → `docker compose up -d --build` → Health check（6 attempts × 10s via nginx port 80）
4. **LINE 通知**：Success/Failure 都發 push message，用 `printf` + `jq` 構造 JSON（避免 commit message 中的特殊字元和換行破壞 shell/YAML）
5. **GitHub Secrets**：`VPS_HOST`, `VPS_USERNAME`, `VPS_SSH_PRIVATE_KEY`, `VPS_SSH_PORT`, `LINE_CHANNEL_ACCESS_TOKEN`, `LINE_DESTINATION_USER_ID`

### VPS 準備

- 原為 SCP 部署，改為 `git init` + `git remote add` + `git fetch` + `git reset --hard`
- Deploy key 加入 `~/.ssh/authorized_keys`（`chattr +i` 保護）

### 迭代修復歷程（6 次）

| 問題 | 修復 |
|------|------|
| `script_stop` 不支援 | 改用 `set -e` |
| SSH key 缺少 header/footer | 完整 PEM 格式 |
| Health check port 8000 不通 | 改 port 80（通過 nginx） |
| Health check 10s 太短 | 6 attempts × 10s retry loop |
| Commit message 括號破壞 shell | `env:` block + `jq` 構造 JSON |
| YAML literal newline 語法錯 | `printf` 取代 literal `\n` |

### 注意事項

- 本地 main 有 32 個未推送 commits（包含進行中的工作），CI/CD 測試用 temp branch cherry-pick 方式推送
- 待本地工作穩定後，需 rebase 或 merge 本地 main 與 origin/main 的 CI/CD commits

---

## ✅ Track AC：Login 系統 B2B Production Ready（2026-03-16）

**目標**：補齊 Login 系統 B2B production 所需的 API、測試、前端功能，達到可上線狀態。

### Commits

| Commit | 內容 |
|--------|------|
| `49997e2` | Bug fixes：SQLite boolean compat、datetime fix、PUBLIC_ENDPOINTS 加 `/ask`/`/api/deep_research`/`/api/feedback`、route ordering |
| `6f00022` | 113/113 tests pass，適配 B2B bootstrap model |
| `17726b5` + `0960bdc` | 5 個新後端 API |

### 新增 API

| Endpoint | 說明 |
|----------|------|
| `POST /api/auth/change-password` | 已登入改密碼 |
| `POST /api/auth/logout-all` | 登出全部裝置 |
| `POST /api/admin/logout-user/{user_id}` | Admin 強制登出 |
| `PATCH /api/admin/user/{user_id}/active` | 停用/啟用帳號 |
| `DELETE /api/admin/user/{user_id}` | 刪除帳號 |
| `PATCH /api/admin/user/{user_id}/role` | 修改角色 |

### 前端實作

- Auth guard：未登入只顯示 login modal，不渲染主介面
- 改密碼 modal
- 登出 hover dropdown（登出 + 登出全部裝置）
- Admin org modal 擴充：角色切換、停用/啟用、強制登出、刪除

### 確認項目

- Multi-org session 隔離：已有（org_id filter 早已實作於 session_service）
- 強制登入：`/ask`、`/api/deep_research`、`/api/feedback` 從 PUBLIC_ENDPOINTS 移除

### 決策

- decisions.md #42：Transactional email 採 Resend + Cloudflare Email Routing

---

## ✅ Track AA：Zoe Plan Phase 2 — /delegate + /update-docs 擴充（2026-03-04）

**目標**：建立 Zoe 智慧派工 skill 與文件更新 skill 擴充。

### 主要修改

| 變更 | 說明 |
|------|------|
| `/delegate` skill | `.claude/commands/delegate.md` — 6 步驟派工流程 |
| `/update-docs` 擴充 | `.claude/commands/update-docs/SKILL.md` — 新增 decisions/patterns 參數、修正過時路徑 |
