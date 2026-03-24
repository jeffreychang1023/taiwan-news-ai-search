---
name: Crawler 技術教訓
description: Crawler engine、parser、registry、dashboard 相關的除錯經驗與技術陷阱。Crawler 或 Dashboard 除錯時必讀。
type: feedback
---

> 通用除錯哲學（Silent fail 防範、API 重試等）見 `lessons-general.md`。遭遇未知成因 Bug 時，優先閱讀 general。

## Infrastructure

### Full Scan Blocked Limit 太敏感導致 einfo/chinatimes 提早停止
**問題**：`BLOCKED_CONSECUTIVE_LIMIT=5` 是為 auto mode 設計的，但 full scan 模式下遇到短暫封鎖（如 chinatimes 的 CloudFlare、einfo 的速率限制）很容易連續觸發 5 次就停止，導致掃描無法完成。
**解決方案**：區分 full scan 和 normal mode 的 blocked limit。新增 `FULL_SCAN_BLOCKED_LIMIT=50` 和 `FULL_SCAN_BLOCKED_COOLDOWN=120s`。engine 用 `self._full_scan_mode` flag 在 `_check_blocked_stop()` 和 cooldown 處切換。
**信心**：中
**檔案**：`crawler/core/settings.py`, `crawler/core/engine.py`
**日期**：2026-02

### LTN Full Scan 因 Candidate URLs 過多導致低 throughput
**問題**：LTN 有 15+ 個 category candidate URLs，每個 404 都要嘗試所有 candidate，導致 full scan throughput 僅 ~0.7 req/s。
**解決方案**：在 `FULL_SCAN_OVERRIDES` 各 source 加 `max_candidate_urls` 設定，`_process_article()` 兩處 candidate URL loop 加入 slice 限制。LTN 限制為 3，chinatimes 限制為 2，UDN/CNA/einfo/ESG BT 設為 0（不需要 candidate）。
**信心**：中
**檔案**：`crawler/core/settings.py`, `crawler/core/engine.py`
**日期**：2026-02

### Early return 遮蔽初始化邏輯 — skip 資料載入被 overrides 檢查跳過
**問題**：`_apply_full_scan_overrides()` 在頂部有 `if not overrides: return`。將 watermark 和 not_found_ids 載入邏輯放在 return 之後，導致沒有 `FULL_SCAN_OVERRIDES` 的 source 完全不會載入 skip 資料，三層加速機制靜默失效。Code review 才發現。
**解決方案**：將 skip 資料載入（watermark + not_found_ids + `_full_scan_mode = True`）移到 early return 之前。通則：**初始化邏輯不應依賴可選配置的存在**。
**信心**：高
**檔案**：`crawler/core/engine.py`
**日期**：2026-02

### 用既有 Watermark 推斷 404 — 免等新 table 累積即刻生效
**問題**：新增 `not_found_articles` 表記錄 404，但第一輪掃描才開始累積資料，需跑完一輪+重啟才有加速效果。
**解決方案**：既有的 `scan_watermarks.last_scanned_id` 已表示「掃到哪」。低於 watermark 且不在 crawled_ids 的 ID = 上一輪掃過但沒成功 → 直接跳過。Sequential 用 `current_id <= watermark_id`（O(1)），Date-based 用 `current_day <= watermark_date` 整天跳過。重啟後第一輪就生效，不需等 not_found 表累積。
**信心**：中（邏輯正確但尚未在 production 長時間驗證）
**檔案**：`crawler/core/engine.py`, `crawler/core/crawled_registry.py`
**日期**：2026-02

### SQLite INSERT 不 commit 會長期持有 write lock — 多 subprocess 必爆 "database is locked"
**問題**：`mark_not_found()` 做 `conn.execute(INSERT)` 但不 commit，等 batch 結束才由 `flush_not_found()` commit。在 SQLite WAL mode 下，INSERT 就開始 write transaction，其他 subprocess 的寫入會被阻塞。6 個 subprocess 同時掃描，先拿到鎖的 process 佔住整個 batch 時間（幾十秒），其他 process 等 30 秒 timeout 後 `database is locked` 失敗。
**解決方案**：改為記憶體 buffer pattern：`mark_not_found()` 只 append 到 `List[tuple]`，`flush_not_found()` 用 `executemany()` + `commit()` 一次寫入。Write lock 從「整個 batch 時間」降為「毫秒級」。**通則：多 process 共用 SQLite 時，write transaction 必須盡可能短，絕不能跨越 async 等待。**
**信心**：高（production 驗證）
**檔案**：`crawler/core/crawled_registry.py`
**日期**：2026-02

