---
name: update-docs
description: |
  定期維護專案文件，同步程式碼與文件的一致性。結合 git 分析、對話摘要、程式碼結構掃描來更新文件。
  觸發時機：(1) 用戶輸入 /update-docs，(2) 完成功能開發後需要記錄進度，(3) 架構變更後需要更新文件。
  支援參數：all（全部）、progress（進度相關）、architecture（架構相關）。
---

# Update Docs

同步專案文件與程式碼的一致性。

## 參數

| 參數 | 更新範圍 |
|------|----------|
| `all` 或無參數 | 全部文件 |
| `progress` | CONTEXT.md, PROGRESS.md, COMPLETED_WORK.md, NEXT_STEPS.md |
| `architecture` | systemmap.md, state-machine-diagram.md |

## 文件分工

| 文件 | 定位 | 更新策略 |
|------|------|----------|
| `CLAUDE.md` | 專案入口指引 | 更新模組狀態表、開發重點 |
| `.claude/CONTEXT.md` | 當前工作上下文 | 從對話摘要更新 |
| `.claude/PROGRESS.md` | 開發進度 | 從 git log + 對話摘要更新 |
| `.claude/COMPLETED_WORK.md` | 已完成工作 | 追加新完成項目 |
| `.claude/NEXT_STEPS.md` | 下一步規劃 | 移除已完成、新增待辦 |
| `.claude/systemmap.md` | 靜態結構 | 模組清單、API、檔案對應 |
| `docs/architecture/state-machine-diagram.md` | 動態流程 | Mermaid 狀態圖 |
| `static/architecture.html` | 視覺化 | **手動維護**，skill 會提醒 |

## 執行流程

### 1. 收集資訊

```bash
# Git 變更分析
git diff --stat HEAD~10
git log --oneline -20

# 程式碼結構掃描
python tools/indexer.py --index
```

掃描以下目錄的結構變化：
- `code/python/` - 主要程式碼
- `code/python/reasoning/` - Reasoning 系統
- `code/python/core/` - 核心模組

### 2. 分析變更

比較現有文件與實際程式碼：
- 檢查模組是否新增/刪除/重命名
- 檢查 API 端點是否變更
- 檢查狀態機流程是否變更

### 3. 更新文件

依參數決定更新範圍，直接編輯文件。

**progress 範圍**：
1. 從對話中提取完成的工作 → 更新 COMPLETED_WORK.md
2. 從對話中提取目前狀態 → 更新 CONTEXT.md
3. 從 git log 提取最近進度 → 更新 PROGRESS.md
4. 移除已完成項目 → 更新 NEXT_STEPS.md

**architecture 範圍**：
1. 掃描程式碼結構 → 更新 systemmap.md 的模組清單
2. 檢查資料流變更 → 更新 state-machine-diagram.md

**all 範圍**：
1. 執行 progress + architecture
2. 更新 CLAUDE.md 的模組狀態表

### 4. 提醒手動維護

完成後輸出：
```
architecture.html 需要手動更新。請在瀏覽器中開啟並編輯視覺化架構圖。
```

### 5. Git 整合

詢問用戶：
```
是否要 commit 這些文件變更？(y/n)
```

若用戶同意，執行：
```bash
git add CLAUDE.md .claude/*.md docs/architecture/*.md
git commit -m "docs: update project documentation"
```

## 文件格式規範

### CONTEXT.md 格式

```markdown
# 當前工作上下文

## 目前狀態
[簡述目前在做什麼]

## 最近完成
- [項目1]
- [項目2]

## 待解決問題
- [問題1]

## 相關檔案
- `path/to/file.py` - 說明
```

### PROGRESS.md 格式

```markdown
# 開發進度

## 2026-01-28
- [x] 完成項目1
- [x] 完成項目2
- [ ] 進行中項目

## 2026-01-27
...
```

### systemmap.md 靜態結構重點

- 模組清單（M0-M6）及狀態
- 關鍵檔案對應表
- API 端點清單
- SSE 訊息類型

### state-machine-diagram.md 動態流程重點

- Mermaid 狀態圖
- 狀態轉換條件
- 錯誤處理流程
