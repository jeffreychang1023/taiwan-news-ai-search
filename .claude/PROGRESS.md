# 進度日誌

## 最近里程碑

### 2026-02-15：Chinatimes 雙機協作 + Sitemap Date Filter 修復 ✅

**3 項改進**

1. **Chinatimes 雙機協作部署**
   - `engine.py` `run_sitemap()` 新增 `sitemap_offset` + `sitemap_count` 參數
   - `subprocess_runner.py` forward 新參數
   - `scripts/gcp-chinatimes-sitemap.sh` 自管理 long-running 腳本
   - GCP 從 sub-sitemap #980 往回跑，桌機從 #1 往前跑
   - 適應性批次大小：空區間 x3（max 200）、密集區 /2（min 5）
   - State file crash recovery、coverage 報告、PID file
   - 停止條件：距桌機 50 sub-sitemap 或連續 3 次 task failed

2. **Sitemap Date Filter Bug 修復**（`engine.py` `_filter_article_urls_by_date()`）
   - **根因**：Chinatimes lastmod 日期為 sitemap 重新產生日期（2024-02-27），不是文章發布日期
   - 2010 年文章的 lastmod=2024 → 通過 date_from=202401 filter → 錯誤爬取
   - **修復**：改為 URL 日期優先（從 URL 提取 YYYYMMDD），lastmod 僅作 fallback
   - 修復後測試：5 個 2010-era sub-sitemap 正確 exclude 全部 44,364 篇，0 new articles

3. **桌機 Chinatimes 重啟**
   - 停止舊 task（53K success, 298K skipped, 23 sitemaps）
   - 用 fixed code 重啟，已爬文章快速 skip（~30K/min）
   - GCP UDN Phase 2 + Retry 已全部完成

---

### 2026-02-13：LTN/CNA 完成 + GCP Phase 2 自動接力 + 監控 Agent 清理 ✅

**4 項改進**

1. **LTN/CNA 全量掃描完成**
   - LTN：693,273 篇，watermark 5,342,046（第一輪完成）
   - CNA：242,011 篇，watermark 2026-02-12（第一輪完成）
   - 桌機轉至 Chinatimes sitemap + einfo full_scan

2. **GCP Phase 2 自動接力腳本**（`scripts/gcp-udn-next.sh`）
   - 每 2 小時 cron 檢查 2025-03~07 月文章數 > 27K
   - 全部達標 → 自動 API 啟動 UDN sitemap 202401→202409
   - 觸發後自我從 cron 移除
   - 已部署至 GCP 並驗證（test script + cron 設定完成）

3. **監控 Agent 停止**
   - `scripts/crawler-monitor/monitor-loop.sh` 已停止
   - 該 Agent 曾 41 次重啟 UDN、19 次重啟 Dashboard（違反手動停止意圖）
   - monitoring-log.md 清理：59 次 check（268KB）→ 12 次有效 check（60KB）

4. **UDN 覆蓋規劃修正**
   - 確認 sitemap newest→oldest 處理順序
   - 三機 UDN 覆蓋：桌機 2025-08+（完成）→ GCP 2025-03~07（Phase 1）+ 2024-01~09（Phase 2）→ 筆電 2024-10~2025-02

---

### 2026-02-12（深夜）：GCP UDN Sitemap 啟動 + overrides Bug 修復 ✅

**3 項改進**

1. **GCP UDN sitemap 啟動**
   - 範圍 2025-03 → 2025-07（5 個月缺口）
   - 速率 ~150 篇/分鐘，hit rate 97%
   - GCP Dashboard 重啟（用 `/tmp/start-dash.sh` 腳本解決工作目錄問題）

2. **overrides 格式 bug 修復**（3 個檔案）
   - `dashboard_api.py` 完全不讀 `overrides` 欄位（0 references）
   - `start_id`/`end_id` 必須放 JSON body 最外層
   - 修復：`crawler-deployment-prompt.md`、`laptop-crawler-spec.md`、`gcp-crawler-spec.md`
   - 影響：MOEA 會掃 0 篇（watermark 122,001 > end 122,000）、einfo 範圍錯

