---
description: |
  觸發：/learn、完成功能開發後、架構變更後、「更新文件」「記一下」「記錄教訓」。
  不觸發：只問問題、只讀文件、沒有新知識產生的對話。
  參數：all（預設）、lessons、docs、progress、specs、decisions、patterns。
---

# /learn

記錄教訓 + 更新專案文件。兩邊都要做，不能只做一邊。

---

## Gotchas

- **staleness verification 被跳過**：最常見的失誤。層級 1 每次都做，沒有例外。
- **「session 中已更新」不等於「已正確更新」**：同一 session 多次改同一檔案時，最後一次 /learn 容易假設「之前改過了」而跳過驗證。必須 **re-read 實際檔案內容** 確認，不可靠記憶。特別是 status.md 的暫時 tag（如「待 E2E 驗證」）在 E2E 通過後必須移除。
- **只更新 docs/ 忘了 memory/**：「更新文件」= docs/ + memory/ 兩邊都要。
- **MEMORY.md 寫了實質內容**：`memory/MEMORY.md` 是純索引（只放指標）。教訓寫 `lessons-*.md`。
- **lessons 重複記錄**：已有類似 lesson → 更新信心等級，不要新增重複條目。
- **decisions.md 計數沒更新**：追加新決策後，更新「共 N 筆」。
- **status.md「最近完成」粒度太細**：只記大功能，不記個別 bugfix。超 10 項移 completed-work.md。
- **跨文件引用漏更新**：一個事實出現在 3-4 份文件，改一份時 indexer 搜全部。
- **CLAUDE.md 塞了流水帳**：每個 session 都 load CLAUDE.md。已完成的項目不要留在「目前工作」，移除或指向 status.md。不放 bugfix 細節、commit hash、日期。
- **只寫入不整理**：寫新 lesson/status/decision 時，同步清理既有內容（B3 歸檔整理）。不整理 = 下次清理的成本更高。
- **memory/ 路徑混淆**：專案 memory 在 `C:/users/user/nlweb/memory/`（git 內），不是 `~/.claude/projects/.../memory/`。

---

## 兩大職責

| 職責 | 目標檔案 |
|------|---------|
| **Lessons** | `memory/lessons-*.md`（技術陷阱、踩坑記錄） |
| **Docs** | `docs/`（狀態、規格、決策、完成工作） |

---

## Part A：Lessons

### A1. 分析對話，找值得記錄的內容

- 解決了非顯而易見的 bug
- 框架/套件的陷阱或限制
- 新的 pattern 或 best practice
- 派工經驗（→ `delegation-patterns.md`）

**不記錄**：瑣碎修復、一次性問題、尚未驗證的假設。

### A2. 寫入正確的 lessons 檔案

| 問題領域 | 檔案 |
|---------|------|
| Crawler / Dashboard | `memory/lessons-crawler.md` |
| VPS / Docker / 部署 / 資安 | `memory/lessons-infra-deploy.md` |
| Auth / Login / Cookie | `memory/lessons-auth.md` |
| 其他 | `memory/lessons-general.md` |

**分拆門檻**：同一主題在 `lessons-general.md` 超過 3 條 → 獨立成 `lessons-{module}.md` + 在 `MEMORY.md` 加指標。

**memory/ 路徑**：永遠用 `C:/users/user/nlweb/memory/`（git repo 內），不是 `~/.claude/projects/.../memory/`。

### A3. 格式

```markdown
### [簡短標題]
**問題**：[遇到什麼問題]
**解決方案**：[如何解決]
**信心**：[低/中/高]
**檔案**：`[相關檔案路徑]`
**日期**：YYYY-MM-DD
```

---

## Part B：Docs

### B1. 收集 git history（看足夠廣）

```bash
git log --oneline -30
git diff --stat HEAD~20
```

### B2. 判斷受影響文件

| 修改的模組 | 可能受影響的文件 |
|-----------|---------------|
| Analytics | `docs/specs/analytics-spec.md`, `CLAUDE.md` |
| Ranking | `docs/specs/xgboost-spec.md`, `docs/specs/mmr-spec.md` |
| Auth / Login | `docs/specs/login-spec.md` |
| Crawler | `docs/specs/gcp-crawler-spec.md`, `docs/specs/crawler-dashboard-spec.md` |
| Infra / Deploy | `docs/reference/docker-deployment.md`, `CLAUDE.md` |
| 任何模組 | `docs/status.md`, `docs/archive/completed-work.md` |

一個事實可能出現在多份文件中。修改一處時用 indexer 搜尋關鍵詞，確認所有引用處。

### B3. 歸檔整理（寫入的同時整理）

寫入新內容時同步檢查：

| 檢查 | 動作 |
|------|------|
| status.md 有 `~~已完成~~` 項目 | 移到 `completed-work.md`，不留刪除線 |
| decisions.md 有 `superseded` 條目在 active 區 | 移到底部「歷史決策」區 |
| 規則出現在多份文件 | 保留一份完整版，其他改為一行指標 |
| lessons-general.md 某主題超過 3 條 | 獨立成 `lessons-{module}.md` + 更新 `MEMORY.md` |

### B4. Staleness Verification（不可跳過）

**層級 1（每次強制）**：對受影響 spec，讀取「已知限制」「待做」「未完成」段落，逐項驗證：
- 已完成 → 加刪除線 + 完成日期
- 部分完成 → 更新描述
- 仍存在 → 保留
- 描述過時 → 修正

**層級 2（本次 session 有改 code 時強制）**：對受影響 spec 全文檢查：

| 檢查項目 | 怎麼驗證 |
|---------|---------|
| 檔案路徑引用 | Glob 確認存在 |
| API 表格 | 對照 config YAML 或程式碼 |
| 程式碼範例（CSS 變數、config） | 讀實際檔案前 30 行比對 |
| 行號引用（`ranking.py:546`） | 確認不超出檔案總行數 |
| 測試狀態宣稱（"All tests passing ✅"） | 確認測試檔案存在 |
| 環境變數 / 外部服務名稱 | indexer 搜尋確認 |

例外：本次 session 只修改文件（docs/、memory/），不做層級 2。

**`/learn specs`**：對 `docs/specs/` 所有 spec 做層級 2 全文驗證（每月或大 milestone 後用）。

### B5. 更新文件（依優先順序 + 格式規則）

**1. `docs/specs/*-spec.md`**（staleness verification）
- 已完成的待做項目：`~~原文~~ → 已完成（YYYY-MM）` 格式

**2. `docs/status.md`**
- 「最近完成」只記大功能層級（Infra Migration、Login 系統、Analytics 重整），不記個別 bugfix
- 超過 5 項就移到 `completed-work.md`

**3. `docs/archive/completed-work.md`**
- Track 編號遞增（A, B, ... AG, AH）

**4. `docs/decisions.md`**
- 固定格式，每條必須有：
```markdown
### [Decision 標題]
- **Category**: [product/technical/business/process] | **Modules**: [M0-M6, Auth, etc.] | **Date**: YYYY-MM | **Status**: [active/superseded/pending]
- **Reason**: [為什麼做這個決定]
- **Tradeoff**: [取捨了什麼]
```
- 追加後更新檔案開頭的「共 N 筆」計數

**5. `CLAUDE.md`**
- **保持乾淨**：每個 session 都 load，不放歷史流水帳
- 「目前工作」只放進行中的項目，已完成的移除（指向 status.md）
- 不放個別 bugfix、commit hash、日期細節
- 模組狀態表只在模組整體狀態改變時才更新

**6. `memory/delegation-patterns.md`**

### B6. Cross-doc 一致性

| 事實 | 出現位置 |
|------|---------|
| DB 環境變數名稱 | `CLAUDE.md`, `analytics-spec.md`, `login-spec.md`, `decisions.md` |
| Production DB 位置 | `CLAUDE.md`, `analytics-spec.md`, `status.md` |
| 模組完成狀態 | `CLAUDE.md` 模組表, `status.md`, `completed-work.md` |

用 indexer 搜尋關鍵詞確認沒有殘留過時引用。

### B7. Source of Truth 順序

```
程式碼 → Spec → Docs 指南 → Systemmap → Progress
```

---

## Part C：Skill Eval（本次 session 有使用 skill 時才做）

1. 本次用了哪些 skill？
2. 該 skill 有 `eval.md` → 逐項打分（Y/N）
3. 有失敗 → 分析根因 → 一次只改一個東西 → 記到 skill 的 `changelog.md`
4. 全過 → 記到 `changelog.md`（確認之前的 mutation 有效）
5. 沒有 `eval.md` → 跳過（不強制每個 skill 都有）

**eval.md 位置**：
- commands 類 skill → `.claude/evals/`（如 `learn-eval.md`、`zoe-eval.md`）
- skills 類 skill → skill 資料夾內（如 `~/.claude/skills/newest-scan/eval.md`）
**changelog.md 位置**：同上對應目錄

---

## 完成後輸出

```
=== /learn 完成 ===

Lessons：
- [N] 個 lesson 已記錄到 memory/lessons-*.md
- delegation-patterns.md [已更新/無需更新]

Docs：
- [列出更新的檔案]

Staleness Check：
- [驗證過的 spec + 修正了幾項過時描述]
- [無法確認的項目列待確認清單]

Cross-doc：
- [修正的跨文件不一致]

Skill Eval：
- [用了哪些 skill + eval 結果]
- [mutation 記錄（如有）]

是否要 commit？(y/n)
```

若同意：
```bash
git add docs/ memory/ CLAUDE.md
git commit -m "docs: update documentation and lessons learned"
```

