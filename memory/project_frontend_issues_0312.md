---
name: Frontend Issues from E2E Testing (2026-03-12)
description: CEO 人工 E2E 測試發現的前端問題 + 搜尋 regression，記錄修復狀態
type: project
---

## 前端問題清單（2026-03-12 E2E 測試發現）

FE-1~6 全部 FIXED (2026-03-12)

---

## 搜尋 Regression（2026-03-12 CEO 手動發現，待查）

CEO 手動測試發現搜尋品質 regression，明天(03-13)查：

### SR-1: 多元性不見
- **問題**: 搜尋結果缺乏多樣性（可能 MMR 沒生效）
- **可能原因**: WindowsSelectorEventLoopPolicy 影響？MMR 邏輯問題？retrieval 回的結果本身就不多元？

### SR-2: 摘要仍有英文
- **問題**: CEO 實測仍看到英文摘要（但 E2E agent 測試 3/3 PASS）
- **可能原因**:
  - prompts.xml 修改後 server 可能沒重啟（config 需重啟才生效）
  - 或是 E2E agent 測試的時機剛好 server 已重啟，但 CEO 測的時候還沒
  - 明天重啟 server 後再驗證

### SR-3: 日期跑掉
- **問題**: 搜尋結果中日期顯示異常（不是 FE-3 的 session 日期，是搜尋結果裡的文章日期）
- **可能原因**: 待查

**Why:** Login 系統整合後的 E2E 測試，先修前端再發現搜尋品質也有 regression
**How to apply:** 依序排查 SR-1~3。先確認 server 已重啟套用 prompts.xml，再逐一驗證。

---

## Session 切換問題（2026-03-13 修復）

### SS-1: 搜尋中切 session 結果遺失 ✅ FIXED
- **方案**: Cancel + Retry Button（`interruptedSearch` 標記 + `showInterruptedSearchNotice`）
- **嘗試過的失敗方案**: auto re-search（無限迴圈）→ 背景 stream 繼續（stale ref + 污染）→ single-stream-per-mode（卡住）
- **教訓**: 簡單方案優先，背景 stream 狀態管理是假需求

### SS-2: Login Code Review 修復 ✅ FIXED
- CRITICAL(3) + HIGH(5) + MEDIUM(5) + LOW(2)
- Deep Research 401 fix（PUBLIC_ENDPOINTS）
- Session cleanup type error（time.time() → datetime）