3. **merge_registry.py 更新至 GCP**
   - 確認桌機版已有 `failed_urls` 合併邏輯（第 84-93 行）
   - GCP 版是舊的（tar 上傳時沒有此功能）→ scp 更新

---

### 2026-02-12（晚）：三機協作規劃 + merge_registry 強化 ✅

**3 項改進**

1. **三機分工規劃與部署文件**（`docs/crawler-deployment-prompt.md`）
   - 桌機：LTN/CNA/einfo 收尾 → 全力 Chinatimes
   - 筆電：MOEA backfill → UDN sitemap 202410→202502
   - GCP：UDN sitemap 202503→202507
   - 各 source 覆蓋缺口總覽、桌機 checkpoint 狀態

2. **merge_registry.py 支援 failed_urls**（`crawler/remote/merge_registry.py`）
   - `failed_urls` 表合併，排除本地已成功的 URL
   - 遠端機器的 transient failures 可統一收回桌機 retry

3. **Tasks 清理與重整**
   - 移除 UDN/Chinatimes/ESG_BT 歷史 tasks（57 筆）
   - Dashboard kill 導致 tasks.json 截斷 → 建立乾淨空檔案
   - Watermarks 完好無損（crawled_registry.db 不受影響）

---

### 2026-02-12：Dashboard 穩定性 + Watermark Skip Bug 修復 + Sitemap OOM 修復 ✅

**6 項重大修復**

1. **Watermark Skip Bug — Blocked (429) URLs 被誤跳過**（`engine.py`, `crawled_registry.py`）
   - **根因**：watermark skip 條件 `current_id <= watermark_id` 將所有低於 watermark 的 ID 視為「已掃描」
   - 但 HTTP 429 blocked URLs **從未被實際抓取**，不應被跳過
   - **影響**：全 7 source 共 4,581 blocked URLs（chinatimes 1,726, MOEA 1,411, CNA 866, einfo 332, UDN 97, LTN 81, ESG BT 69）
   - **修復**：`load_blocked_ids()` + `load_blocked_dates()` 從 `failed_urls` 載入 blocked ID/日期集合
   - Sequential skip: `current_id <= watermark AND current_id NOT IN blocked_ids`
   - Date-based skip: `current_day <= watermark AND current_day NOT IN blocked_dates`
   - **驗證**：MOEA 重掃 119K-122K 從 0 success（全跳過）→ 22 success / 40 processed = 55% hit rate

2. **stderr→file + Event Loop Starvation 修復**（`dashboard_api.py`）
   - **根因**：12 concurrent asyncio pipe readers（6 stdout + 6 stderr）搶佔 event loop，HTTP handlers 永遠排不到
   - **修復**：stderr 改為 file redirect（`stderr=stderr_log_file`），完全不經 event loop
   - Dashboard 穩定運行 4+ 小時、6 concurrent subprocesses，API 持續回應

3. **Adaptive Throttle Backoff Ceiling 修復**（`engine.py`）
   - **根因**：`_throttle_backoff()` 上限為 `max_delay`（MOEA=4.0s），429 反覆觸發但 delay 不再增加
   - **修復**：允許 backoff 至 `max_delay * 4`，`_adaptive_delay()` 尊重 elevated delay
   - MOEA 後續 tasks 全部 blocked=0

4. **Sitemap Incremental Processing — OOM 修復**（`engine.py`）
   - **根因**：`run_sitemap()` 下載所有 sub-sitemaps 後累積全部 URLs 到記憶體（chinatimes ~15M URLs → 870MB OOM）
   - **修復**：逐 sub-sitemap 處理（download → crawl → discard → next），記憶體 ~130MB

5. **Windows Pipe Hang on Force Kill**（`dashboard_api.py`）
   - **根因**：Windows `proc.kill()` 不會關閉 pipes，`async for line in proc.stdout` 永遠 hang
   - **修復**：`_force_kill_after()` 在 kill 後 cancel `task._reader_task`

