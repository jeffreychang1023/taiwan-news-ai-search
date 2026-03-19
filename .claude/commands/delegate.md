---
name: delegate
description: |
  Zoe 的核心派工能力。分析 CEO 指令，收集必要上下文，選擇正確的 skill 或 agent 執行任務。
  觸發時機：CEO 下達需要派工的指令（功能開發、bug 修復、重構、文件更新等）。
  不觸發：在 /zoe session 中時，Zoe 直接用 Agent tool 派工，不需要另調 /delegate。
  用法：/delegate <CEO 指令>
---

# Delegate

CEO 指令的智慧派工。收集上下文 → 判斷方向 → 選擇 skill → 派工 → 回報。

## Gotchas

- **delegate vs zoe**：/zoe session 中 Zoe 直接用 Agent tool 派工（不調用 Skill tool，否則覆蓋人格）。/delegate 是在非 Zoe session 中使用的獨立指令。
- **不寫 prompt template** — 選正確的 skill，讓 skill 本身引導流程。直接寫 prompt 繞過 skill 等於重複造輪子。
- **spec 不憑記憶列** — 每次 `ls docs/specs/` 動態發現，不要照抄你記得的 spec 路徑。
- **CLAUDE.md 覆蓋的規則不重複寫進 agent prompt** — smoke test、indexer 搜尋、不可 silent fail，subagent 會讀到。prompt 要補的是模組特定陷阱和架構決策背景。
- **方向不明確時先問** — 不要猜測後派工，猜錯比多問一句代價高。

## Step 1: 收集上下文（全部平行讀取）

```
同時讀取：
1. docs/status.md              — 目前狀態，避免衝突
2. docs/decisions.md           — 避免走回頭路
3. memory/delegation-patterns.md — 模組 → agent 需要什麼
4. memory/lessons-general.md   — 技術陷阱
```

## Step 2: 發現相關 Spec

```bash
ls docs/specs/
```

從列表中判斷哪些 spec 與任務相關，不憑記憶列舉。

## Step 3: 選擇執行方式

| 任務性質 | 選擇 |
|----------|------|
| Bug 修復 | `systematic-debugging` skill |
| 新功能（需設計） | `brainstorming` skill → 再派工 |
| 多步驟實作計畫 | `writing-plans` skill |
| 多個獨立子任務 | `dispatching-parallel-agents` skill |
| 單一明確修改 | 直接用 Agent tool 派工 |
| 文件更新 | `update-docs` skill |
| 程式碼品質 | `simplify` 或 `requesting-code-review` skill |

## Step 4: 組裝 Agent Prompt

從 delegation-patterns.md 取得對應模組指引，包含：
1. 優先閱讀的程式碼
2. 相關 spec 路徑（從 Step 2）
3. 模組特定陷阱（CLAUDE.md 沒有的部分）
4. CEO 原始指令

**model 選擇**：Haiku（單檔案小修改）/ Sonnet（跨 2-5 檔案）/ Opus（架構決策、困難 debug）

## Step 5: 派工並回報

```
## 派工回報
**任務**：[一句話描述]
**執行方式**：[skill 或 Agent tool]
**涉及模組**：[模組名稱]
**相關 Spec**：[spec 檔案]
**已知風險**：[從 lessons 找到的陷阱，若無省略]
**預期結果**：[完成後應該看到什麼]
```

任務完成後提醒 CEO 是否需要 `/learn` 更新文件。