### Resume 與 Watermark Skip 語意重疊 — 正常 resume 不會觸發 watermark skip
**問題**：實作三層 404 skip 後，重啟 full scan 發現 skip 數量沒有明顯增加。調查後發現：Dashboard resume 已經將 `start_id` 設為 `last_scanned_id + 1`，而 watermark skip 的條件是 `current_id <= watermark_id`。因為 `start_id = watermark + 1`，所以 watermark skip 永遠不觸發。
**解決方案**：這不是 bug，是兩個機制的語意重疊。Resume 處理「從上次停的地方繼續」，Watermark skip 處理「手動從頭重掃已覆蓋範圍」。兩者互補不衝突。設計優化時要區分：哪些情境已被既有機制覆蓋，新機制的增量價值在哪。
**信心**：高
**檔案**：`crawler/core/engine.py`, `indexing/dashboard_api.py`
**日期**：2026-02

### QdrantClient 不支援 context manager — 維度驗證被靜默跳過
**問題**：Code simplifier 將 `client = QdrantClient(...)` 改為 `with QdrantClient(...) as client:`，但 qdrant-client (本專案版本) 的 sync client 不支援 context manager protocol。`'QdrantClient' object does not support the context manager protocol` 被外層 `except Exception` 捕獲，導致維度驗證**整段被跳過**，log 只有一行 warning。維度不符的致命錯誤變成 silent pass。
**解決方案**：改用 `try/finally` + `client.close()` 確保資源釋放。**通則：`except Exception` 廣捕獲容易吞掉結構性錯誤，只應用於真正可容忍的失敗（如網路不可達），不應包含 client 初始化。** 測試時要驗證 log 中有 "Dimension check OK" 而非 "Could not validate"。
**信心**：高（production 驗證，log 確認）
**檔案**：`core/qdrant_profile.py`
**日期**：2026-02

### Profile Overlay Pattern — 多 Qdrant 實例安全切換
**問題**：Indexing 和 Query 系統各自獨立設定 Qdrant（不同 collection、不同 embedding 維度、不同設定來源），手動切換容易造成維度不符或 collection 錯誤。
**解決方案**：Profile overlay pattern：`QDRANT_PROFILE` env var → 在 `AppConfig.__init__()` 最後載入 profile YAML → 覆蓋 `preferred_embedding_provider`、`write_endpoint`、endpoint 的 `index_name`。Indexing 側 `QdrantConfig.from_env()` 和 `embedding.py` 都透過 `get_active_profile()` 路由。啟動時用 sync client 驗證 collection 維度。不設定時為 no-op（向後相容）。
**信心**：中（第一次實作，測試通過但尚未 production 驗證）
**檔案**：`core/qdrant_profile.py`, `config/config_qdrant_profiles.yaml`, `indexing/embedding.py`, `indexing/qdrant_uploader.py`
**日期**：2026-02

### trafilatura 2.0 breaking change — bare_extraction 回傳 Document 非 dict
**問題**：trafilatura 2.0 的 `bare_extraction()` 回傳型別從 `dict` 改為 `Document` 物件。`Document` 沒有 `.get()` method，呼叫 `result.get('title')` 直接拋 `'Document' object has no attribute 'get'`。因為這個錯誤發生在 engine 的 `_trafilatura_fallback()` 中，被外層 `except Exception` 捕獲記錄為 `parse_exception`，所有走到 trafilatura fallback 的文章都被標記為失敗。einfo parser 已經用 `doc.title` 屬性存取所以不受影響。
**解決方案**：在 `_trafilatura_fallback()` 中加入 `if hasattr(result, 'as_dict'): result = result.as_dict()`。`Document` 有 `.as_dict()` 方法可轉回 dict，向前相容舊版本（dict 沒有 `as_dict`）。**通則：第三方套件大版本升級（1.x→2.0）的回傳型別改變是常見破壞源，尤其是從 dict 改為 dataclass/NamedTuple/custom object。**
**信心**：高（production 驗證，MOEA fail rate 從 70% 降到 ~40%）
**檔案**：`crawler/core/engine.py`（`_trafilatura_fallback` method）
**日期**：2026-02

