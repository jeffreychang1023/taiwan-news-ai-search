---
name: E2E 測試必須模擬人類操作
description: E2E 測試必須用 DevTools fill/click 操作 UI，不可用 fetch() 繞過前端。API test ≠ E2E test。
type: feedback
---

E2E 測試必須模擬人類使用者操作（navigate → snapshot → fill → click → verify），不可用 `evaluate_script` + `fetch()` 直接打 API。

**Why:** fetch() 繞過前端 UI，無法發現表單缺欄位、JS handler 有 bug 等前端問題。2026-03-12 B2B 測試 14/14 API test PASS，但前端註冊表單缺 org_name 欄位，人工測試立刻失敗。

**How to apply:** 派 E2E 測試 subagent 時，prompt 必須明確寫「模擬人類使用者操作，不要用 fetch() 繞過 UI」。用 fill/click 操作表單，用 snapshot/screenshot 驗證結果。如果需要測純 API（無 UI），明確標記為「API test」。

### E2E 通過的 evidence 必須來自 screenshot，不可用 console/DOM

**Why:** 2026-03-20 Guardrail E2E，Agent 用 console 訊息和 `evaluate_script` DOM 查詢報 PASS（「error message 在 DOM 裡」），但 CEO 人工測試發現畫面完全看不到訊息（CSS `display:none`）。Console/DOM 有訊息 ≠ 使用者看得到。Agent 偷看後台是作弊，不是測試。

**How to apply:** E2E 測試的 PASS 判定標準：**能在 screenshot 或 snapshot 的視覺輸出中讀到目標文字**。以下不算 evidence：(1) console.log 輸出 (2) evaluate_script 查 DOM innerHTML (3) network response body (4) 「code path 存在」的 code review。派工 prompt 必須明確寫「不可用 console/DOM/network 當通過依據，只能用 screenshot/snapshot 視覺確認」。
