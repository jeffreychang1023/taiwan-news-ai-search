---
description: 啟動 Planner Agent 做高層架構規劃（不寫程式碼）
---

# /high-level-plan

在編碼前調用 Planner Agent 建立架構層級的實作策略。

## 定位

這是規劃流程的**第一步**——回答「要不要做、影響哪些模組、有什麼風險」。
不包含具體程式碼或 test cases。

## 執行步驟

1. 讀取 `.claude/agents/planner.md` 載入規劃指引
2. 讀取 `docs/reference/systemmap.md` 了解模組狀態
3. 讀取 `docs/status.md` 了解目前重點
4. 根據使用者需求輸出結構化計劃
5. **等待使用者確認後才進入下一步**

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

## 確認後的下一步

使用者確認 high-level plan 後，根據複雜度選擇：

| 複雜度 | 建議下一步 |
|--------|-----------|
| **簡單**（單檔案，< 50 行） | 直接實作 |
| **中等**（2-5 個檔案） | 用 `superpowers:writing-plans` 展開為 TDD 細部計畫 |
| **複雜**（跨模組） | 用 `superpowers:writing-plans` 產出計畫檔 → `superpowers:executing-plans` 分批執行 |

## 範例

```
User: /high-level-plan 新增 Web Search 功能到 M2 Retrieval

Claude: [讀取 systemmap.md, CONTEXT.md]
        [輸出結構化計劃]

        這是複雜任務（跨 M2+M4 模組），確認後建議用
        superpowers:writing-plans 展開細部執行計畫。

        請確認以上計劃。
```
