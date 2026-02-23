# Lessons Learned

> 累積的專案知識與解決方案。由 `/learn` 指令自動或手動記錄。

---

## 格式說明

每個 lesson 包含：
- **問題**：遇到什麼問題
- **解決方案**：如何解決
- **信心**：低/中/高（重複驗證會提升）
- **檔案**：相關檔案路徑
- **日期**：記錄日期

---

## Reasoning

<!-- 與 reasoning/orchestrator.py、reasoning/agents/*.py 相關的 lessons -->

### Orchestrator 狀態管理
**問題**：Actor-Critic 迴圈中狀態不一致
**解決方案**：使用 Pydantic model 驗證狀態轉換，確保 writer sources ⊆ analyst sources
**信心**：高
**檔案**：`reasoning/orchestrator.py`
**日期**：2025-12

---

## Ranking

<!-- 與 core/ranking.py、core/xgboost_ranker.py、core/mmr.py 相關的 lessons -->

### XGBoost 模型載入效能
**問題**：每次請求重新載入模型導致延遲
**解決方案**：使用 global model cache，只在啟動時載入一次
**信心**：高
**檔案**：`core/xgboost_ranker.py`
**日期**：2025-12

---

## Retrieval

<!-- 與 core/retriever.py、core/bm25.py 相關的 lessons -->

### 語義分塊對中文新聞效果有限
**問題**：嘗試用語義分塊（相鄰句子 cosine similarity < threshold 時切分）處理中文新聞，但無論閾值設 0.75-0.90，都切成每句一個 chunk
**解決方案**：中文新聞相鄰句子相似度普遍 < 0.5（每句話主題轉換明顯），改用長度優先策略（170 字/chunk），在句號邊界切分
**信心**：中
**檔案**：`docs/index-plan.md`、`code/python/indexing/poc_*.py`
**日期**：2026-01

### Chunk 區別度的理想範圍
**問題**：如何評估 chunk 切分品質？區別度（相鄰 chunk 相似度）應該多少？
**解決方案**：理想範圍 0.4-0.6。> 0.8 太相似（檢索難區分）、< 0.4 太碎（上下文丟失）。170 字/chunk 區別度約 0.56，符合理想範圍
**信心**：中
**檔案**：`code/python/indexing/poc_length_analysis.py`
**日期**：2026-01

---

## API / Frontend

<!-- 與 webserver/、static/ 相關的 lessons -->

### SSE 連線中斷處理
**問題**：客戶端斷線時 server 繼續處理
**解決方案**：檢查 `request.transport.is_closing()` 提前終止
**信心**：中
**檔案**：`core/utils/message_senders.py`
**日期**：2025-11

### 獨立 Dashboard Server 避免影響主服務
**問題**：開發者 Dashboard（如 Indexing Dashboard）若整合到主 webserver，會增加主服務複雜度，且 Dashboard 重啟會影響使用者
**解決方案**：Dashboard 使用獨立的 aiohttp server（如 Port 8001），與主服務完全隔離。好處：(1) 不影響主服務穩定性 (2) 可獨立開發/重啟 (3) 可獨立部署或不部署
**信心**：中
**檔案**：`code/python/indexing/dashboard_server.py`
**日期**：2026-02

### 雙 Handler Pipeline 需要 API 層控制生命週期
**問題**：Unified mode 需要串接兩個 handler（NLWebHandler → GenerateAnswer），但 `runQuery()` 結尾自動送 `end-nlweb-response` 和記錄 analytics，導致第二個 handler 開始前 SSE 就結束了。且錯誤路徑也有 `send_end_response(error=True)`，兩處都要處理
**解決方案**：在第一個 handler 設 `skip_end_response = True`，讓 API 層（api.py）透過 `try/finally` 統一控制 end response 和 analytics。注入狀態時需轉移：`final_ranked_answers`、`items`、`query_id`、`conversation_id`、`connection_alive_event`、`decontextualized_query`。關鍵：baseHandler.py 的正常路徑和錯誤路徑都要檢查 `skip_end_response`
**信心**：低
**檔案**：`webserver/routes/api.py`、`core/baseHandler.py`
**日期**：2026-01

### asyncio.create_task 不保證 SSE 訊息順序
**問題**：`create_assistant_result()` 和 `asyncio.create_task(handler.send_message())` 是 fire-and-forget，不等待實際送出。在 unified mode 需要嚴格的訊息順序（articles → summary → answer）時，fire-and-forget 不保證前一條訊息在下一個處理階段開始前已送出
**解決方案**：需要順序保證時改用 `await handler.send_message(message)` 取代 `asyncio.create_task()`。修改了 `ranking.py:sendAnswers()`（unified → await）和 `post_ranking.py:SummarizeResults.do()`（unified → await）
**信心**：中
**檔案**：`core/ranking.py`、`core/post_ranking.py`
**日期**：2026-01

### DOM 父子元素可見性級聯陷阱
**問題**：隱藏父元素會連帶隱藏所有子元素，即使子元素本身有 `.active { display: block }`。本專案中 `#chatContainer` 是 `#resultsSection` 的子元素，移除 `resultsSection` 的 `.active` class 後，chatContainer 無論如何設定都不會顯示，且 console 無任何錯誤
**解決方案**：切換到 chat 模式時，必須無條件 `resultsSection.classList.add('active')`，因為它是 chatContainer 的父容器。修改父元素可見性前，先確認 DOM 樹中是否有需要獨立控制可見性的子元素
**信心**：高
**檔案**：`static/news-search.js`（mode switch handler）、`static/news-search-prototype.html`（DOM 結構）
**日期**：2026-01

### CSS inline style 永遠覆蓋 class 規則
**問題**：在 JS 中設定 `element.style.display = 'none'` 後，即使加上 CSS class `.active { display: block }`，元素仍然隱藏。因為 inline style 優先級高於 class 選擇器
**解決方案**：要讓 CSS class 重新生效，必須清除 inline style：`element.style.display = ''`（空字串），而非設為其他值。統一使用 CSS class 控制可見性，避免混用 inline style 和 class
**信心**：高
**檔案**：`static/news-search.js`（`resetToHome()` 函式）
**日期**：2026-01

### CSS replace_all 會產生 :root 循環參照
**問題**：使用 Edit 工具的 `replace_all` 將硬編碼色碼（如 `#2563eb`）全域替換為 CSS 變數（如 `var(--color-primary)`）時，`:root` 區塊中的定義也被替換，產生 `--color-primary: var(--color-primary)` 循環參照，導致所有顏色失效
**解決方案**：全域替換 CSS 色碼後，必須手動檢查並還原 `:root` 區塊中的定義值回硬編碼色碼。或者先替換再補回 `:root`
**信心**：高
**檔案**：`static/news-search.css`（`:root` CSS 變數定義區）
**日期**：2026-01

### Create-or-Update 函式必須回寫 ID
**問題**：`saveCurrentSession()` 在建立新 session 後，沒有將 `newSession.id` 回寫到 `currentLoadedSessionId`。導致後續每次呼叫都以為是「新建」而非「更新」，產生大量重複 session
**解決方案**：Create-or-Update 模式中，建立新實體後必須更新參照 ID：`currentLoadedSessionId = newSession.id`。通用規則：任何 "if exists → update, else → create" 的函式，create 分支結尾必須更新用來判斷 exists 的變數
**信心**：高
**檔案**：`static/news-search.js`（`saveCurrentSession()`）
**日期**：2026-01

### 子層級操作不應觸發父層級建立
**問題**：釘選新聞（session 子操作）呼叫 `saveCurrentSession()` 時，若 `currentLoadedSessionId` 為 null，會意外建立新 session 並出現在左側邊欄。使用者預期：session 只在第一則訊息發出時建立，釘選是 session 內部操作
**解決方案**：子層級操作（如釘選）加 guard：`if (currentLoadedSessionId !== null) saveCurrentSession()`。父層級建立只在主要操作完成時觸發（搜尋結果返回、深度研究完成、自由對話回應後）
**信心**：高
**檔案**：`static/news-search.js`（`togglePinNewsCard()`、`togglePinMessage()`）
**日期**：2026-01

### 非同步產生的狀態必須即時持久化 + 切換前保存
**問題**：深度搜尋報告完成後，切換到其他對話紀錄再切回，報告消失。原因：(1) 報告產生後只存在記憶體變數 `currentResearchReport`，沒有立即保存到 localStorage；(2) `loadSavedSession()` 直接覆蓋所有狀態，沒有先保存當前對話
**解決方案**：雙重保護——(1) 非同步操作完成時立即保存：`displayDeepResearchResults()` 結尾加 `saveCurrentSession()`，防止關閉/刷新丟失；(2) 切換前保存：`loadSavedSession()` 呼叫前加 `if (sessionHistory.length > 0 || currentResearchReport) saveCurrentSession()`，防止後續操作（如 Free Conversation）丟失。通用規則：任何產生重要狀態的非同步操作完成時，必須觸發持久化
**信心**：高
**檔案**：`static/news-search.js`（`displayDeepResearchResults()`、三處 `loadSavedSession()` 呼叫點）
**日期**：2026-02

### 頁面切換必須完整快照/還原所有 UI 狀態
**問題**：`showFolderPage()` 反覆導致左側邊欄收合，因為函式中硬編碼了 `leftSidebar.classList.remove('visible')`。此外，快照只保存 4 個元素的 `style.display`，未保存 `chatContainer`/`chatInputContainer` 狀態，導致從資料夾返回後若原本在聊天模式，UI 不一致（空白畫面）
**解決方案**：(1) 移除 `showFolderPage()` 中任何與左側邊欄相關的操作——資料夾頁不應改變側欄狀態。(2) 快照必須包含所有可能影響佈局的元素狀態（含 `chatContainer.classList.active`、`chatInputContainer.style.display`），離開時完整還原。通用規則：頁面切換函式只應影響自己的頁面元素，不可有側面效應修改其他區域的 UI
**信心**：高
**檔案**：`static/news-search.js`（`showFolderPage()`、`hideFolderPage()`）
**日期**：2026-01

### JavaScript `let` 跨區段 TDZ 陷阱
**問題**：在大型 JS 檔案中，將 `let _folderModeActive` 宣告在 FOLDER section（檔案後段），但 `renderLeftSidebarSessions()` 函式（定義在前段）內部引用它，且該函式在宣告行之前就被呼叫（初始化呼叫）。結果：`ReferenceError: Cannot access '_folderModeActive' before initialization`。此錯誤終止整個腳本執行，導致所有後續事件綁定失效——所有按鈕看似「沒反應」，但實際是 handler 從未註冊。更隱蔽的是，第一個 TDZ 錯誤會級聯：腳本停止後，後段的其他 `let` 變數（如 `_preFolderState`）也永遠留在 TDZ，使用者操作觸發時產生第二個 ReferenceError
**解決方案**：新增 `let` 變數時，必須檢查所有引用它的函式是否在宣告前被呼叫（包括初始化呼叫、事件監聽 callback）。安全做法：將跨區段共享的 `let` 變數集中宣告在最早的引用點之前。偵錯時：「所有按鈕無反應」→ 先查 console 是否有 ReferenceError 終止了腳本
**信心**：高
**檔案**：`static/news-search.js`（`_folderModeActive`、`_preFolderState`）
**日期**：2026-01

### SSE 漸進式渲染 Pattern
**問題**：長時間 SSE 流程（如搜尋需 10+ 秒），用戶等待期間只看到轉圈圈，感知延遲高、不知道系統在做什麼
**解決方案**：三層架構——
1. **立即回饋**：提交查詢後立即顯示 skeleton 佔位符（shimmer 動畫）+ typing indicator
2. **後端進度訊息**：在關鍵步驟發送 `progress` SSE 訊息（如 `{message_type: "progress", stage: "searching", message: "搜尋資料庫中..."}`）
3. **前端 callback 機制**：`handlePostStreamingRequest(url, body, query, signal, callbacks)` 支援 `{onProgress, onArticles, onAnswer, onComplete}`，每種 message_type 觸發對應 callback 即時更新 UI

關鍵點：skeleton 在 `articles` 到達後才被替換，進度訊息持續更新直到 `complete`，讓用戶感知延遲從 10+ 秒降到 1-2 秒
**信心**：中
**檔案**：`static/news-search.js`（`renderSkeletonCards`、`handlePostStreamingRequest`）、`static/news-search.css`（skeleton 樣式）、`core/baseHandler.py`（`send_progress` 呼叫點）、`core/utils/message_senders.py`（`send_progress` 方法）
**日期**：2026-02

---

## Infrastructure

<!-- 與 DB、Cache、Config 相關的 lessons -->

### Foreign Key Race Condition
**問題**：Async queue 導致 FK 違規
**解決方案**：`log_query_start()` 改為同步執行
**信心**：高
**檔案**：`core/query_logger.py`
**日期**：2025-11

### SQLite + asyncio 線程安全
**問題**：使用 `run_in_executor()` 從不同線程存取 SQLite 時報錯 `SQLite objects created in a thread can only be used in that same thread`
**解決方案**：`sqlite3.connect(path, check_same_thread=False)`
**信心**：中
**檔案**：`code/python/indexing/dual_storage.py`
**日期**：2026-01

### 長時間任務進度回調需要節流
**問題**：Crawler 處理每篇文章後都呼叫 `progress_callback` 並透過 WebSocket 廣播，高併發時（如 5 concurrent requests）會產生大量訊息，影響效能且前端更新太頻繁
**解決方案**：在 callback 加節流機制，記錄 `_last_progress_update` 時間戳，間隔小於閾值（如 1 秒）時跳過。確保結束時一定會有最終更新
```python
def _report_progress(self):
    if self.progress_callback is None:
        return
    now = time.time()
    if now - self._last_progress_update < self._progress_update_interval:
        return
    self._last_progress_update = now
    self.progress_callback(self.stats.copy())
```
**信心**：中
**檔案**：`code/python/crawler/core/engine.py`
**日期**：2026-02

### [已淘汰] ID-Date Interpolation → 改用 Full Scan
**問題**：ID-Date 插值嚴重低估 ID 範圍（UDN backfill 只得 1-3K/月，auto mode 得 28-29K/月，10x 差距）
**解決方案**：放棄 interpolation，改用 `run_full_scan()` 掃描完整 ID 範圍（start_id → end_id）。不做 404 early-stop，只有 BLOCKED_CONSECUTIVE_LIMIT 停止。404 adaptive throttle 降速不停止
**信心**：高
**檔案**：`code/python/crawler/core/engine.py`（`FULL_SCAN_CONFIG`、`run_full_scan()`、`_full_scan_sequential()`、`_full_scan_date_based()`）
**日期**：2026-02

### 設計爬蟲策略前必須實際驗證資料來源
**問題**：為 ESG_BusinessToday 設計 sitemap backfill，但 sitemap 實際最新文章是 2021-03-01，近 5 年完全沒更新。前一個 agent 調查時未實際抓取 sitemap 內容驗證，導致設計了無效的 backfill 策略
**解決方案**：設計任何爬蟲策略前，必須：
1. 實際 HTTP 請求 sitemap URL，確認回應正常
2. 檢查 sitemap 內容的日期範圍（最舊/最新文章日期）
3. 對 2-3 篇文章實際測試 parser
4. 不可只看程式碼中的 URL 設定就假設有效
**信心**：高
**檔案**：`code/python/crawler/parsers/esg_businesstoday_parser.py`
**日期**：2026-02

### Auto mode 需要日期下界避免爬取過多歷史資料
**問題**：Crawler auto mode 從最新 ID 往回爬，遇到 skip（已爬過）才停。但如果中間有大段 ID 未被爬過（如 LTN 3K 篇跨 10 年），auto mode 會一路爬到 2016 年。用戶只需要 2024-01-01 以後的資料
**解決方案**：auto mode 應支援 `date_floor` 參數，文章日期早於此值時自動停止。或改用 date_range mode 明確指定範圍
**信心**：中
**檔案**：`code/python/crawler/core/engine.py`（`run_auto()`）
**日期**：2026-02

---

## 開發環境 / 工具

<!-- 與開發流程、工具相關的 lessons -->

### Python 版本相容性
**問題**：Python 3.13 破壞 qdrant-client
**解決方案**：固定使用 Python 3.11
**信心**：高
**檔案**：專案全域
**日期**：2025-12

### aiohttp vs curl_cffi Response API 差異
**問題**：Crawler 需要同時支援 aiohttp 和 curl_cffi（繞過 WAF），但兩者 Response 物件 API 不同：
- HTTP 狀態碼：aiohttp 用 `.status`，curl_cffi 用 `.status_code`
- Response body：aiohttp 的 `.text()` 是 async，curl_cffi 的 `.text` 是 sync 屬性
**解決方案**：使用 getattr 兼容模式
```python
# 狀態碼
status = getattr(response, 'status_code', None) or getattr(response, 'status', 0)

# Response text
if hasattr(response, 'text') and callable(response.text):
    html = await response.text()
else:
    html = response.text
```
**信心**：高
**檔案**：`code/python/crawler/parsers/einfo_parser.py`、`esg_businesstoday_parser.py`
**日期**：2026-01

### [已更新] 編碼偵測：charset_normalizer 取代 response.text
**問題**：curl_cffi 的 `response.text` 在 server 回傳 Big5/cp950 編碼時拋 `UnicodeDecodeError`。aiohttp 的 `response.text()` 較穩但也不完美。不同框架（Scrapy 用 w3lib/chardet，Trafilatura 內建偵測）各有方案
**解決方案**：統一用 `charset_normalizer`（比 chardet 更準、更快）取代所有 `response.text`：
```python
from charset_normalizer import from_bytes
detected = from_bytes(response.content).best()
text = str(detected) if detected else response.content.decode('utf-8', errors='replace')
```
curl_cffi 和 aiohttp 兩個分支都改。此方案比原本的 try/except UnicodeDecodeError 更根本——不是「UTF-8 解碼失敗才補救」，而是「從 bytes 自動偵測正確編碼」
**信心**：高（經 Trafilatura/Scrapy 三方比較驗證）
**檔案**：`code/python/crawler/core/engine.py`（`_fetch()` 雙分支）
**日期**：2026-02

### 架構圖維護 - 檔案路徑必須徹底調查
**問題**：之前 agent 自動填入架構圖的檔案路徑是錯的（如 `decomposer.py` 不存在，實際是 `decontextualize.py`；`tool_selector.py` 根本不存在）。錯誤的路徑會誤導後續開發
**解決方案**：更新 `architecture-diagram.json` 前，必須用 `Glob` 工具確認檔案是否存在，不可依賴記憶或推測。特別注意：(1) 檔案名稱可能有底線/連字號差異 (2) 檔案可能在不同目錄 (3) 功能可能整合在其他檔案中而非獨立存在
**信心**：高
**檔案**：`static/architecture-diagram.json`
**日期**：2026-02

### 架構圖維護 - Source of Truth 優先順序
**問題**：架構圖、spec 文件、程式碼之間可能不一致，不知道以誰為準
**解決方案**：建立更新優先順序（高層級根據低層級更新）：
1. L1: 程式碼（最終真相）
2. L2: Spec 文件（`docs/*-spec.md`，貼近實作）
3. L3: 架構文件（`state-machine-diagram.md`、`systemmap.md`、`architecture-diagram.json`）
4. L4: 進度文件（`CONTEXT.md`、`PROGRESS.md`）

當衝突時：程式碼 > Spec > 架構圖 > 進度文件。更新時從低層級往高層級推導
**信心**：高
**檔案**：`.claude/commands/update-docs/SKILL.md`
**日期**：2026-02

### 架構圖維護 - 必須先討論再執行
**問題**：Agent 自行判斷節點「不存在」或「應該移除」，未經用戶確認就刪除。例如：nodePositions 引用的功能性節點（如 knowledge-gap）沒有在 nodes array 中定義，Agent 誤以為是錯誤而刪除，但實際上這些是用戶刻意規劃的重要功能模組
**解決方案**：架構圖維護必須遵循「表格呈現 → 討論 → 執行」流程：
1. **表格呈現**：用表格列出現有節點（ID、檔案、狀態、備註），以及發現的問題
2. **討論**：逐一與用戶確認——哪些要保留、哪些要移除、哪些要新增、哪些要改狀態
3. **執行**：用戶確認後才執行修改

表格格式範例：
```
| 節點 | 檔案 | 狀態 | 備註 |
|------|------|------|------|
| xxx  | path ✓/❌ | done/notdone | 說明 |
```

**絕對禁止**：未經討論就刪除節點、移除 edges、或「清理」看似不一致的資料
**信心**：高
**檔案**：`static/architecture-diagram.json`
**日期**：2026-02

### Buffer Zone Top-Down 掃描陷阱
**問題**：Sequential ID 掃描（從新到舊）加入 buffer 後，掃描起點在 buffer 頂端（`interpolated_end + buffer`）。Buffer zone 的 ID 全是 404，但 LTN buffer = 6,132 IDs，以 1.5s/request 計算需 153 分鐘才能通過。更糟的是，若 `max_consecutive_not_found < buffer`（如 2000 < 6132），掃描會在 buffer zone 就 early stop，永遠到不了真正的文章範圍
**解決方案**：分離 buffer zone 和 main zone 的 early stop 策略：
1. 記錄 `interpolated_end` 作為 buffer/main 分界點
2. Buffer zone 用小 limit（50 個連續 404 就跳過），直接 `current_id = interpolated_end` 跳到主範圍
3. Main zone 用較大 limit（如 500）
4. 進入 main zone 時重置 `consecutive_not_found`
**信心**：高
**檔案**：`code/python/crawler/core/engine.py`（`_run_sequential_id_scan()`）
**日期**：2026-02

### 持久化任務狀態的 Zombie 處理（含 Subprocess Orphan）
**問題**：Crawler task 狀態持久化到 JSON 檔案，status 包含 "running"/"stopping"。Server 重啟後，(1) task 永遠停在 "running"，阻擋同 source 新 task；(2) subprocess 模式下，孤兒 OS 進程繼續存活佔用資源；(3) auto-resume 為 zombie task 啟動新 subprocess → 同 source 雙重 crawler
**解決方案**：3 層清理：
1. **PID 持久化**：`_task_to_dict()` 保存 `pid`，重啟後可追蹤
2. **`_load_tasks()` 三步清理**：(a) 建立 signal file 讓 subprocess graceful stop → (b) `_kill_orphan_process(pid)` 強制清理（Windows: `taskkill /F /PID`, Unix: `SIGTERM`）→ (c) 標記 failed
3. **Auto-resume 在 orphan 清理後才啟動**：`_load_tasks()` 在 `__init__` 同步執行，`schedule_auto_resume()` 在 `on_startup` hook 異步執行
通用規則：持久化「進行中」狀態 + subprocess 模式 = 必須同時清理狀態和 OS 進程
**信心**：高
**檔案**：`code/python/indexing/dashboard_api.py`（`_load_tasks()`、`_kill_orphan_process()`）
**日期**：2026-02

### Server 程式碼中的相對路徑陷阱
**問題**：`TASKS_FILE = "data/crawler/crawler_tasks.json"` 依賴 CWD 解析。從 `code/python/` 啟動 server 時，檔案被創建在 `code/python/data/crawler/` 而非預期的 `nlweb/data/crawler/`，導致 dashboard 和 CLI 讀取不同檔案
**解決方案**：用 `Path(__file__)` 計算絕對路徑：`TASKS_FILE = str(Path(__file__).parent.parent.parent.parent / "data" / "crawler" / "crawler_tasks.json")`。通用規則：server 程式碼中的資料檔案路徑，必須從 `__file__` 或環境變數推導，不可用相對路徑
**信心**：高
**檔案**：`code/python/indexing/dashboard_api.py`（`TASKS_FILE`）
**日期**：2026-02

### [已淘汰] Buffer Zone / Early Stop 複雜性 → 改用 Full Scan
**問題**：Buffer zone skip、early stop、test mode 掃描耗盡等機制互相干擾（skipped articles 重置計數器、limit 永遠不觸發等），導致各種邊界問題
**解決方案**：Full Scan 重構（2026-02-07）完全移除這些機制。新設計：掃描每一個 ID（ascending），不做 404 early-stop。Checkpoint 在 batch 完成後更新。簡單、可靠、無邊界問題。404 adaptive throttle 也已移除（2026-02-09），因為 404 不會造成 server 負擔
**信心**：高
**檔案**：`code/python/crawler/core/engine.py`（`_full_scan_sequential()`、`_full_scan_date_based()`）
**日期**：2026-02

### Zombie Task Auto-Resume：sync __init__ vs async resume
**問題**：`IndexingDashboardAPI.__init__()` 是同步的（在 `get_api()` 中初始化），但 resume 需要 async（建立 session、啟動 crawler）。不能直接在 `__init__` 中 resume
**解決方案**：在 `_load_tasks()` 中只收集候選 task ID 到 `_pending_auto_resume` list，不執行 resume。透過 aiohttp 的 `app.on_startup.append(on_startup)` hook 在 server 啟動後異步執行 `schedule_auto_resume()`。這是 aiohttp 官方的延遲初始化模式
**信心**：中
**檔案**：`code/python/indexing/dashboard_api.py`（`_load_tasks()`、`schedule_auto_resume()`、`setup_routes()`）
**日期**：2026-02

### Windows subprocess stdout 編碼陷阱（cp950 vs UTF-8）
**問題**：Windows `sys.stdout.encoding` 預設 cp950。Subprocess IPC 用 stdout 傳 JSON，parent 用 UTF-8 解碼。兩個 cp950 汙染源：(1) logging.StreamHandler 預設輸出到 stdout（中文 log 以 cp950 編碼）；(2) `print(json.dumps(..., ensure_ascii=False))` 的 `print()` 也以 cp950 編碼輸出中文 JSON 值（如 `early_stop_reason: "連續 6 次請求被封鎖"`）。結果：parent 解碼為亂碼 `�s�� 6 ���ШD�Q����`
**解決方案**：兩層修復——(1) `sys.stdout.reconfigure(encoding='utf-8')` 在 subprocess 入口強制 stdout 用 UTF-8，解決所有 `print()` 的編碼問題；(2) monkey-patch logger 重導到 stderr：
```python
_original_setup_logger = CrawlerEngine._setup_logger
def _patched_setup_logger(self_engine):
    _original_setup_logger(self_engine)
    for handler in self_engine.logger.handlers:
        if isinstance(handler, logging.StreamHandler) and handler.stream is not sys.stderr:
            handler.stream = sys.stderr
CrawlerEngine._setup_logger = _patched_setup_logger
```
加上 parent 端防禦：`line.decode("utf-8", errors="replace")`。通用規則：subprocess IPC 使用 stdout 時，必須確保所有 logging 和 print 都走 stderr
**信心**：高
**檔案**：`code/python/crawler/subprocess_runner.py`、`code/python/indexing/dashboard_api.py`
**日期**：2026-02

### 日期型 ID 爬蟲的 max_suffix 必須實際驗證 + 彈性掃描
**問題**：CNA full scan 設 `max_suffix=100`（每天掃 0001~0100），但 CNA 實際每天發佈 300+ 篇文章（suffix 到 350+）。結果 95% 的天數被截斷在 suffix=100，漏了約 2/3 的文章。兩年掃描只得 ~50K 篇，實際應有 ~150K+
**解決方案**：(1) 設定前必須實際 HTTP probe 目標網站多個日期的 suffix 邊界 (2) 改為 per-day adaptive scanning：設高上限（600），每天掃描時用 consecutive miss 偵測白工（連續 80 個 404 → 當天結束），接近上限仍有文章時自動擴展。兼顧覆蓋率和效率
**信心**：高
**檔案**：`code/python/crawler/core/engine.py`（`FULL_SCAN_CONFIG`、`_full_scan_date_based()`）、`code/python/crawler/core/settings.py`（`DATE_SCAN_MISS_LIMIT`、`DATE_SCAN_AUTO_EXTEND_STEP`）
**日期**：2026-02

### 大型升級計劃：先審計再實作，避免重複工作
**問題**：接手 9 項修改的升級計劃（handoff prompt），逐一讀取檔案後發現 8 項已在前一個對話中實作完畢，只剩 2 處文件修正。若不先審計就開始「實作」，會花大量 token 重寫已有的程式碼
**解決方案**：接手 handoff prompt 或升級計劃時，先逐一讀取目標檔案，與計劃逐項比對「已實作 vs 未實作」，再只做差異部分。對話上下文可能不完整（context 被壓縮），不可假設「計劃中的都還沒做」
**信心**：高
**檔案**：`docs/indexing-upgrade-handoff.md`
**日期**：2026-02

### simple_keyword_extraction 對中文無效
**問題**：`TextProcessor.simple_keyword_extraction()` 用空格分詞再取 2-4 字，但中文文本沒有空格分隔，整個標題會變成一個超長「詞」被過濾掉。導致 einfo 54.6% 的文章 fallback 到此方法後仍然拿不到 keywords
**解決方案**：改用中文標點切分標題取短語（`re.split(r'[，。、！？：；「」（）《》\s]+', title)`），再去除首尾停用詞，取 2-8 字片段。不依賴 jieba 等分詞器。效果：einfo keywords 45% → 78%
**信心**：高
**檔案**：`code/python/crawler/parsers/einfo_parser.py`（`_chinese_keyword_extraction()`）
**日期**：2026-02

### CNA 記者名在正文而非 HTML 元素
**問題**：CNA parser `_extract_raw_author()` 只查 `.author`/`.reporter`/`.byline` CSS 選擇器，但 CNA 頁面完全沒有這些元素。記者名嵌在正文開頭：`（中央社記者XXX地名日專電）`。導致 68,837 篇文章 author 全部為空
**解決方案**：新增 `_extract_author_from_body(paragraphs)` 方法，用 regex 從首段提取。記者名通常 2-3 字中文，後面跟地名，用 `re.match(r'([\u4e00-\u9fff]{2,3})', raw)` 分離。29.4% 是「綜合外電報導」天生無個人記者。效果：0% → 70.6%
**信心**：高
**檔案**：`code/python/crawler/parsers/cna_parser.py`（`_extract_author_from_body()`）
**日期**：2026-02

### Embedding 模型 docstring 與實際不一致
**問題**：`indexing/embedding.py` docstring 寫 `bge-small-zh-v1.5`（512d），但 `_model_name` 實際是 `BAAI/bge-m3`（1024d）。Spec 文件也跟著寫錯。導致對系統維度的認知錯誤
**解決方案**：修改 embedding 模型後，必須同步更新：(1) 程式碼 docstring (2) `get_embedding_dimension()` 回傳值 (3) spec 文件的模型/維度表格 (4) Qdrant collection 的 vector size 設定
**信心**：高
**檔案**：`code/python/indexing/embedding.py`、`docs/indexing-spec.md`
**日期**：2026-02

### Trafilatura/Scrapy vs Custom Parser：針對已知來源 Custom 大勝
**問題**：考慮用 Trafilatura 或 Scrapy 替代/補充 custom parser，以提升穩定性和成功率
**解決方案**：A/B 測試 20 篇 einfo 文章結果：Custom=20/20, Trafilatura=0/20（抓不到 title/date，Drupal 非標準結構）, Scrapy=1/20（泛用 CSS selector 抓不到 body）。**Custom parser 在已知來源大勝，低成功率是 403 封鎖和非文章頁面造成的，不是 parse 失敗**。但這些框架的「架構模式」值得學習：
- **Trafilatura**：`charset_normalizer` 編碼偵測（已採用）、`htmldate` 日期偵測（已採用為 fallback）、`bare_extraction()` 當 custom parser 失敗的 fallback
- **Scrapy**：AutoThrottle（基於回應延遲自動調速）、Middleware chain（可插拔的 request/response 處理）、信號系統（spider_opened/closed 等事件）
不建議遷移到 Scrapy（Twisted 依賴重、async 支持仍是 wrapper），而是挑選最佳 pattern 整合到現有 asyncio 架構
**信心**：高
**檔案**：`code/python/crawler/parsers/einfo_parser.py`（A/B test 實作）、`code/python/crawler/core/engine.py`（charset_normalizer）
**日期**：2026-02

### Full Scan 速度瓶頸：delay-inside-semaphore 是 rate limiter，調參數而非改架構
**問題**：Full scan 4 個爬蟲同時跑，LTN 理論 ~2.5 req/s 但實際只有 0.4 req/s（6 倍差距）。原因：`_process_one()` 在 semaphore 內 sleep（delay），佔著 concurrent slot 空轉。直覺想法是「把 delay 移到 semaphore 外」，但這與「提高併發數」互相衝突——兩個都做等於對伺服器壓力暴增
**解決方案**：delay-inside-semaphore 本身就是 rate limiter，保留架構不動，改用 `FULL_SCAN_OVERRIDES` 針對 full scan 模式調參：
- 提高併發（5→12）+ 縮短 delay（0.5-1.5s→0.1-0.3s）+ 縮短 timeout（10s→5s）
- 不同來源不同設定（einfo 保守：3 併發 + 1-3s delay）
- 不跳過 candidate URLs（100% coverage 優先於速度）

通用規則：asyncio semaphore + delay 模式中，delay 位置決定了 rate limiting 語義。要加速時調參數（併發數、delay 值），不要同時改架構（移動 delay）又改參數（提高併發）
**信心**：中
**檔案**：`code/python/crawler/core/engine.py`（`_process_one()`、`_apply_full_scan_overrides()`）、`code/python/crawler/core/settings.py`（`FULL_SCAN_OVERRIDES`）
**日期**：2026-02

---

### HTTP Server `--directory` 造成雙重路徑 404
**問題**：用 `python -m http.server 8080 --directory static` 啟動開發 server，但 HTML 中引用 `/static/news-search.css`。Server 以 `static/` 為根目錄，路徑解析為 `static/static/news-search.css` → 404。CSS/JS 全部載不到，頁面空白，console 只顯示 404 錯誤
**解決方案**：從專案根目錄啟動 server（不加 `--directory`）：`python -m http.server 8080`。這樣 `/static/news-search.css` 正確解析為 `./static/news-search.css`。通用規則：`--directory` 改變的是 server 根目錄，HTML 中的絕對路徑（`/static/...`）會從該根開始解析，容易造成路徑重複
**信心**：高
**檔案**：`static/news-search-prototype.html`（HTML 引用路徑）
**日期**：2026-02

### htmldate 比手寫 regex 更可靠的日期提取
**問題**：每個 parser 各自手寫 `_parse_date()`，格式稍有不同就 return None，文章被丟掉
**解決方案**：用 `htmldate.find_date(html, outputformat='%Y-%m-%d')` 作為 fallback。支援幾十種日期格式 + JSON-LD + meta tags + 啟發式偵測。在 einfo 實測，htmldate 成功找到所有日期（包括 custom regex 漏掉的）。用法：custom regex 先試，失敗才 fallback 到 htmldate，避免 htmldate 的計算開銷
**信心**：高
**檔案**：`code/python/crawler/parsers/einfo_parser.py`（`_custom_parse()` 中 htmldate fallback）
**日期**：2026-02

### run_auto 名義上有 concurrent_limit 但實際逐條處理
**問題**：`run_auto` 設定了 `concurrent_limit=5`，但實際是 `for` 迴圈逐條 `await _process_article()`，完全沒有並行。UDN auto 只有 ~26 req/min，遠低於 full scan 的 ~100+ req/min（使用 semaphore+gather）
**解決方案**：改為與 `_run_sequential_scan` 相同的 batch parallel 模式：收集一批 ID → `asyncio.Semaphore(concurrent_limit)` + `asyncio.gather()` 並行處理。Phase 1 收集（跳過已爬）→ Phase 2 並行處理 → 評估結果。通用規則：**設定 concurrent_limit 但沒有使用 semaphore+gather 的 async 函數等於白設定**，要逐一檢查
**信心**：高
**檔案**：`code/python/crawler/core/engine.py`（`run_auto()`）
**日期**：2026-02

### Dashboard API 多處 async 反模式：sequential awaits、sync I/O
**問題**：Dashboard start/stop/resume 操作卡頓 30-90 秒。原因：(1) `start_full_scan` 逐一 auto-detect 3 個 sequential source 的 latest ID（每個最多 30s → 共 90s），(2) `schedule_auto_resume` 逐一 resume zombie tasks，(3) WebSocket broadcast 逐一 send，(4) `_save_tasks` 在 async handler 中同步寫檔
**解決方案**：
1. `_detect_latest_id()` 抽出為獨立方法 + `asyncio.gather()` 並行偵測
2. `schedule_auto_resume` 用 `asyncio.gather()` 並行 resume
3. `_broadcast_status` 用 `asyncio.gather()` + safe wrapper 並行 send
4. `_save_tasks` JSON 序列化在主線程，`run_in_executor` 背景寫檔
通用規則：**任何在 async 函數中的 `for item: await operation(item)` 都是潛在的效能殺手**，優先改成 `gather()`
**信心**：高
**檔案**：`code/python/indexing/dashboard_api.py`
**日期**：2026-02

### 爬蟲資料分布 ≠ 實際文章分布（生存者偏差）
**問題**：分析 UDN 已爬文章的 ID 分布，發現 8.2M-9.1M 之間有大片空白，推測為「dead zone」。但這只是因為 auto（從 9.3M 往回）和 full scan（從 7.8M 往上）各自爬了一段，中間尚未覆蓋，並非文章不存在
**解決方案**：分析爬蟲資料時，必須區分「已爬資料的分布」和「實際文章的分布」。缺少資料點不代表文章不存在——可能只是還沒掃到。只有在 ID 被實際掃過且回傳 404 時才能確認「不存在」
**信心**：高
**檔案**：N/A（分析方法論）
**日期**：2026-02

### 外部 HTTP probe 被 rate limit 會產生嚴重誤導
**問題**：用 aiohttp 批量 probe CNA 600 個 suffix 來驗證每日文章數。結果顯示「190 篇/天，max suffix=200」。據此計算「47% 覆蓋率」，進而推導出「DATE_SCAN_MISS_LIMIT=80 導致過早截斷」的錯誤結論
**實際情況**：probe 在發完 ~200 個請求後被 CNA rate limit，後續 suffix 全部回 404。實際 CNA 每天 ~307 篇，分布在 suffix 1-399。舊爬蟲只抓了 suffix 0-99（88 篇/天），full scan 正確補抓 suffix 100-399（218 篇/天）
**教訓**：
1. **probe 結果必須與 DB 交叉驗證**：光看 HTTP status code 不夠，要對照 crawled_articles 的 task_id 分組 + suffix 分布
2. **rate limit 會截斷結果**：如果只有第一個日期有資料、後續全部 0，幾乎肯定是被封
3. **不要輕信 agent 的根因分析**：agent 拿到被截斷的 probe 數據就推導出錯誤結論，必須獨立驗證
**信心**：高
**日期**：2026-02

### 爬蟲覆蓋率分析必須按 task_id 拆分
**問題**：看到 CNA 每月 ~2,700 篇就以為那是全部輸出。實際上 2,700 只是舊爬蟲（task_id=None）的 suffix 0-99 區間。Full scan 在 suffix 100-399 還找到 ~218 篇/天，但因為 full scan 才跑 19 天，這些新文章只存在於 January 2024
**教訓**：分析爬蟲覆蓋率時：
1. 先 `GROUP BY task_id` 看資料來源
2. 比對不同 task 的 suffix 分布
3. 不要把單一 task 的結果當作網站全部產量
**信心**：高
**日期**：2026-02

### LTN 自動 redirect 使 candidate URLs 完全浪費
**問題**：LTN full scan 設定 `max_candidate_urls=3`，每個 404 額外打 3 個 candidate URL（其他 category + 子站），導致請求量 ~1.6-4 倍放大。Full scan 掃描速度極慢
**實際情況**：LTN 的 server **會自動 redirect** 到正確 category/subdomain。例如用 `news/life/5300000` 請求，server 自動 302 到 `health.ltn.com.tw/5300000`。因此 404 就是真的文章不存在，candidate URL 不可能成功
**解決方案**：LTN 的 `max_candidate_urls` 應設為 **0**。redirect 機制已經保證任何 category 都能找到文章。驗證方法：`aiohttp session.get(url)` 預設 follow redirect，檢查 `resp.url != 原始 url` 即可確認
**教訓**：新增 candidate URL 前，先測試 server 是否支援 redirect。如果支援，candidate 是浪費
**信心**：高
**檔案**：`code/python/crawler/parsers/ltn_parser.py`、`code/python/crawler/core/settings.py`（FULL_SCAN_OVERRIDES）
**日期**：2026-02

### Chinatimes URL 必須包含正確 category code（不像 CNA）
**問題**：Chinatimes full scan 50 天只找到 247 篇文章（5 篇/天）。Primary URL 用 `-260402`（社會），candidate 只加 newspapers-260109 和 opinion-262101，完全沒覆蓋政治(260401)、生活(260405)、國際(260404)、科技(260408)、娛樂(260410)、體育(260412)等主要分類
**對比**：CNA 不需要正確 category（`news/aipl/...` 和 `news/afe/...` 都能 resolve 同一篇文章）。但 Chinatimes 的 URL **必須**包含正確 category code，否則回 404
**教訓**：每個新聞源的 URL routing 機制不同，不能假設都像 CNA 一樣 category-agnostic。加入新 parser 時必須測試：(1) 錯誤 category 是否 redirect？(2) 還是直接 404？
**信心**：高
**檔案**：`code/python/crawler/parsers/chinatimes_parser.py`（`get_url()`、`get_candidate_urls()`）
**日期**：2026-02

### 新聞源月產量驗證：必須用多種方法交叉確認
**問題**：spec 中各來源「月均文章」數字嚴重偏離現實（UDN 寫 3,000 實際 28,000、LTN 寫 4,700 實際 27,000）。單一驗證方法（外部 probe、已爬資料統計、sitemap）各有盲點
**解決方案**：正確的驗證流程需三步交叉：
1. **DB 分析**：`GROUP BY task_id` 拆分不同爬蟲的貢獻，比較 suffix 分布
2. **ID→日期映射**：probe 幾個代表性 ID，建立 ID 增長速率 × hit rate 的月產量估算
3. **Sitemap/列表頁**：確認 sitemap 覆蓋範圍，但注意 sitemap 可能不完整
任何一種方法單獨使用都可能嚴重偏差（probe 被 rate limit、DB 只反映已爬範圍、sitemap 只有近期）
**信心**：高
**檔案**：`docs/indexing-spec.md`（外部驗證數據段落）
**日期**：2026-02

### stderr Pipe Buffer Deadlock（subprocess 未讀取 stderr 導致死鎖）
**問題**：`dashboard_api.py` 的 `_run_crawler_subprocess()` 建立 subprocess 時用 `stderr=asyncio.subprocess.PIPE` 但從未讀取 stderr。快速爬蟲的 log 輸出填滿 Windows 65KB pipe buffer → subprocess 在 `write()` 阻塞 → stdout 也跟著停（同一進程）→ parent 看到計數器凍結。症狀：subprocess 隨機凍結，重啟後短暫恢復，快速爬蟲（LTN/CNA）更容易觸發。整晚發生 9 次凍結才找到 root cause
**解決方案**：為每個 subprocess 建立 `_drain_stderr()` async task，與 stdout reader 同時運行：
```python
async def _drain_stderr():
    while True:
        line = await process.stderr.readline()
        if not line:
            break
stderr_task = asyncio.create_task(_drain_stderr())
```
通用規則：**使用 `subprocess.PIPE` 時，所有被 PIPE 的 fd（stdout + stderr）都必須被讀取**。只需要 stdout 時，stderr 應設為 `DEVNULL` 或建立 drain task。Windows 65KB buffer 比 Linux 更容易觸發此問題
**信心**：高
**檔案**：`code/python/indexing/dashboard_api.py`（`_run_crawler_subprocess()`）
**日期**：2026-02

### Watermark 設為未來日期導致掃描靜默跳過
**問題**：ESG BT 的 `last_scanned_date` 被設為 2026-02-13（未來日期），導致 full scan 啟動時 `scan_start = last_scanned_date + 1 day = 2026-02-14`，而 `scan_end = today = 2026-02-12`。因為 `scan_start > scan_end`，整個掃描範圍為空，task 立即完成且 success=0。沒有錯誤訊息，看起來像「正常完成但找不到文章」
**解決方案**：(1) 啟動 full scan 前，用 `registry.get_scan_watermark(source_id)` 檢查 watermark 是否合理（不是未來日期、不是 NULL 等）；(2) 重置 watermark：`UPDATE scan_watermarks SET last_scanned_date = NULL WHERE source_id = 'xxx'`；(3) `update_scan_watermark()` 只允許 forward（不會自動修復），設計上是正確的，但意味著手動錯誤無法自動恢復
**信心**：高
**檔案**：`code/python/crawler/core/crawled_registry.py`（`update_scan_watermark()`、`get_scan_watermark()`）
**日期**：2026-02

### 修改 long-running process 管理的檔案：必須先停程序
**問題**：Dashboard 在記憶體中持有 `crawler_tasks.json` 全部內容，定期 `_save_tasks()` 寫回檔案。外部直接修改 JSON 檔案後，Dashboard 下次寫檔時以記憶體內容覆蓋修改。更嚴重的是，`taskkill` force kill Dashboard 時如果正好在寫檔，檔案會被截斷為 0 bytes（連備份也來不及保存）
**解決方案**：
1. **修改前必須停程序**：確認 `curl localhost:8001` 無回應後才改檔案
2. **備份在停程序前做**：`shutil.copy2()` 要在程序還活著時就備份，不能等 kill 後才備份已截斷的檔案
3. **或提供 API**：理想方案是加 DELETE/cleanup API endpoint，從記憶體內操作
4. **驗證已停**：Windows 上 terminal 關閉不等於 process 結束，用 `Get-Process python*` 確認
**信心**：高
**檔案**：`data/crawler/crawler_tasks.json`、`code/python/indexing/dashboard_api.py`（`_save_tasks()`）
**日期**：2026-02

### Dashboard API `overrides` 欄位完全無效 — start_id/end_id 必須 top-level
**問題**：呼叫 `/api/indexing/fullscan/start` 時，用 `{"sources":["moea"],"overrides":{"moea":{"start_id":100000,"end_id":122000}}}` 格式傳 start_id/end_id。API 返回 200 但使用了 watermark（122,001）和 config 預設值（end 122,000），導致 start > end → 掃描 0 篇文章。三個文件（deployment prompt + 兩個 spec）都寫了錯誤格式
**根因**：`dashboard_api.py` 中 `overrides` 一詞出現 **0 次**。第 83 行：`start_id = body.get("start_id") or default_start` — 直接從 body top-level 讀取，完全不看 nested overrides
**解決方案**：`start_id`/`end_id` 必須放在 JSON body 最外層：`{"sources":["moea"],"start_id":100000,"end_id":122000}`。`overrides` 結構只存在於 `settings.py` 的 `FULL_SCAN_OVERRIDES`（控制 concurrent_limit/delay_range），不是 API 參數
**信心**：高
**檔案**：`code/python/indexing/dashboard_api.py`（`start_full_scan()`，第 83-84 行）
**日期**：2026-02

### gcloud SSH `pkill -f` 會殺死 SSH session 自身
**問題**：`gcloud compute ssh --command="pkill -f dashboard_server"` 返回 exit code 128。`pkill -f` 匹配的是 process 的完整命令行，而 SSH session 的命令行包含 `dashboard_server` 字串，導致 pkill 把 SSH session 自己也殺了
**解決方案**：(1) 用 `pgrep -f` 先找 PID，再 `kill <PID>` 精確殺；(2) 或用 `pkill` 但接受 exit 128（session 斷但 pkill 已生效）；(3) 複雜操作寫成 VM 上的 shell script（`/tmp/start-dash.sh`），避免長命令行被 SSH 截斷或解析錯誤
**信心**：高
**檔案**：N/A（GCP 操作模式）
**日期**：2026-02

### GCP nohup 啟動服務：必須 script 化，不能裸 command
**問題**：`gcloud ssh --command="nohup python -m indexing.dashboard_server &"` 失敗，因為 (1) 工作目錄是 `$HOME` 不是 `code/python/`；(2) `source venv/bin/activate` 在 `--command` 中不穩定；(3) 複雜命令串（`cd && source && nohup ... &`）常因引號嵌套失敗
**解決方案**：先用簡單 `--command` 建立 script：
```bash
echo '#!/bin/bash
cd /home/User/nlweb/code/python
export CRAWLER_ENV=gcp
/home/User/nlweb/venv/bin/python -m indexing.dashboard_server' > /tmp/start-dash.sh
chmod +x /tmp/start-dash.sh
```
再用 `nohup /tmp/start-dash.sh > log 2>&1 &` 啟動。所有路徑用絕對路徑，不依賴 `source activate`
**信心**：高
**檔案**：N/A（GCP 操作模式）
**日期**：2026-02

*最後更新：2026-02-12*