6. **Qdrant Stats Non-blocking**（`dashboard_api.py`）
   - **根因**：`_get_qdrant_stats()` 用 sync QdrantClient 阻塞 event loop 5s
   - **修復**：`loop.run_in_executor()` 移至 thread pool

---

### 2026-02-12（早）：整夜監控 + stderr Pipe Buffer 修復 + Auto-Restart ✅

**3 項改進**

1. **stderr Pipe Buffer 死鎖修復**（`dashboard_api.py`）
   - **根因**：`_run_crawler_subprocess()` 用 `stderr=asyncio.subprocess.PIPE` 但從未讀取
   - 快速爬蟲填滿 Windows 65KB pipe buffer → subprocess 阻塞 → 計數器凍結
   - 整夜發生 9 次凍結，第 8 次 check 找到 root cause
   - **修復**：新增 `_drain_stderr()` async task 與 stdout reader 同時運行
   - 修復後 72+ 分鐘零凍結（後續進一步改為 stderr→file redirect）

2. **MOEA Auto-Restart 機制**（`dashboard_api.py`）
   - `AUTO_RESTART_DELAY = {"moea": 900}` — early_stop 後 15 分鐘自動重啟
   - `_delayed_restart()`: 等待 → 檢查無同 source running → `_auto_resume_task()`
   - 解決 MOEA 因 rate limit early_stop 後需手動重啟的問題

3. **自動化監控迴圈**（`scripts/crawler-monitor/`）
   - `monitor-loop.sh`: 外部 bash loop，每 30 分鐘啟動新 Claude CLI session
   - `monitoring-plan.md`: 356 行完整 prompt（角色定義、6 source 參考、異常規則、修復流程）
   - `monitoring-log.md`: 持久化 log（12 次 check，01:04→09:48）
   - ESG BT backfill 確認完成

---

### 2026-02-11：Dashboard Bug Fixes + Full Scan 穩定性 ✅

**4 項修復**

1. **MOEA 429 Rate Limiting 修復**（`settings.py`）
   - `FULL_SCAN_OVERRIDES["moea"]`: concurrent 5→2, delay (0.5-1.5)→(2.0-4.0)s, timeout 8→10s
   - 修復後 MOEA 成功 crawl（ok=8+），不再被封鎖

2. **`null -> null` 顯示 Bug 修復**（3 層修復）
   - `dashboard_api.py` `start_crawler`: 當 mode=="full_scan" 時初始化 `scan_start`/`scan_end`
   - `dashboard_api.py` progress handler: 從 engine stats backfill `scan_start`/`scan_end`
   - `engine.py` `_reset_stats()`: 在 `_full_scan_sequential` 和 `_full_scan_date_based` 加入 `scan_start`/`scan_end`
   - 根因：`start_crawler` endpoint（通用）未像 `start_full_scan`（專用）一樣初始化掃描範圍

3. **Task Cleanup**
   - 124 筆累積 tasks → 13 筆（每個 source 保留 2 筆最新）
   - 防止 auto-resume 再膨脹：cleanup 時已將 running→failed，不觸發 auto-resume

4. **indexing-spec.md 全面更新**
   - MOEA session type AIOHTTP→CURL_CFFI
   - UDN scan method 加入 sitemap（推薦）+ hit rate 對比
   - 新增 Sitemap Mode 完整文件
   - 新增 CURL_CFFI_SOURCES 設定文件
   - 新增 MOEA 到 NEWS_SOURCES

---

### 2026-02-11：UDN Sitemap Backfill + curl_cffi Reward Hack 清理 + Qdrant Profile ✅

**3 項重大改進**

