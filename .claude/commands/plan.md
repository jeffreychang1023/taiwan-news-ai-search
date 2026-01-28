---
description: 啟動 Planner Agent 規劃複雜任務
---

# /plan

在編碼前調用 Planner Agent 建立實作策略。

## 執行步驟

1. 讀取 `.claude/agents/planner.md` 載入規劃指引
2. 讀取 `.claude/systemmap.md` 了解模組狀態
3. 讀取 `.claude/CONTEXT.md` 了解目前重點
4. 根據使用者需求輸出結構化計劃
5. **等待使用者確認後才開始實作**

## 使用時機

- 新功能開發
- 重大架構變更
- 跨模組修改
- 不確定從何開始時
- 需求不夠明確時

## 輸出格式

計劃將包含：
- 需求摘要
- 影響模組表
- 實作步驟（含具體檔案路徑）
- 風險評估
- 複雜度評估

## 範例

```
User: /plan 新增 Web Search 功能到 M2 Retrieval

Claude: [讀取 systemmap.md, CONTEXT.md]
        [輸出結構化計劃]
        請確認以上計劃後，我才會開始實作。
```
