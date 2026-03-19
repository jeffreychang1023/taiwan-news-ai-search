---
description: 啟動 Planner Agent 做高層架構規劃（不寫程式碼）。觸發：「規劃」「高層計劃」「先想想」「/high-level-plan」。不適用於已明確知道要改哪些檔案的小修改。
---

# /high-level-plan

在編碼前建立架構層級的實作策略。

## Gotchas

- **不要在計劃確認前寫任何程式碼** — 這個 skill 的唯一產出是計劃文字，等使用者說「確認」再動手。
- **不要跳過 systemmap.md** — 影響模組表必須根據實際模組狀態填寫，不能憑印象。
- **別和 superpowers:writing-plans 混淆** — 本 skill 做「要不要做、影響哪些模組」；writing-plans 做「具體怎麼改、TDD 步驟」。high-level-plan 是 writing-plans 的前置步驟。

## 定位

規劃流程第一步——回答「要不要做、影響哪些模組、有什麼風險」。不包含具體程式碼或 test cases。

## 執行步驟

1. 讀取 `docs/reference/systemmap.md` 了解模組狀態
2. 讀取 `docs/status.md` 了解目前重點
3. 輸出結構化計劃（需求摘要、影響模組表、實作步驟含檔案路徑、風險評估、複雜度）
4. **等待使用者確認後才進入下一步**

## 確認後的下一步

| 複雜度 | 建議下一步 |
|--------|-----------|
| 簡單（單檔案，< 50 行） | 直接實作 |
| 中等（2-5 個檔案） | `superpowers:writing-plans` 展開為 TDD 細部計畫 |
| 複雜（跨模組） | `superpowers:writing-plans` 產出計畫檔 → `superpowers:executing-plans` 分批執行 |