1. **UDN Sitemap Backfill 串接**
   - `subprocess_runner.py` 新增 `elif mode == "sitemap":` 分支
   - `dashboard_api.py` ALLOWED_MODES 加入 `"sitemap"`
   - `engine.py` run_sitemap/run_list_page 的 batch 迴圈加入 `self.stats['progress']` 更新
   - UDN sitemap 命中率 100%（vs full_scan 6%），backfill 效率大幅提升

2. **curl_cffi Reward Hack 清理**（系統性修復）
   - **根因**：engine `_create_session()` curl_cffi 不可用時 silent fallback 到 aiohttp
   - **連鎖問題**：4 個 parser 加了 `getattr(response, 'status_code', None) or getattr(response, 'status', 0)` 兼容 shim 掩蓋問題
   - **修正 1**：engine fail fast — `raise RuntimeError` 取代 silent fallback
   - **修正 2**：移除 cna/chinatimes/einfo/esg_bt 所有兼容 shim，直接用 curl_cffi API
   - **修正 3**：`settings.py` CURL_CFFI_SOURCES 加入 `moea`（之前漏了）
   - **修正 4**：`_create_session()` CurlSession 建立 dead code bug（code simplifier 發現）
   - **原則**：parser 宣告 curl_cffi → settings 必須列入 → engine 必須提供 → 缺了就炸

3. **Qdrant Profile 切換系統**
   - `QDRANT_PROFILE=online|offline` 環境變數
   - Profiles: `config/config_qdrant_profiles.yaml`
   - Manager: `core/qdrant_profile.py`（load → validate dimension → overlay CONFIG）
   - Dimension validation at startup via sync QdrantClient

4. **全量 Backfill 啟動**（7 source，2024-02 起）
   - UDN: sitemap, LTN/einfo/MOEA: full_scan sequential, CNA/chinatimes/ESG BT: full_scan date-based
   - Watermark reset for ESG BT（was stuck at 2026-02-13）, einfo, MOEA

---

### 2026-02-10：Crawler 效能與 Dashboard 非阻塞優化 ✅

**run_auto 批次並行 + Dashboard async 反模式修復**

1. **run_auto 批次並行**（`engine.py`）
   - 從 sequential（一次一篇，~26 req/min）改為 semaphore+gather 批次並行（~100+ req/min）
   - 保留 consecutive_skips 和 date_floor 邏輯，在 pre-filter 階段追蹤
   - batch_size = concurrent_limit * 5，UDN 預設 concurrent=5

2. **Dashboard watermark 顯示修正**（`indexing-dashboard.html`）
   - 移除 `updated_at` 日期顯示，避免 sequential source 誤導為 date-based

3. **start_full_scan auto-detect 並行化**（`dashboard_api.py`）
   - 抽出 `_detect_latest_id()` helper，3 個 sequential source 的 `get_latest_id` 用 `asyncio.gather` 並行
   - 從 ~30s 降到 ~10s

4. **schedule_auto_resume 並行化**（`dashboard_api.py`）
   - zombie task resume 從串列改為 `asyncio.gather`

5. **WebSocket broadcast 並行化**（`dashboard_api.py`）
   - 多 client 廣播從逐個 await 改為 `asyncio.gather`

6. **_save_tasks 非阻塞化**（`dashboard_api.py`）
   - JSON 序列化在主線程，`run_in_executor` 背景寫檔
   - start_full_scan 中 per-task save 合併為一次

---

### 2026-02-10：UIUX 修改（B+C 類 7 項 + A 類 3 項）✅

**與設計師討論後的 10 項 UI/UX 改進**

**A 類（簡單修改）**：
1. **#2 全選按鈕改國字**（`news-search-prototype.html`）— SVG icon → 文字「全選」
2. **#4 大字體模式影響 Deep Research**（`news-search.css`）— 新增 `.large-font` 下研究報告字體規則
3. **#14 包含文件自動開右面板**（`news-search.js`）— `togglePrivateSources()` 勾選時 `openTab('files')`

