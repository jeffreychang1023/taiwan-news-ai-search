---
description: |
  記錄 lessons + 更新專案文件。整合了 /learn 和 /update-docs。
  觸發：(1) 用戶輸入 /learn，(2) 完成功能開發後，(3) 架構變更後，(4) 用戶說「更新文件」「記一下」。
  支援參數：all（全部）、lessons（只記 lessons）、docs（只更新 docs/）、progress、specs、decisions、patterns。
---

# /learn

記錄教訓 + 更新專案文件。一個指令做完所有持久化工作。

---

## 兩大職責

| 職責 | 更新什麼 | 檔案位置 |
|------|---------|---------|
| **Lessons** | 技術教訓、踩坑記錄 | `memory/lessons-*.md` |
| **Docs** | 專案狀態、規格、決策、完成工作 | `docs/` 目錄 |

**原則**：「更新文件」= docs/ + memory/，兩邊都要做。

---

## 參數

| 參數 | 範圍 |
|------|------|
| `all` 或無參數 | Lessons + Docs 全部 |
| `lessons` | 只記 lessons（memory/ 檔案） |
| `docs` | 只更新 docs/ 目錄 |
| `progress` | `docs/status.md`, `docs/archive/completed-work.md`, `CLAUDE.md` |
| `specs` | `docs/specs/*-spec.md` |
| `decisions` | `docs/decisions.md` |
| `patterns` | `memory/delegation-patterns.md` |

---

## 執行流程

### Part A：Lessons（memory/）

#### A1. 分析對話

回顧本次對話，找：
- 解決了非顯而易見的 bug
- 發現框架/套件的陷阱或限制
- 踩過的坑（避免下次再犯）
- 新的 pattern 或 best practice
- 派工經驗（delegation patterns 更新）

**不記錄**：瑣碎修復、一次性問題、尚未驗證的假設。

#### A2. 分類到正確的 lessons 檔案

| 問題領域 | 寫入檔案 |
|---------|---------|
| Crawler / Dashboard | `memory/lessons-crawler.md` |
| VPS / Docker / 部署 / 資安 | `memory/lessons-infra-deploy.md` |
| 其他（前端、後端、DB、工具） | `memory/lessons-general.md` |

#### A3. 寫入格式

```markdown
### [簡短標題]
**問題**：[遇到什麼問題]
**解決方案**：[如何解決]
**信心**：[低/中/高]
**檔案**：`[相關檔案路徑]`
**日期**：YYYY-MM-DD
```

#### A4. 更新 delegation-patterns.md（如果有派工經驗）

- 新增的模組指引
- 發現的陷阱或依賴關係
- 新的 spec 檔案

---

### Part B：Docs（docs/）

#### B1. 收集資訊

```bash
git diff --stat HEAD~10
git log --oneline -20
```

#### B2. 更新文件（依參數決定範圍）

| 優先順序 | 文件 | 更新策略 |
|---------|------|---------|
| 1 | `docs/specs/*-spec.md` | 根據程式碼變更更新規格 |
| 2 | `docs/status.md` | 從對話 + git log 更新狀態 |
| 3 | `docs/archive/completed-work.md` | 追加完成項目 |
| 4 | `docs/decisions.md` | 追加新決策 |
| 5 | `CLAUDE.md` | 更新模組狀態表與開發重點 |
| 6 | `memory/delegation-patterns.md` | 更新派工經驗 |

#### B3. Source of Truth 優先順序

```
程式碼 → Spec → Docs 指南 → Systemmap → Progress
```

高層級文件根據低層級文件更新，不是反過來。

---

## 完成後輸出

```
=== /learn 完成 ===

Lessons：
- [N] 個 lesson 已記錄到 memory/lessons-*.md
- delegation-patterns.md [已更新/無需更新]

Docs：
- [列出更新的檔案]

是否要 commit？(y/n)
```

若用戶同意：
```bash
git add docs/ memory/ CLAUDE.md
git commit -m "docs: update documentation and lessons learned"
```

---

## 注意事項

- 如果已存在類似 lesson，更新信心等級而非新增
- `docs/status.md` 的「最近完成」不要無限增長，超過 10 項就移到 `completed-work.md`
- 決策記錄要更新 decisions.md 的計數（共 N 筆）
- **MEMORY.md 是純索引**：不寫實質內容，只放指標
