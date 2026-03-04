# Orchestrator Spec — Context Management + Job Delegation

> Living document. 邊實作邊更新。
> Plan: `docs/in progress/plans/zoe.md`

**Last updated**: 2026-03-02
**Status**: Phase 1 實作中

---

## 1. 系統概述

### 目標
讓 Claude 在任何 session、任何 module 工作時，準確 recall 相關 context，並有效拆分委派工作。

### 設計原則
1. **兩層 Context 隔離** — Orchestrator 持有全局 context，Agent 只拿到精準指令 + 2-3 個檔案
2. **短命 Session** — 狀態存檔案，不存 context window
3. **Ask for Forgiveness** — 方向明確就派工 + 回報；不明確才問 CEO

---

## 2. Context 層級架構

```
CEO（人）
  │ 高層指令
  ▼
Orchestrator（Claude 主 session 或 skill）
  │ 讀取：
  │   ├── MEMORY.md (技術 context + delegation patterns)
  │   ├── CONTEXT.md (當前工作)
  │   ├── Notion 決策日誌 (商業 context)
  │   └── active-tasks.json (任務狀態)
  │
  │ 輸出：精準 prompt（只含必要 context）
  ▼
Coding Agent（Agent tool, worktree 隔離）
  │ 只看到：
  │   ├── 指定的 2-3 個檔案
  │   ├── 具體修改指令
  │   └── 驗證方式
  ▼
結果 → 更新 active-tasks.json → 通知 CEO
```

---

## 3. 持久儲存

### 3-1. Delegation Patterns（MEMORY.md 內）

**位置**: `~/.claude/projects/C--users-user-nlweb/memory/MEMORY.md`
**Section**: `## Delegation Patterns`

內容：
- Module → Required Context mapping（什麼 task 要給 agent 什麼檔案）
- Prompt Structure Patterns（什麼類型的 task 用什麼 prompt 結構最有效）
- 學習迴圈：成功的 delegation 自動寫回

**狀態**: ✅ 已建立（MEMORY.md 索引 + `memory/delegation-patterns.md`）

### 3-2. Notion 決策日誌 Database

**Schema**:

| 欄位 | 類型 | 說明 | 必填 |
|------|------|------|------|
| Decision | Title | 決策標題 | Y |
| Date | Date | 決策日期 | Y |
| Category | Select | `architecture` / `business` / `product` / `operations` | Y |
| Affected Modules | Multi-select | `M0-Indexing` / `M1-Input` / `M2-Retrieval` / `M3-Ranking` / `M4-Reasoning` / `M5-Output` / `M6-Infrastructure` / `crawler` / `infra` / `workflow` | N |
| Reason | Rich Text | 為什麼做這個決定 | Y |
| Tradeoff | Rich Text | 放棄了什麼替代方案 | N |
| Status | Select | `active` / `superseded` / `pending` | Y |
| Context | Rich Text | 商業背景、客戶反饋等 | N |

**位置**: Notion workspace（獨立 DB，不在現有頁面下）
**Database URL**: `https://www.notion.so/447d8a05a8fb4b56888ee63d4bbfa770`
**Data Source ID**: `0a99f1b4-5970-4dd3-a464-1d3149d72aab`

**狀態**: ✅ 已建立（2026-03-02）

### 3-3. active-tasks.json

**位置**: `.claude/swarm/active-tasks.json`
**用途**: 追蹤 delegate 出去的 agent 任務狀態

```json
{
  "tasks": [
    {
      "id": "string — kebab-case task identifier",
      "description": "string — 一句話描述",
      "branch": "string — git branch name",
      "status": "pending | running | done | failed",
      "agent_model": "haiku | sonnet | opus",
      "files_scope": ["string — 檔案路徑"],
      "prompt_summary": "string — 給 agent 的精準指令",
      "pr_number": "number | null",
      "ci_status": "passed | failed | pending | null",
      "created_at": "ISO 8601",
      "updated_at": "ISO 8601",
      "retry_count": "number",
      "max_retry": 3,
      "decision_ref": "string | null — notion page id"
    }
  ],
  "last_check": "ISO 8601"
}
```

**狀態**: 🔲 Phase 3 建立

---

## 4. Skills

### 4-1. `/decide` — 記錄決策

**觸發**: CEO 說「記一下」「決定記錄」或 session 有重要決策
**檔案**: `.claude/skills/decide.md`