**B 類（中等修改）**：
4. **#1 Deep Research 輸入框移到聊天區底部**（`news-search.js`）— 與 Chat 模式相同，`searchContainer` 移至 `chatInputContainer`
5. **#3 展開/折疊合併為單一 Toggle**（`news-search.js`）— `addToggleAllToolbar()` 改為單按鈕切換「全部折疊/全部展開」
6. **#5+#6 English labels 改中文**（`deep_research.py`, `orchestrator.py`, `writer.py`）— mode/confidence/feedback 標籤全部中文化
7. **#8 進度感簡化**（`news-search.js`）— 標題改「深度研究進行中」，移除 `.log-detail` 技術細節
8. **#11 參考資料 toggle**（`news-search.js` + `news-search.css`）— 引用列表改為可折疊（預設折疊），顯示 Title + 完整 URL
9. **#13 Session 隔離驗證** — 確認 `currentResearchReport` 已正確 save/load/switch，無需修改

**已用 DevTools 測試通過**：#2, #14, #1（三模式切換）

---

### 2026-02-10：Code Review 修復 + C3 Qdrant UUID5 遷移 ✅

**3 項 review fix + Point ID 安全性修復**

1. **CancelledError unpack 修復**（`engine.py`）
   - `_evaluate_batch_results()`: `isinstance(result, Exception)` → `BaseException`
   - Python 3.9+ `CancelledError` 繼承 `BaseException`，stop 時 gather 回傳被漏判

2. **`_ensure_date()` log 改善**（`engine.py`）
   - 新增 `url` 參數，warning 時標明被丟棄的文章 URL

3. **`_adaptive_delay()` jitter 上限 clamp**（`engine.py`）
   - `actual` 加 `min(actual, self.max_delay)`，防止 jitter 微超 max_delay

4. **C3 Qdrant Point ID → UUID5**（`qdrant_uploader.py`）
   - MD5 截斷 64-bit int → `uuid.uuid5()` string（SHA-1 based, 128-bit）
   - Qdrant 目前無資料，直接改零成本，未來不再有碰撞風險

---

### 2026-02-10：Scrapy/Trafilatura 最佳模式整合 ✅

**Engine 層級 4 項增強：AutoThrottle、htmldate fallback、trafilatura fallback、latency 追蹤**

1. **AutoThrottle**（`engine.py` + `settings.py`）
   - Scrapy 風格自適應延遲：`new_delay = (old_delay + avg_latency/target_concurrency) / 2`
   - 取代固定 `random.uniform(min_delay, max_delay)`，4 個呼叫點全部替換
   - 錯誤回應自動 `_throttle_backoff()` 加倍 delay
   - `AUTOTHROTTLE_ENABLED` 開關可隨時回退

2. **htmldate 通用 Fallback**（`engine.py`）
   - `_ensure_date(data, html)`: parser 漏掉 datePublished 時自動補全
   - 3 個 parse 成功路徑全部加入（primary URL、404 candidate、parse-failed candidate）
   - 無日期 → 丟棄文章（避免無日期資料進入系統）

3. **Trafilatura 通用 Fallback**（`engine.py`）
   - `_trafilatura_fallback(html, url)`: custom parser 回傳 None 後最後嘗試
   - `bare_extraction(favor_precision=True)` + MIN_ARTICLE_LENGTH 品質檢查
   - `stats['trafilatura_fallbacks']` 計數器追蹤勝率
   - 標記 `_source: "trafilatura_fallback"` 便於溯源

4. **Response Latency 追蹤**（`engine.py`）
   - rolling window 50 筆 `_latencies`，`_avg_latency` 滾動平均
   - `_fetch()` HTTP 請求前後包 `time.monotonic()` 計時
   - `_report_progress()` 回報 `stats['avg_latency']` 和 `stats['current_delay']`

---

### 2026-02-10：Crawler Fixes & Dashboard Enhancement ✅

**三項修復：UTF-8 decode、tasks 清理、Clear by Error Type**

