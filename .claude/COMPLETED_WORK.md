# 已完成工作記錄

本文件包含已完成 tracks 的詳細實作歷史。僅在需要過去實作詳細上下文時參考。

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

*更新：2026-02-12*