### Dashboard auto-resume 造成 task 無限膨脹
**問題**：每次 dashboard 重啟，`_load_tasks()` 將 running 的 task 標記為 failed 並加入 `_pending_auto_resume`。`schedule_auto_resume()` 為每個 zombie task 建立新 task。清理 tasks.json 後重啟 → zombie detection → auto-resume → 又產生新 task → 反覆膨脹。124 筆 tasks 清到 20 筆，重啟後又長回來。
**解決方案**：清理 tasks 時同時將 status 改為 `failed`（不是保持 `running`），因為 auto-resume 只觸發於 `_load_tasks()` 讀到 `RUNNING`/`STOPPING` 狀態的 task。先殺 dashboard → 改 JSON 中的 status → 再重啟，auto-resume 就不會觸發。之後手動用 API 重啟需要的 full_scan。
**信心**：高（驗證 3 次重啟循環）
**檔案**：`indexing/dashboard_api.py`（`_load_tasks`, `schedule_auto_resume`）
**日期**：2026-02

### 兩個 API endpoint 做同一件事但初始化邏輯不同步
**問題**：`start_crawler`（通用 endpoint）和 `start_full_scan`（專用 endpoint）都能啟動 full_scan mode 的 crawler，但 `start_full_scan` 會初始化 `scan_start`/`scan_end`（顯示掃描範圍），`start_crawler` 不會 → Dashboard 顯示 `null -> null`。
**解決方案**：(1) `start_crawler` 加入 `if mode == "full_scan": 初始化 scan_start/scan_end`。(2) progress handler backfill：從 engine stats 補填缺失的 scan 範圍。(3) engine `_reset_stats()` 加入 scan_start/scan_end。三層防禦確保無論從哪個 endpoint 進來都正確。**通則：同功能多入口（REST 常見）必須確保共享初始化邏輯，或集中到一個 helper。**
**信心**：高
**檔案**：`indexing/dashboard_api.py`, `crawler/core/engine.py`
**日期**：2026-02

## 開發環境 / 工具

### Dashboard Server 入口點是 dashboard_server.py 不是 dashboard_api.py
**問題**：Dashboard server 啟動指令是 `python -m indexing.dashboard_server`（不是 `dashboard_api`）。`dashboard_api.py` 只有 API handler 和 `setup_routes()`，沒有 `__main__` block。`dashboard_server.py` 才有 `create_app()` + `web.run_app()` + CORS middleware + static files。
**解決方案**：記住正確入口：`python -m indexing.dashboard_server`（port 8001）。
**信心**：高
**檔案**：`indexing/dashboard_server.py`, `indexing/dashboard_api.py`
**日期**：2026-02

### asyncio Subprocess Pipe Readers 導致 Event Loop Starvation
**問題**：Dashboard 同時管理 6 個 subprocess，每個都有 stdout + stderr pipe reader（`async for line in proc.stdout/stderr`）。Windows ProactorEventLoop 下，12 個 pipe reader 持續有數據可讀時，HTTP handler 永遠排不到執行，API endpoint 全部 timeout。stderr 特別嚴重：每個 subprocess 的 logging 全部走 stderr，每秒數百行。`await asyncio.sleep(0)` 不夠（只 yield 到下一個 ready task，通常又是 pipe reader）。
**解決方案**：stderr 改用 file redirect（`stderr=stderr_log_file`）而非 `asyncio.subprocess.PIPE`。完全不經過 event loop。只保留 stdout pipe（JSON protocol，每秒 1 行/subprocess，可控）。Dashboard 從 12 concurrent pipe readers 降為 6，且全部是低頻。
**信心**：高（production 驗證，dashboard 穩定回應 API）
**檔案**：`indexing/dashboard_api.py`（`_run_crawler_subprocess`）
**日期**：2026-02