1. **UTF-8 Decode Error 修復**（`crawler/core/engine.py`）
   - curl_cffi `response.text` 在 Big5/cp950 content 時拋 UnicodeDecodeError
   - 新增 try/except，fallback 到 `response.content.decode('utf-8', errors='replace')`
   - 修復 CNA/einfo subprocess 因 cp950 content 崩潰的問題

2. **Tasks.json 清理**
   - 140 筆累積任務（71% failed）→ 3 筆（zombie tasks 標記 failed）
   - `crawled_registry.db`（393K articles）不受影響，去重機制正常

3. **Dashboard Clear by Error Type**
   - `crawled_registry.py` `clear_failed()`: 新增 `error_types` 參數，使用 parameterized SQL IN clause
   - `dashboard_api.py` `clear_errors()`: 接收並傳遞 `error_types`
   - `indexing-dashboard.html` `clearErrors()`: 與 `retryAllErrors()` 對齊，使用相同的 `getSelectedErrorTypes()` 過濾邏輯

---

### 2026-02-09：Subprocess Per Crawler（B1）✅

**Crawler 進程隔離 — 每個 crawler 獨立 subprocess，真正 GIL 隔離**

1. **Subprocess Runner**（`crawler/subprocess_runner.py`）
   - 新檔案，作為 subprocess 入口點
   - 接收 CLI 參數（--params JSON, --task-id, --signal-dir）
   - All logging → stderr, JSON protocol → stdout
   - 支援所有 5 種 mode: full_scan, auto, list_page, retry, retry_urls

2. **Dashboard API 改造**（`indexing/dashboard_api.py`）
   - `_run_crawler_subprocess()`: 用 `asyncio.create_subprocess_exec()` 啟動 crawler
   - 讀取 subprocess stdout JSON lines 更新 task 狀態
   - 7 個啟動點全部改用 subprocess
   - 舊 `_run_crawler()` 保留為 `_run_crawler_inprocess()` fallback

3. **Engine stop_check**（`crawler/core/engine.py`）
   - `__init__` 新增 `stop_check: Optional[Callable[[], bool]]` 參數
   - `_report_progress()` 檢查 `stop_check()` → `raise CancelledError`

4. **Stop Mechanism**
   - Signal file: `data/crawler/signals/.stop_{task_id}`
   - 10 秒 graceful shutdown timeout → `proc.terminate()` fallback

5. **Chinatimes 設定同步**
   - `dashboard_api.py` FULL_SCAN_CONFIG 新增 chinatimes
   - `settings.py` FULL_SCAN_OVERRIDES 新增 chinatimes（concurrent=6, delay=0.3-0.8s）

6. **Windows UnicodeDecodeError 修復**
   - `subprocess_runner.py` patch `CrawlerEngine._setup_logger` 將 StreamHandler 重導到 stderr
   - `dashboard_api.py` stdout 解碼加 `errors="replace"` 防禦
   - 根因：Windows cp950 編碼的中文 log 輸出到 stdout 破壞 JSON protocol

7. **Zombie/Orphan Subprocess 清理**
   - `CrawlerTask._pid` 欄位 + `_task_to_dict()` 持久化 PID
   - `_load_tasks()` 重啟時 3 步清理：signal file → taskkill/SIGTERM → mark failed
   - `_kill_orphan_process()` 靜態方法（Windows: `taskkill /F /PID`, Unix: `SIGTERM`）
   - Auto-resume 從 checkpoint 續跑，不會產生重複 crawler

---

### 2026-02-04：E2E 驗證與搜尋模式優化 ✅

**MCP Wrapper 與 E2E 測試基礎設施**

1. **MCP Wrapper 實作**
   - 統一的 Model Context Protocol 封裝
   - 支援多種 LLM 後端

2. **Streaming 改進**
   - SSE 串流效能優化
   - 前端接收處理修復

3. **E2E 測試框架**
   - 端到端測試基礎設施建立
   - 整合測試覆蓋

**Search Mode 大規模優化**

1. **統一搜尋 UX 重構**
   - 搜尋模式統一化
   - 前端 UI/UX 改進
   - 多項 Bug 修復

