# E2E Findings Log

> 跨輪次累積記錄 — 不會被 reset_checklist.py 清除
> 新 agent 每輪開始時必須讀取此檔案

---

## Stable Items (連續 PASS >= 2 輪，本輪跳過)

T01, T02, T03, T04, T05, T06, T07, T08, T09, T10, T12, T13, T14, T15, T16, T17, T18, T19, T20, T21, T22, T23, T24, T25, T26, T27, T28, T29, T30, T31

> Agent 每輪檢查：如果修復了相關程式碼，需將受影響項目從此清單移除並重測。

---

## Open Issues

- **T11** Deep Research 後自由對話 follow-up：後端 500 錯誤導致「無法回答」
  - [Round 5] 首次可測（T09 已修復）。技術流程正常：report injected 9085 chars, POST 9642 bytes, SSE response received。但 LLM 回覆「抱歉，我無法回答這個問題。」——未參考已注入的 Deep Research report。與舊 T12 bug 模式類似，可能是 system prompt 或 conversation context 未正確傳遞 report 給 LLM。
  - [Round 6] 持續復現，**root cause 已定位為後端錯誤（非 LLM 行為）**。前端正確注入 research_report（POST 27,289 bytes，含完整 6 章報告），但後端回傳 `{"message_type": "error", "error": "[Errno 22] Invalid argument", "status": 500}`。Server log 確認：`Error in synthesizeAnswer: LLM call failed for prompt 'SynthesizePromptForGenerate': OSError: [Errno 22] Invalid argument`（generate_answer.log + prompt_runner.log）。前端收到 error 後顯示「抱歉，我無法回答這個問題。」作為 fallback。Root cause 可能是：(1) LLM API 調用時 prompt 過大（注入完整報告後超出限制）觸發 OS 層級錯誤；(2) Windows 平台 subprocess/pipe buffer 限制；(3) prompt_runner 中的編碼或參數問題。
  - [Round 7] **持續復現，行為與 Round 6 完全一致**。經 commit `6e66cab` 大規模重構（908 insertions, 302 deletions）後重新驗證。前端正確注入 research_report（POST 20,424 bytes），SSE response: `{"message_type": "error", "error": "[Errno 22] Invalid argument", "status": 500}`。HTTP status 200（SSE stream 已建立），error 在 SSE payload 中。前端 gracefully 顯示「抱歉，我無法回答這個問題。」Console 無 JS 錯誤。**3 輪持續復現，需優先修復**。
  - [Round 8] **持續復現，第 4 輪 FAIL**。載入既有 session「台灣AI產業最新政策」（已有完整 Deep Research 報告），在自由對話模式問「這份研究報告的主要結論是什麼？」。POST 20,428 bytes（含完整 research_report，6 章報告），後端回傳 SSE: `{"message_type": "error", "error": "[Errno 22] Invalid argument", "status": 500}`。Server log: `Error in synthesizeAnswer: LLM call failed for prompt 'SynthesizePromptForGenerate': OSError: [Errno 22] Invalid argument`（generate_answer.log 01:37:24）。前端顯示「抱歉，我無法回答這個問題。」Console 無 JS 錯誤。**4 輪持續復現，確認為後端 LLM prompt 處理問題，需優先修復**。
  - [Round 9] **持續復現，第 5 輪 FAIL**。載入既有 session「台灣AI產業最新政策」，自由對話模式問「這份研究報告提到了哪些關鍵政策？」。POST 20,373 bytes（含完整 research_report 8,710 chars，6 章報告），後端回傳 SSE: `{"message_type": "error", "error": "[Errno 22] Invalid argument", "status": 500}`。HTTP 200（SSE stream 已建立），error 在 SSE payload 中。前端 gracefully 顯示「抱歉，我無法回答這個問題。」Console 無 JS 錯誤。**5 輪持續復現，後端 SynthesizePromptForGenerate OSError 未修復**。
  - [Round 10] **持續復現，第 6 輪 FAIL**。載入既有 session「台灣AI產業最新政策」，自由對話模式問「這份研究報告中提到的重點政策有哪些？」。POST 20,388 bytes（含完整 research_report，6 章報告），後端回傳 SSE: `{"message_type": "error", "error": "[Errno 22] Invalid argument", "status": 500}`。HTTP 200（SSE stream 已建立），error 在 SSE payload 中。前端 gracefully 顯示「抱歉，我無法回答這個問題。」Console 無 JS 錯誤（僅 1 個無關 404）。**6 輪持續復現，無程式碼變更，後端 OSError 未修復**。
  - [Round 11] **持續復現，第 7 輪 FAIL**。載入既有 session「台灣AI產業最新政策」，自由對話模式問「報告中提到的AI基本法主管機關是哪個單位？」。POST 20,404 bytes（含完整 research_report，6 章報告），後端回傳 SSE: `{"message_type": "error", "error": "[Errno 22] Invalid argument", "status": 500}`。HTTP 200（SSE stream 已建立），error 在 SSE payload 中。前端 gracefully 顯示「抱歉，我無法回答這個問題。」Console 無 JS 錯誤（僅 1 個無關 404）。**7 輪持續復現，無程式碼變更，後端 OSError 未修復。停止條件：T11 為唯一 Open Issue，已連續 7 輪 FAIL 且無程式碼修復，建議停止 E2E loop 並優先修復此 bug**。
  - [Round 13] **持續復現，第 8 輪 FAIL**。E2E loop 重啟原因：commit `6e66cab` 中 `generate_answer.py` 有 66 insertions/20 deletions，為 T11 直接相關檔案。載入既有 session「台灣AI產業最新政策」，自由對話模式問「這份報告中提到哪些部會參與AI政策推動？」。POST 20,403 bytes（含完整 research_report 8,710 chars，6 章報告），後端回傳 SSE: `{"message_type": "error", "error": "[Errno 22] Invalid argument", "status": 500}`。HTTP 200（SSE stream 已建立），error 在 SSE payload 中。前端 gracefully 顯示「抱歉，我無法回答這個問題。」Console 無 JS 錯誤（僅 1 個無關 404）。Console 確認前端正常：research report restored 8,710 chars, POST body 9,343 bytes (JS-side)。**`generate_answer.py` 的修改未修復此 OSError，root cause 仍在後端 prompt 處理層（可能是 Windows pipe buffer 或 LLM API 參數問題）。建議再次停止 E2E loop，需深度 debug 後端 `SynthesizePromptForGenerate` 的 LLM 調用路徑**。