### Sitemap Crawler OOM — 15M URLs 全部累積在記憶體
**問題**：`engine.run_sitemap()` 先下載所有 1000 個 sub-sitemap，從每個提取 URL 全部 `extend()` 到 `total_urls_to_crawl` list，再一次性爬取。Chinatimes 有 ~15M URLs，光 URL 字串就 >1GB → OOM（870MB 後 crash）。
**解決方案**：重構為 incremental processing — 下載一個 sub-sitemap，立即爬取其 URL，完成後丟棄、下載下一個。記憶體只需容納一個 sub-sitemap 的 URL（~15K 條，約 1.2MB）。
**信心**：高（production 驗證，chinatimes sitemap 穩定運行，記憶體 ~130MB）
**檔案**：`crawler/core/engine.py`（`run_sitemap`）
**日期**：2026-02

### ~~Chinatimes `realtimenews` 是萬用路徑~~ **已推翻 (2026-02-23)**
**原結論**：`realtimenews/{id}-260402` 可存取所有 category 文章。`max_candidate_urls=0`。
**推翻驗證**：同 100 篇已知文章，`260402` 只有 12-16% 命中，**正確 category** 100% 命中。`?chdtv` 參數無影響。260402 只能打到 category 恰好是 260402 的文章（~13% 佔比）。
**根因**：原測試可能只驗證了同一 category 的文章，或 chinatimes 後來改了 URL routing。
**正確做法**：Full scan 必須嘗試多個 category code。136 個唯一 category，top 40 覆蓋 95.6%（不是之前誤記的 top 6=96.6%）。`max_candidate_urls=39`，parser `REALTIMENEWS_CATEGORY_CODES` 列出 top 40。
**影響**：full_scan 從 ~3K/月（只用 260402）預計提升到 ~18K+/月。
**信心**：高（2026-02-23 A/B/C/D 四組對照測試，30 篇 + 100 篇驗證）
**檔案**：`crawler/core/settings.py`, `crawler/parsers/chinatimes_parser.py`
**日期**：2026-02-23

### Watermark Skip 誤殺 Blocked (429) IDs — 重掃 3001 筆全部跳過
**問題**：Full scan 的三層 skip 最佳化中，watermark skip 條件為 `current_id <= self._watermark_id`，會跳過所有低於 watermark 的 ID。但 HTTP 429（blocked）的 ID **從未被實際抓取**，它們被記錄在 `failed_urls` 表中，不在 `crawled_articles` 也不在 `not_found_articles`。啟動針對 119K-122K 的重掃時，watermark 已在 122,000，所有 3,001 筆 ID 在 0.5 秒內被全部跳過，success=0。
**解決方案**：(1) `CrawledRegistry` 新增 `load_blocked_ids(source_id)` 從 `failed_urls WHERE error_type='blocked'` 提取 ID set。(2) `engine._apply_full_scan_overrides()` 載入 `self._blocked_ids`。(3) Skip 條件加入排除：`current_id <= watermark AND current_id not in self._blocked_ids`。修復後重掃立即恢復：22 success / 40 processed = 55% hit rate。**通則：Skip 最佳化必須區分「已掃描且無內容」vs「掃描失敗（被擋、超時）」，後者必須保留重試機會。**
**信心**：高（production 驗證，修復前 0 success → 修復後 55% hit rate）
**檔案**：`crawler/core/engine.py`（`_full_scan_sequential`）, `crawler/core/crawled_registry.py`（`load_blocked_ids`）
**日期**：2026-02

### Numeric ID Dedup — `_is_any_url_crawled()` URL pattern 去重漏洞
**問題**：`_is_any_url_crawled(article_id)` 只檢查 3 個固定 URL pattern（`realtimenews/{id}-260402`、`newspapers/{id}-260109`、`opinion/{id}-262101`），但 sitemap 爬到的 URL 用不同 category code（如 `260405`、`260202`）。結果：94.7% 已爬文章在 full_scan 時不被識別為重複，浪費大量時間重爬。530/530 跨 section 同 ID 對都是不同 category code。
**解決方案**：建立 `crawled_numeric_ids: Set[int]` 二級索引。`_load_history()` 對每個 URL 呼叫 `parser.extract_id_from_url()` 提取數字 ID。`_is_any_url_crawled()` 先查 numeric ID（O(1)），再 fallback 到 URL matching。`_mark_as_crawled()` 同步更新。GCP 部署後確認：366K URLs → 190K unique numeric IDs，32 skip 在首批結果。
**信心**：高（GCP production 驗證）
**檔案**：`crawler/core/engine.py`（`_load_history`, `_is_any_url_crawled`, `_mark_as_crawled`）
**日期**：2026-02

