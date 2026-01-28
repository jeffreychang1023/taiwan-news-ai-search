---
description: 顯示專案狀態
---

# /status

顯示 NLWeb 專案目前狀態摘要。

## 執行步驟

讀取並摘要顯示：
1. `.claude/CONTEXT.md` - 目前重點
2. `.claude/NEXT_STEPS.md` - 下一步計劃
3. `.claude/systemmap.md` - 模組狀態

## 輸出格式

```
=== NLWeb 專案狀態 ===

目前重點：
[從 CONTEXT.md 提取 1-2 項]

模組狀態：
┌─────────────────────┬────────┐
│ M0 Indexing         │ 🔴 規劃中 │
│ M1 Input            │ 🟡 部分完成 │
│ M2 Retrieval        │ 🟡 部分完成 │
│ M3 Ranking          │ 🟢 完成 │
│ M4 Reasoning        │ 🟢 完成 │
│ M5 Output           │ 🟡 部分完成 │
│ M6 Infrastructure   │ 🟢 完成 │
└─────────────────────┴────────┘

下一步（前 3 項）：
1. [從 NEXT_STEPS.md 提取]
2. ...
3. ...

最近完成：
- [從 PROGRESS.md 提取最新里程碑]
```

## 使用時機

- 開始新 session 時
- 忘記目前進度時
- 需要快速了解專案狀態時