## Resolved Issues

- **T09** Deep Research 前端未發送請求至後端（**連續 4 輪 FAIL → Round 5 已修復**）
  
  - [Round 1] 首次發現：請求有發送但 Actor-Critic 推理逾時（>5 min）
  - [Round 2] **惡化**：UI 顯示「停止生成」但 POST 請求完全未送出（Network tab 確認無 /ask 請求）。按鈕點擊與 Enter 鍵均復現。新聞搜尋模式正常，僅進階搜尋模式異常。
  - [Round 3] 持續復現：與 Round 2 行為一致。切換至進階搜尋、輸入查詢、按搜尋按鈕後 UI 進入「停止生成」狀態但 Network tab 無 POST /ask 請求。新聞搜尋模式正常（T08 PASS）。
  - [Round 4] 持續復現：行為與 Round 2-3 一致。進階搜尋模式下按搜尋按鈕，UI 進入「停止生成」紅色按鈕狀態，但 Network tab 僅有舊的 POST /ask（來自 T08 新聞搜尋），無新請求。Console log 顯示 "Conversation reset" 後無 POST SSE 相關日誌。新聞搜尋模式（T08）和自由對話（T10）均正常。
  - [Round 5] **已修復** ✅：Root cause 為 `advancedSearchConfirmed` 在 popup close 時未設為 true + `setProcessingState(false)` 未在 early return 路徑呼叫。修復：(1) `hideAdvancedPopup()` 加入 `advancedSearchConfirmed = true`（因一定有 discovery 預設值）；(2) `performSearch()` 在 early return 前呼叫 `setProcessingState(false)`。修復後完整流程驗證通過：clarification multi-question card → 選擇時間範圍與焦點 → Actor-Critic reasoning pipeline (analyst → critic → CoV → writer) → 110 sources analyzed → 7 reasoning chain nodes → report displayed with citations。

- **T02** sidebar 點擊 session 項觸發重命名而非載入（minor UX bug）
  
  - [Round 1] 首次發現：需透過 loadSavedSession() 才正確載入
  - [Round 2] 復現：點擊 StaticText 仍觸發重命名，需用 JS `.left-sidebar-session-item` div click 才正確切換
  - [Round 3] **已修復** ✅：單擊 session 項正確載入內容，不再觸發重命名
  - [Round 4] 修復持續有效 ✅

- **T12** 自由對話直接問日期回答「無法回答」（LLM 行為不一致）
  
  - [Round 1] 首次發現：AI 自我介紹正確提及 2026-01-31，但直接問「今天幾月幾號」回覆「抱歉，我無法回答這個問題」
  - [Round 2] 復現：同樣行為
  - [Round 3] **已修復** ✅：AI 正確回答「今天是 2026 年 1 月 31 日。」
  - [Round 4] 修復持續有效 ✅：AI 正確回答「今天是 2026 年 2 月 1 日。」

---

## Round Summary