### `run_list_page()` 對 curl_cffi sources 靜默失敗
**問題**：`engine.run_list_page()` 使用 `aiohttp.ClientTimeout` 和 `async with self.session.get(...)` context manager — 這是 aiohttp 專用語法。curl_cffi session 不支援這些，拋出 exception 被 `except Exception: continue` 靜默吃掉。結果：所有 list page 抓取都失敗，`total_urls_to_crawl` 為空，回傳全 0 且無 error message。CNA（curl_cffi source）用 list_page 模式時完全不工作。
**解決方案**：目前 workaround：對 curl_cffi sources 使用 `auto` 模式代替 `list_page`。長期修復應讓 `run_list_page()` 像 `_fetch()` 一樣區分 session type。**通則：except Exception + continue 在 loop 中會吞掉結構性錯誤，改為至少 log error level。**
**信心**：中（單次驗證，但 code 邏輯明確）
**檔案**：`crawler/core/engine.py`（`run_list_page`）
**日期**：2026-02

### Full Scan Watermark 不適合短期補缺 — 用 Auto Mode
**問題**：UDN full_scan 的 watermark 在 ID ~8.2M，但最新 ID ~9.3M（gap 1.1M IDs）。以 6% hit rate 計算需 4+ 天。用戶只想補 6 天空缺（~3000 篇），但 full_scan 從 watermark 開始掃整個 gap。
**解決方案**：短期補缺用 `auto` mode（從最新 ID 向後掃，遇到 10 個連續已爬就停）。UDN auto count=5000 在 29 分鐘內補了 2,174 篇。**通則：full_scan 適合歷史 backfill（從頭掃到尾），auto 適合近期補缺（從新到舊，遇到已爬就停）。**
**信心**：高（production 驗證）
**檔案**：`crawler/core/engine.py`（`run_auto`）
**日期**：2026-02

### Dashboard API `count` vs `stats.success` — 讀錯欄位導致誤殺正常任務
**問題**：`/api/indexing/crawler/status` 回傳的 task 物件中，top-level `count` 欄位為 0，但 `stats.success` 實際有 18,298。監控腳本讀取 `count` 後判定任務「0 成功」，建議停止任務並切換模式。若執行此建議，會白費 86 小時工作並丟失 18,298 篇文章成果。
**解決方案**：監控時**只讀 `stats` 物件內的欄位**（`stats.success`、`stats.failed`、`stats.skipped`、`stats.not_found`、`stats.blocked`），不可用 top-level `count` 判斷任務健康度。**通則：API 回傳有多層結構時，先確認每個欄位的語意，不要假設名稱相似的欄位等價。**
**信心**：高（production 驗證，count=0 vs stats.success=18298）
**檔案**：`indexing/dashboard_api.py`（task serialization）
**日期**：2026-02

### 過時記憶導致錯誤診斷 — 多層覆蓋的 memory 必須交叉比對
**問題**：Memory 記錄「Cloudflare blocks full_scan」和後來的「realtimenews 萬用路徑修復」，但兩者都是不完整/錯誤的。監控時讀到第一筆匹配就套用診斷。實際根因是 category code 不對（不是 Cloudflare，也不是萬用路徑修復了 Cloudflare）。
**解決方案**：(1) 診斷前先看數據（`stats.blocked` 是否 >0），不要直接套 memory 結論。(2) Memory 中被推翻的條目要明確標記 ~~刪除線~~ 和推翻原因。(3) **通則：memory 是分層的 — 後來的修復紀錄覆蓋早期觀察，但「修復」本身也可能是錯的，必須用實際數據驗證。**
**信心**：高
**日期**：2026-02