2. **Qdrant 連線修復**
   - 修復遠端連線逾時問題
   - 改善連線穩定性

---

### 2026-01-28：M0 Indexing 資料工廠完成 ✅

**完整 Data Pipeline：Crawler → Indexing → Storage**

#### Crawler 系統

**7 個 Parser 實作**：
| Parser | 來源 | 爬取模式 | HTTP Client |
|--------|------|----------|-------------|
| `ltn` | 自由時報 | Sequential ID | AIOHTTP |
| `udn` | 聯合報 | Sequential ID | AIOHTTP |
| `cna` | 中央社 | Date-based ID | CURL_CFFI |
| `moea` | 經濟部 | Sequential ID | CURL_CFFI |
| `einfo` | 環境資訊中心 | Sequential ID | CURL_CFFI |
| `esg_businesstoday` | 今周刊 ESG | Date-based ID | CURL_CFFI |
| `chinatimes` | 中國時報 | Date-based ID (14位) | CURL_CFFI |

**核心模組**（`code/python/crawler/`）：
- `core/engine.py` - 爬蟲引擎
- `core/interfaces.py` - 抽象介面
- `core/pipeline.py` - 處理管線
- `core/settings.py` - 配置常數
- `parsers/factory.py` - Parser 工廠

**特色**：
- Binary Search 自動偵測最新 ID（einfo）
- Sitemap 模式批量取得（esg_businesstoday）
- 34 個單元測試 + E2E 測試
- 完整文件（`docs/indexing-spec.md`）

**CLI**：
```bash
python -m crawler.main --source ltn --auto-latest --count 100
```

#### Indexing Pipeline

**模組**（`code/python/indexing/`）：
- `source_manager.py` - 來源分級（Tier 1-4）
- `ingestion_engine.py` - TSV → CDM 解析
- `quality_gate.py` - 品質驗證
- `chunking_engine.py` - 170 字/chunk + Extractive Summary
- `dual_storage.py` - SQLite + Zstd 壓縮
- `rollback_manager.py` - 遷移記錄、備份
- `pipeline.py` - 主流程 + 斷點續傳
- `vault_helpers.py` - Async 介面

**CLI**：
```bash
python -m indexing.pipeline data.tsv --site udn --resume
```

---

### 2026-01-28：M0 Indexing Module 完成 ✅

**Phase 1：核心基礎設施**
- `config/config_indexing.yaml` - 完整配置
- `SourceManager` - 來源分級（Tier 1-4）

**Phase 2：Data Flow**
- `IngestionEngine` - TSV → CDM 解析
- `QualityGate` - 品質驗證（長度、HTML、中文比例）
- `ChunkingEngine` - 170 字/chunk + Extractive Summary

**Phase 3：Storage & Safety**
- `VaultStorage` - SQLite + Zstd 壓縮（線程安全）
- `RollbackManager` - 遷移記錄、payload 備份
- `IndexingPipeline` - 主流程 + 斷點續傳
- `MapPayload` - Qdrant payload 結構（version 2）

**Phase 4：Integration**
- `vault_helpers.py` - Async 介面
  - `get_full_text_for_chunk(chunk_id)` - 取得 chunk 原文
  - `get_full_article_text(article_url)` - 取得整篇文章
  - `get_chunk_metadata(chunk_id)` - 解析 chunk ID

**CLI**：`python -m indexing.pipeline data.tsv --site udn --resume`

---

### 2026-01-28：Free Conversation Mode + CoV ✅

**Reasoning 系統重大強化**

1. **Free Conversation Mode**
   - 注入之前的 Deep Research 報告進行後續 Q&A
   - 支援多輪對話延續研究上下文
   - 實作於 `methods/generate_answer.py`

2. **Phase 2 CoV（Chain of Verification）**
   - 事實查核機制整合於 Critic Agent
   - 驗證 Analyst 輸出的事實準確性
   - 實作於 `reasoning/agents/critic.py`、`reasoning/prompts/cov.py`