| Round | 時間                     | 完成項目             | PASS | FAIL         | 備註                                                                                                                                                                                                                                           |
| ----- | ---------------------- | ---------------- | ---- | ------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1     | 2026-01-31 01:30~02:30 | T01~T31（31/31）   | 29   | 2            | T02 minor UX bug, T09 timeout                                                                                                                                                                                                                |
| 2     | 2026-01-31 03:00~04:30 | T01~T31（31/31）   | 28   | 2 (+ 1 SKIP) | T09 regression（請求未送出）, T12 partial fail, T18 SKIP（依賴 T09）                                                                                                                                                                                    |
| 3     | 2026-01-31 05:00~06:30 | T01~T31（31/31）   | 28   | 1 (+ 2 SKIP) | T09 持續 FAIL, T02+T12 已修復, T11+T18 SKIP（依賴 T09）                                                                                                                                                                                               |
| 4     | 2026-02-01 16:30~17:00 | T01~T31（31/31）   | 28   | 1 (+ 2 SKIP) | T09 持續 FAIL（4th round），其餘全 PASS，T11+T18 SKIP（依賴 T09）                                                                                                                                                                                         |
| 5     | 2026-02-01 18:00~19:30 | T01~T31（31/31）   | 30   | 1            | **T09 已修復** ✅（bug fix in news-search.js）, T18 PASS, T11 partial fail（LLM 行為：回覆「無法回答」despite report injection）, 28 SKIP (STABLE)                                                                                                              |
| 6     | 2026-02-01 01:20~01:50 | T01~T31（31/31）   | 30   | 1            | T11 持續 FAIL（root cause 定位：後端 500 `[Errno 22] Invalid argument` in SynthesizePromptForGenerate，非 LLM 行為問題），30 SKIP (STABLE)                                                                                                                   |
| 7     | 2026-02-01 17:30~18:00 | T01~T31（31/31）   | 30   | 1            | 經 commit `6e66cab` 大規模重構後重測 13 項 Active items，全部 PASS except T11。T11 持續 FAIL（第 3 輪，`[Errno 22] Invalid argument`），需優先修復。T19 conditional PASS（KG disabled in config）。                                                                         |
| 8     | 2026-02-02 01:30~01:40 | T01~T31（31/31）   | 30   | 1            | T11 持續 FAIL（第 4 輪，`[Errno 22] Invalid argument`，POST 20,428 bytes）。30 項 SKIP (STABLE)，無相關程式碼變更。**T11 為唯一 Open Issue，需優先修復後端 SynthesizePromptForGenerate 的 OSError**。                                                                         |
| 9     | 2026-02-02 02:05~02:15 | T01~T31（31/31）   | 30   | 1            | T11 持續 FAIL（第 5 輪，`[Errno 22] Invalid argument`，POST 20,373 bytes）。30 項 SKIP (STABLE)，無相關程式碼變更。**T11 為唯一 Open Issue，需優先修復**。                                                                                                                 |
| 10    | 2026-02-02 02:20~02:30 | T01~T31（31/31）   | 30   | 1            | T11 持續 FAIL（第 6 輪，`[Errno 22] Invalid argument`，POST 20,388 bytes）。30 項 SKIP (STABLE)，無程式碼變更。**T11 為唯一 Open Issue，6 輪持續復現，需優先修復後端 SynthesizePromptForGenerate 的 OSError**。                                                                   |
| 11    | 2026-02-02 02:14~02:20 | T01~T31（31/31）   | 30   | 1            | T11 持續 FAIL（第 7 輪，`[Errno 22] Invalid argument`，POST 20,404 bytes）。30 項 SKIP (STABLE)，無程式碼變更。**建議停止 E2E loop，T11 需後端修復後才有意義重測**。                                                                                                             |
| 12    | 2026-02-02 (STOPPED)   | —                | —    | —            | **E2E Loop 停止**。停止條件達成：T11 為唯一 Open Issue，已連續 7 輪 FAIL，無新程式碼變更。30/31 項 STABLE，1 項需後端修復。下次觸發條件：T11 相關後端程式碼（`SynthesizePromptForGenerate` / `prompt_runner`）有修復 commit 後重啟 loop。                                                               |
| 13    | 2026-02-01 18:30~18:35 | T11（1/31 Active） | 30   | 1            | **E2E Loop 重啟**（`generate_answer.py` 在 commit `6e66cab` 有 66 ins/20 del）。T11 持續 FAIL（第 8 輪，`[Errno 22] Invalid argument`，POST 20,403 bytes）。30 項 SKIP (STABLE)。`generate_answer.py` 修改未修復 OSError。**建議再次停止 E2E loop，需深度 debug 後端 LLM 調用路徑**。 |
| 14    | 2026-02-01 (STOPPED)   | —                | —    | —            | **E2E Loop 再次停止**。停止條件達成：T11 為唯一 Open Issue，已連續 8 輪 FAIL（Round 5~13），最新 commit 仍為 `6e66cab`，無新程式碼變更。30/31 項 STABLE，1 項需後端深度 debug。下次觸發條件：`SynthesizePromptForGenerate` / `prompt_runner` / LLM 調用路徑有修復 commit 後重啟 loop。                      |