### TimeoutError 映射為 NOT_FOUND — 暫時性錯誤被永久跳過
**問題**：`engine.py:_fetch()` 的 `except asyncio.TimeoutError` 直接 `return (None, CrawlStatus.NOT_FOUND)`，跳過 retry loop。NOT_FOUND 寫入 `not_found_articles` 永久跳過表，未來重掃直接 skip。但 timeout 是暫時性錯誤（網站慢/暫時無法連線），文章可能存在。相比之下，其他 `Exception`（如 ConnectionError）會落入 retry loop，耗盡後回傳 `FETCH_ERROR`（可 retry）。
**解決方案**：移除 TimeoutError handler 的 `return`，讓它跟其他 Exception 一樣走 retry → FETCH_ERROR 流程。一行改動。**通則：錯誤分類要區分「確定不存在」（404）vs「暫時無法確認」（timeout/network error），後者不應永久標記。**
**信心**：高（code 邏輯明確）
**檔案**：`crawler/core/engine.py`（`_fetch` method, L507-510）
**日期**：2026-02

### curl_cffi 與 aiohttp 不可混用 — silent fallback 會爆
**問題**：Parser 宣告 `preferred_session_type = CURL_CFFI` 但 engine 給了 aiohttp session。兩者 API 不相容（`.status_code` vs `.status`、`.text` property vs coroutine），但錯誤被外層 catch 吞掉，表現為靜默全部失敗。
**解決方案**：**Rule**: Parser 宣告 CURL_CFFI → 必須在 `settings.CURL_CFFI_SOURCES` → engine 必須給 curl_cffi session → 缺一 = RuntimeError。絕不加 `getattr()` 相容 shim。CURL_CFFI: `['cna', 'chinatimes', 'einfo', 'esg_businesstoday', 'moea']`。AIOHTTP: `['ltn', 'udn']`。
**信心**：高
**檔案**：`crawler/core/engine.py`, `crawler/core/settings.py`
**日期**：2026-02

### Windows Pipe Hang — kill subprocess 後 pipe reader 無限等待
**問題**：`proc.terminate()`/`kill()` on Windows 不會乾淨關閉 pipes。`async for line in proc.stdout` 在 subprocess 被殺後永久掛住。Dashboard event loop 阻塞 → API 全部 timeout。
**解決方案**：`_force_kill_after()` 現在在 `proc.kill()` 後取消 `task._reader_task`。`_run_crawler_subprocess` 的 CancelledError handler 將 task 標記為 FAILED。**通則：Windows 上 kill subprocess 後必須主動取消 pipe reader task。**
**信心**：高
**檔案**：`indexing/dashboard_api.py`
**日期**：2026-02

### Watermark 只往前不往回 — ESG BT 未來日期導致全跳過
**問題**：`update_scan_watermark()` 只往前推進。ESG BT watermark 被設為 2026-02-13（未來日期），導致整個掃描日期範圍被跳過，success=0。
**解決方案**：重設需直接 SQLite UPDATE `SET last_scanned_date = NULL`。啟動 full_scan 前必須驗證 watermark：`registry.get_scan_watermark(source_id)`。**通則：單調遞增的 watermark 若被設錯（如未來日期），影響面是整個範圍跳過。**
**信心**：高
**檔案**：`crawler/core/crawled_registry.py`
**日期**：2026-02

### Proxy Pool — free proxy 必須用 HTTPS 驗證，無法繞 Cloudflare
**問題**：einfo IP 被 ban，需 proxy。Free proxy 驗證時用 HTTP 通過但 HTTPS 失敗（無法 CONNECT tunnel）。Cloudflare 網站（chinatimes）free proxy 100% 失敗。
**解決方案**：驗證必須用 HTTPS（`https://httpbin.org/ip`）。`PROXY_MAX_RETRIES=5`（vs normal 2）。einfo 成功率 66%→87%。**通則：free proxy 只能用於無 WAF 的網站，且必須用目標協議驗證。**
**信心**：高
**檔案**：`crawler/core/proxy_pool.py`
**日期**：2026-02

### GCP SSH 操作陷阱
**問題**：(1) `pkill -f X` via SSH 會殺 SSH 自身（exit 128）(2) `nohup` 不繼承 `cd`，background process 用錯路徑 (3) 快速連續 SSH port 耗盡 (4) Python 3.11 f-string 不支援 `f"{dict["key"]}"`
**解決方案**：(1) 改用 pgrep+kill 或接受 exit 128 (2) script 裡用絕對路徑 + 明確 cd (3) SSH 間隔 sleep 10-15s (4) remote 命令用簡單 print
**信心**：高
**日期**：2026-02