---

### 2026-01：Tier 6 API 整合 ✅

**知識增強 API 已部署**

為 Gap Resolution 新增外部 API 整合：
- Stock APIs（Yahoo Finance Taiwan/Global）
- Weather APIs
- Wikipedia API
- Web Search（Bing/Google）
- LLM Knowledge

---

### 2025-12：Reasoning 系統完成 ✅

**Deep Research 與多 Agent 系統完整部署**

1. **Reasoning Orchestrator**（`reasoning/orchestrator.py`）
   - Actor-Critic 迴圈（max 3 iterations）
   - 多階段管道：Filter → Analyst → Critic → Writer
   - 幻覺防護（writer sources ⊆ analyst sources）
   - 統一上下文格式化
   - 優雅降級

2. **多 Agent 系統**
   - **Analyst Agent**：研究與合成、引用追蹤
   - **Critic Agent**：品質審查 + gap 偵測
   - **Writer Agent**：最終格式化與 markdown 引用
   - **Clarification Agent**：歧義偵測與問題生成
   - **Base Agent**：重試邏輯、超時處理、Pydantic 驗證

3. **來源分層過濾**
   - 3 模式：strict（tier 1-2）、discovery（tier 1-5）、monitor（1 vs 5）
   - 10 個來源知識庫（中央社、公視、聯合報等）

4. **時間範圍抽取**
   - 3 層解析：Regex → LLM → Keyword fallback
   - 絕對日期轉換

5. **Deep Research Method**
   - 與 NLWeb 搜尋管道整合
   - SSE 串流支援
   - 引用連結

6. **除錯工具**
   - ConsoleTracer：即時事件視覺化
   - IterationLogger：JSON 事件流日誌

---

### 2025-12：XGBoost Phase C 完成 ✅

**ML Ranking 完整部署**

1. **Phase A：基礎設施** ✅
   - Feature engineering 模組
   - XGBoost ranker 模組
   - 訓練管道

2. **Phase B：訓練管道** ✅
   - Binary classification trainer
   - LambdaMART trainer
   - XGBRanker trainer
   - 模型評估（NDCG@10, Precision@10, MAP）

3. **Phase C：Production 部署** ✅
   - 與 `core/ranking.py` 整合（LLM → XGBoost → MMR）
   - Shadow mode 驗證
   - 模型 registry 與版本控制

**關鍵功能**：
- 29 features 從 analytics schema
- XGBoost 使用 LLM 分數作為 features
- Global model caching
- Confidence score 計算

---

### 2025-11：Analytics 基礎設施完成 ✅

1. **資料庫 Schema v2**
   - PostgreSQL via Neon.tech
   - 4 核心表 + 1 ML feature 表
   - Parent Query ID 欄位

2. **Foreign Key 完整性**
   - 修復 async queue race condition
   - log_query_start() 改為同步
   - 解決所有 foreign key 違規

3. **多點擊追蹤**
   - 左、中、右鍵支援
   - auxclick 和 contextmenu 事件監聽

4. **Batch 事件處理**
   - result_clicked 加入 batch handler
   - Decimal JSON 序列化修復

---

## 部署歷史

| 日期 | 版本 | 說明 | 狀態 |
|------|------|------|------|
| 2026-02 | Crawler v2.0 | 三機協作 + Subprocess 隔離 + Dashboard | ✅ 已部署 |
| 2026-01 | Tier 6 API | Knowledge Enrichment APIs | ✅ 已部署 |
| 2025-12 | Reasoning v1.0 | Actor-Critic + 4 Agents | ✅ 已部署 |
| 2025-12 | XGBoost v1.0 | ML Ranking Phase C | ✅ 已部署 |
| 2025-11 | Analytics v2.0 | Parent Query ID + 多點擊 | ✅ 已部署 |

**完整已完成 Track 記錄**：見 `.claude/COMPLETED_WORK.md`

---

*更新：2026-02-23*
