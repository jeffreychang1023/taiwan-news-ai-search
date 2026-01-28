---
description: 記錄這次對話學到的 lesson
---

# /learn

分析本次對話，將值得記錄的問題解決方案寫入 lessons-learned.md。

---

## 執行流程

### Step 1：分析對話

回顧本次對話，尋找符合以下條件的內容：

**值得記錄**：
- 解決了非顯而易見的 bug
- 發現了框架/套件的陷阱或限制
- 找到了效能優化方法
- 建立了可重用的 pattern
- 踩過的坑（避免下次再犯）

**不記錄**：
- 瑣碎修復（typo、格式、import）
- 一次性問題（不會再遇到）
- 使用者特定偏好
- 尚未驗證的假設

### Step 2：判斷是否有 lesson

如果沒有值得記錄的內容：
```
本次對話沒有需要記錄的 lesson。
```
結束執行。

### Step 3：分類領域

將 lesson 歸類到：
- **Reasoning**：orchestrator、agents
- **Ranking**：ranking、xgboost、mmr
- **Retrieval**：retriever、bm25、qdrant
- **API / Frontend**：webserver、static、SSE
- **Infrastructure**：DB、cache、config
- **開發環境 / 工具**：Python、套件、開發流程

### Step 4：評估信心等級

| 信心 | 條件 |
|------|------|
| **低** | 第一次遇到，解法可能不完整 |
| **中** | 解決過 2-3 次，或有文件佐證 |
| **高** | 多次驗證，確定有效 |

### Step 5：寫入 lessons-learned.md

讀取 `.claude/memory/lessons-learned.md`，在對應領域區塊追加：

```markdown
### [簡短標題]
**問題**：[遇到什麼問題]
**解決方案**：[如何解決]
**信心**：[低/中/高]
**檔案**：`[相關檔案路徑]`
**日期**：[YYYY-MM]
```

### Step 6：更新最後更新日期

更新檔案底部的 `*最後更新：YYYY-MM-DD*`

---

## 範例輸出

```
=== /learn 執行結果 ===

分析本次對話...

找到 1 個值得記錄的 lesson：

1. **Async Queue Race Condition**
   - 領域：Infrastructure
   - 信心：高
   - 已寫入 lessons-learned.md

本次對話的 lesson 已記錄完成。
```

---

## 注意事項

- 一次對話可能有 0~N 個 lessons
- 如果已存在類似 lesson，考慮更新信心等級而非新增
- 保持描述簡潔，重點是「下次遇到時能快速回憶」