### Dashboard API 參數陷阱 — start_id/end_id 必須 top-level
**問題**：`start_id`/`end_id` 放在 `overrides` 物件裡，API 完全忽略。`overrides` 只存在於 `settings.py` 的 `FULL_SCAN_OVERRIDES`（控制 concurrent/delay），不是 API 參數。
**解決方案**：`start_id`/`end_id` 必須放 JSON body top-level。**通則：API 參數名稱與內部 config 名稱相似但語意不同時，先看 handler code 確認。**
**信心**：高
**檔案**：`indexing/dashboard_api.py`
**日期**：2026-02

### curl_cffi AsyncSession.close() 是 coroutine — 未 await 導致 subprocess 全標記 failed
**問題**：`engine.close()` 中 `self.session.close()` 對 curl_cffi `AsyncSession` 是 async coroutine，但沒有 `await`。導致：(1) RuntimeWarning: coroutine never awaited (2) session 資源未釋放 (3) `asyncio.run()` cleanup 時爆 `ValueError('I/O operation on closed file')` / `lost sys.stderr` → exit code 1 (4) parent 端因 returncode≠0 將所有 task 標記 failed。爬蟲**實際有在正常工作**（stats 有 success），但 status 全顯示 failed。
**解決方案**：(1) `engine.close()` 統一用 `await asyncio.wait_for(self.session.close(), timeout=5.0)` — aiohttp 和 curl_cffi 都是 async。(2) `subprocess_runner.py` 在 `_send()` 後加 `sys.stdout.close()` 確保 pipe EOF 送達 parent。(3) `asyncio.run()` 外層 wrap `try/except Exception: pass`（`SystemExit` 不被捕獲，保留 main() 的 sys.exit(1)）。(4) Parent 端新增 fallback：`returncode==0 + status==RUNNING` → infer completed。**通則：第三方 async library 的 close() 不一定是 sync — 必須檢查 `inspect.iscoroutinefunction()`。**
**信心**：高（production 驗證，6 sources 全部從 failed → completed/early_stopped）
**檔案**：`crawler/core/engine.py`（close）, `crawler/subprocess_runner.py`, `indexing/dashboard_api.py`
**日期**：2026-03

### asyncio.run() cleanup 在 Windows subprocess 中引發 exit code 1
**問題**：即使修復 session.close() await 後，subprocess 仍 exit code 1。根因：Python interpreter shutdown 時，`asyncio.run()` 的 finally block（`shutdown_asyncgens` / `shutdown_default_executor`）嘗試寫入已關閉的 stderr fd → `ValueError` → 未處理 → exit code 1。此時 `_send({"type": "completed"})` 已執行，但 parent 的 `async for line in proc.stdout` 可能因 pipe 未正確關閉而收不到最後的 message。
**解決方案**：雙重修復：(1) subprocess 端：`_send()` 後立即 `sys.stdout.close()` 強制 pipe EOF。(2) subprocess 端：`asyncio.run()` 外層 `except Exception: pass`（只捕獲 cleanup error，`SystemExit` 透傳）。(3) parent 端：fallback 處理 `returncode==0 + RUNNING` → completed。**通則：Windows 上的 asyncio subprocess 必須假設 asyncio.run() cleanup 可能失敗，不要依賴 exit code 0 來判斷成功 — 用 IPC protocol（JSON message）判斷。**
**信心**：高（production 驗證）
**檔案**：`crawler/subprocess_runner.py`, `indexing/dashboard_api.py`
**日期**：2026-03

