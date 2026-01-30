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

---

*最後更新：2026-01-30*

