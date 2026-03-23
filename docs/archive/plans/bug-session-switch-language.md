# Bug: Session 內切換搜尋 → 摘要語言變英文 + 品牌文字還原

> **發現日期**: 2026-03-23
> **發現者**: CEO 人工 E2E 測試
> **嚴重度**: Medium（影響 UX，不影響功能）
> **狀態**: 待調查

---

## 症狀

在同一個 session 內：
1. 搜尋 A → 摘要正常（繁體中文）
2. 切換到同 session 的歷史搜尋 B，再切回搜尋 A
3. 搜尋 A 的摘要**變成英文**
4. 來回切幾次後，**全部搜尋都變英文**
5. Source-info 文字從「讀豹基於 N 則報導生成」還原為舊版「⚠️ 資料來源：基於 N 則報導生成」

## 重現步驟

1. 開啟 http://localhost:8000，登入
2. 搜尋「台灣經濟」→ 確認摘要是中文、source-info 是「讀豹基於...」
3. 在同一個 session 點擊左側另一個歷史搜尋
4. 再點回「台灣經濟」的搜尋
5. 觀察：摘要語言和 source-info 文字是否改變

## 背景

- **Prompt 改造**（2026-03-23 commit `34c708a`）：所有 prompts.xml 從英文改為繁體中文
- **UI Redesign Phase 5**（2026-03-20）：「⚠️ 資料來源」改為「讀豹基於...」
- 新搜尋的結果是正確的（中文摘要 + 新品牌文字）
- 切換到舊搜尋再切回後，文字還原為舊版

## 假說

### H1: localStorage sessionHistory 快取舊版渲染結果
- `sessionHistory` 存的是已渲染的搜尋結果（包含 HTML 或文字）
- 切到舊搜尋時，從 localStorage 載入舊版結果（英文摘要 + 舊品牌文字）
- 切回時，re-render 用了快取而非原始資料
- **驗偽**：查 `sessionHistory` 的資料結構，確認存的是原始資料還是渲染後的 HTML

### H2: 切換搜尋時觸發 re-render，走了不同 code path
- 初始搜尋結果走 SSE → progressive render → 正確模板
- 從歷史恢復走 `restoreSession` / `loadSavedSession` → 舊模板或舊邏輯
- source-info 文字在 progressive render 和 restore 兩個地方各有一份
- **驗偽**：搜尋 `source-info` 和 `資料來源` 在 `news-search.js` 的所有出現位置

### H3: 切換時觸發了額外的 LLM call（用舊 prompt）
- 可能性最低：不太可能切換搜尋會觸發新的 LLM call
- 但如果有 re-search 或 re-summarize 邏輯，可能用了殘留的舊 prompt
- **驗偽**：切換搜尋時查 server terminal 是否有新的 request log

## 調查方向

1. **前端優先**：搜尋 `restoreSession`、`loadSavedSession`、`renderConversationHistory` 在 `news-search.js` 的邏輯
2. **source-info 文字**：`grep -n "資料來源\|讀豹基於\|source-info" static/news-search.js`
3. **sessionHistory 結構**：確認存原始資料（可重新渲染）還是存渲染結果（快取過期問題）

## 相關檔案

- `static/news-search.js` — 前端 session 管理、搜尋結果渲染
- `config/prompts.xml` — LLM prompt（已改繁中）
- `memory/lessons-frontend.md` — 前端相關教訓