### aiohttp 預設 User-Agent 被台灣新聞網站擋 — parser 自建 session 必須帶 headers
**問題**：GCP cron 的 LTN auto mode 連續 2-3 天 0 success。`LtnParser.get_latest_id()` 自建 `aiohttp.ClientSession()` 沒帶 headers → 預設 UA `Python/aiohttp` → LTN 拒絕 → `asyncio.TimeoutError`。`str(asyncio.TimeoutError())` 是空字串，所以 log 顯示 `Error getting latest ID: `（空白），難以診斷。
**解決方案**：`ltn_parser.py` import `DEFAULT_HEADERS`，`get_latest_id()` 和 `get_date()` 的 session 都加 `headers=DEFAULT_HEADERS`。**通則：parser 中任何自建 aiohttp session 都必須帶 `DEFAULT_HEADERS`，不能依賴 engine 的 session 管理。** 同時注意 `asyncio.TimeoutError` 的 `str()` 為空 — 如果看到空白 error message，先懷疑 timeout。
**信心**：高（修復後立即 273+ success）
**檔案**：`crawler/parsers/ltn_parser.py`
**日期**：2026-03-13

### `.indexing_done` 是舊 Qdrant 時代殘留 — 不反映 PG 實際狀態
**問題**：全量 Indexing 的 resume 機制使用 `.indexing_done` 檔案追蹤已完成的 TSV 檔名。調查發現 `.indexing_done` 標記了 458/463 個檔案為「完成」（進度看似 98.9%），但 PG DB 只有 236,744 篇文章（幾乎全是 chinatimes）。根因：這個 `.indexing_done` 是 Qdrant 時代（舊系統）跑 indexing 時留下的，在遷移到 PG 後從未重建。所有 ltn、cna、udn、einfo、esg 的 TSV 都被錯誤標記為「已完成」，但實際上完全沒有 indexed 進 PG。
**解決方案**：(1) 刪除舊的 `.indexing_done`，重建以反映 PG 實際狀態（用 PG 中的 source_name 分布判斷哪些 source 已完成）。(2) 全量 indexing 的真實進度約 11.5%（236K/2M），不是 98.9%。(3) 日後遷移存儲後端時，必須清除 / 重建所有 resume state 檔案。
**通則**：**Resume state 是與儲存後端耦合的。遷移後端時，resume state 必須一起遷移或重建，否則進度追蹤完全失效。**
**信心**：高（直接查 PG article 數量 + source 分布驗證）
**檔案**：`data/crawler/articles/.indexing_done`, `indexing/pipeline.py`
**日期**：2026-03-18

### Checkpoint 檔案被截斷 — 不完整 JSON 導致整個 TSV 跳過
**問題**：LTN 的兩個 checkpoint 檔案（`ltn_2025_1.tsv.checkpoint.json`、`ltn_2025_2.tsv.checkpoint.json`）內容被截斷（最後 JSON 不完整），當 indexing pipeline 嘗試 resume 時解析失敗。視 error handling 方式，TSV 可能被直接跳過（靜默跳過）或拋出 exception（中斷整個 run）。
**解決方案**：手動清除截斷的 checkpoint 檔案（刪除或重置為空 `{}`），讓 pipeline 從該 TSV 頭開始重跑。已確認兩個 LTN checkpoint 已修復（清除並重建）。
**通則**：**任何 checkpoint 機制都應有 validation 步驟：讀取 checkpoint 失敗時，不應靜默跳過整個任務，應重置為從頭開始並 log warning。**
**信心**：高（本次直接發現並修復）
**檔案**：`crawled/` 目錄下的 `*.checkpoint.json` 檔案
**日期**：2026-03-18

### PG DB Timeout 導致 indexing 文章永久丟失
**問題**：chinatimes_2026-02-15_11-50.tsv 有 60 個 DB timeout 失敗。Indexing pipeline 在寫入 PG 時遇到 timeout → 這些文章的 embedding 已計算完但未寫入 DB → pipeline 記錄失敗但繼續推進 checkpoint → 下次 resume 從失敗點之後開始，這 60 篇被永久跳過。
**解決方案**：(1) 已清除該 TSV 的 checkpoint，讓 pipeline 重跑整個 TSV。(2) PG 現已恢復正常（timeout 是暫時性問題）。
**通則**：**DB 寫入失敗時，checkpoint 不應推進。必須保持冪等性：已寫入的文章 PG 會 ON CONFLICT DO NOTHING，重跑不會重複。只有全批成功才推進 checkpoint。**
**信心**：中（已清除 checkpoint 重跑，但 pipeline 的 checkpoint 推進邏輯尚未驗證是否符合此通則）
**檔案**：`indexing/pipeline.py`, `indexing/postgresql_uploader.py`
**日期**：2026-03-18