**行為**:
1. 整理本次 session 的決策
2. 用 Notion MCP `notion-create-pages` 寫入決策日誌 DB
3. 若產生新 delegation pattern → 更新 MEMORY.md

**狀態**: 🔲 待建立

### 4-2. `/delegate` — 中階主管模式

**觸發**: CEO 給高層指令
**檔案**: `.claude/skills/delegate.md`

**行為**:
1. 讀 MEMORY.md delegation patterns → 找 match
2. 讀 CONTEXT.md → 目前狀態
3. 查 Notion 決策日誌 → 商業 context（orchestrator 層用，不傳給 agent）
4. 判斷方向是否明確：
   - **明確** → 拆 tasks → Agent tool (worktree) spawn → 回報 CEO
   - **不明確** → 問 CEO
5. 成功後 → 寫回 delegation pattern

**Context 路由規則**:
- Agent prompt 只包含：檔案路徑 + 具體指令 + 驗證方式
- 不包含：商業原因、其他 module 資訊、歷史討論

**狀態**: 🔲 待建立

### 4-3. `/briefing` — Session 同步

**觸發**: 新 session、CEO 說 `/briefing`
**檔案**: `.claude/skills/briefing.md`

**行為**:
1. 讀 CONTEXT.md + MEMORY.md
2. 查 Notion 最近 5-10 筆 active 決策
3. 讀 active-tasks.json
4. 輸出精簡摘要（3 段：技術狀態、商業 context、進行中任務）

**狀態**: 🔲 待建立

### 4-4. `/monitor` — Agent 狀態檢查

**觸發**: CEO 說 `/monitor`、或自動化排程
**檔案**: `.claude/skills/monitor.md`

**行為**:
1. 讀 active-tasks.json
2. `gh pr list` + `gh pr checks` per branch
3. 彙總報告
4. 異常 → LINE 通知

**狀態**: 🔲 Phase 3 建立

---

## 5. 外部整合

### 5-1. LINE MCP Server

**用途**: 任務完成/失敗通知
**套件**: `@line/line-bot-mcp-server`
**免費額度**: 200 則/月

**設定位置**: Claude Code settings
```json
{
  "mcpServers": {
    "line-bot": {
      "command": "npx",
      "args": ["@line/line-bot-mcp-server"],
      "env": {
        "CHANNEL_ACCESS_TOKEN": "<TBD>",
        "DESTINATION_USER_ID": "<TBD>"
      }
    }
  }
}
```

**前置**: CEO 需在 LINE Developer Console 建立 Messaging API Channel

**狀態**: 🔲 Phase 3 設定

### 5-2. Notion MCP（已有）

**用途**: 讀寫決策日誌
**已有 Tools**: `notion-search`, `notion-fetch`, `notion-create-pages`, `notion-update-page`

**狀態**: ✅ 已連接

---

## 6. 實作進度

| Phase | Item | Status | Notes |
|-------|------|--------|-------|
| **1** | MEMORY.md delegation patterns | ✅ | MEMORY.md 索引 + `memory/delegation-patterns.md` 詳細內容 |
| **1** | Notion 決策日誌 DB | ✅ | DB ID: `0a99f1b4-5970-4dd3-a464-1d3149d72aab` |
| **1** | Notion 決策日誌回填 | ✅ | 36 筆（產品4+M0~M6全模組），2026-03-03 完成 |
| **2** | `/decide` skill | 🔲 | |
| **2** | `/delegate` skill | 🔲 | |
| **2** | `/briefing` skill | 🔲 | |
| **3** | active-tasks.json | 🔲 | |
| **3** | `/monitor` skill | 🔲 | |
| **3** | LINE MCP 設定 | 🔲 | |
| **4** | Windows Task Scheduler | 🔲 | |

---

## 7. 決策記錄

| 日期 | 決策 | 原因 |
|------|------|------|
| 2026-03-02 | Delegation patterns 存 MEMORY.md | 跟現有 memory 系統一致，不另開檔案 |
| 2026-03-02 | Notion 混合策略（結構化 DB + 自由筆記）| 重要決策結構化可查詢，其他不增加記錄負擔 |
| 2026-03-02 | 用 Skills 實作（非 bash script）| 原生整合、on-demand 載入不佔 context、可迭代 |
| 2026-03-02 | Ask for forgiveness 行為模式 | CEO 偏好：有 pattern 就直接派，事後報告 |
| 2026-03-02 | LINE 取代 Telegram | 台灣使用者習慣 |
