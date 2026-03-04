# Zoe Plan — Context Management + Job Delegation

> Agent Swarm 架構計畫：用 Claude Code 原生能力實現跨 session context 管理與任務委派

**狀態**：Phase 2 進行中
**日期**：2026-03-02（原案）→ 2026-03-04（更新）

---

## 目標

讓 Claude 在任何 session、任何 module 工作時，都能準確 recall 相關 context，並且能有效地把工作拆分委派。Agent swarm 是手段，不是目的。

## 核心痛點

1. 跨 module 工作時 Claude 無法 recall 商業決策和過往討論
2. 每次新 session 要重新給 context
3. Context rot 導致長對話後期品質下降

---

## 設計原則

### 兩層 Context 隔離

```
┌─────────────────────────────────────┐
│  Orchestrator（Claude 主 session）    │
│  ├── 商業 context（docs/decisions.md）│
│  ├── 技術 context（MEMORY.md）       │
│  ├── Delegation patterns             │
│  ├── Lessons learned（技術陷阱）      │
│  └── 決定：派誰、給什麼 prompt        │
└──────────┬──────────┬───────────────┘
           │          │
    ┌──────▼──┐  ┌────▼────┐
    │ Agent A  │  │ Agent B  │
    │ 只看到：  │  │ 只看到：  │
    │ 2-3 檔案 │  │ 2-3 檔案 │
    │ + 精準   │  │ + 精準   │
    │   指令   │  │   指令   │
    └─────────┘  └─────────┘
```

### Orchestrator 是短命 session

- 每次被喚起 → 讀檔 → 判斷 → 寫檔 → 結束
- 狀態存在檔案裡，不在 context 裡
- Context window 是 RAM，檔案是硬碟 — 只讀需要的部分

### Delegation 行為模式：Ask for Forgiveness, Not Permission

- 有 pattern match + 方向明確 → **直接派工 + 回報**（已派什麼、預期結果、fallback）
- 方向不明確 → **問 CEO**

---

## 決定事項

| 項目 | 原案（03-02） | Pivot 後（03-03~04） |
|------|--------------|---------------------|
| 決策日誌位置 | Notion 結構化 DB | `docs/decisions.md`（本地 markdown，35+ 筆） |
| Delegation patterns | MEMORY.md 內嵌 section | 獨立 `memory/delegation-patterns.md` |
| 實作手段 | Claude Code Skills | ✅ 不變 |
| Context 來源 | `.claude/CONTEXT.md` + Notion API | `docs/status.md` + `docs/decisions.md`（本地檔案） |
| 通知管道 | LINE MCP Server | 延後至 Phase 3 |
| 學習迴圈 | 成功的 delegation 自動寫回 patterns | ✅ 不變，透過 `/update-docs patterns` 觸發 |

**Pivot 原因**：
1. Notion API 是額外依賴且延遲高，本地 markdown 更簡單且 Claude Code 原生支援
2. 大搬遷（`.claude/*.md` → `docs/`）後檔案路徑全面改變
3. `/update-docs` 已有成熟的文件同步機制，decisions/patterns 整合進去更自然

---

## Phase 1：Foundation — ✅ 完成（2026-03-03）

### 1-1. Delegation Patterns — 獨立檔案

**檔案**：`memory/delegation-patterns.md`

內容：
- 通用原則（Spec 發現、Skill 調用、Docs 一致性）
- 模組特定指引（Ranking / Crawler Parser / Crawler Engine / Reasoning / Frontend / Indexing / Dashboard / Config / 文件更新）
- 每個模組有：優先閱讀的程式碼 + 考量重點

### 1-2. 決策日誌 — 本地 Markdown

**檔案**：`docs/decisions.md`

- 從 Notion 導出 35 筆決策（全模組 M0-M6 + 產品基礎）
- 格式：Decision / Category / Modules / Date / Status / Reason / Tradeoff
- 持續更新（透過 `/update-docs decisions`）

### 1-3. 檔案系統整合

- `.claude/` 下的文件搬遷至 `docs/` 體系
- MEMORY.md 更新 File Index 指向新路徑
- CLAUDE.md 文件查詢指令表更新

---

## Phase 2：Core Skills — 🔄 進行中

### 2-1. `/delegate` Skill — ✅ 完成（2026-03-04）

**檔案**：`.claude/commands/delegate.md`

觸發：CEO 給高層指令（「author weight 調高」「加一個 XX 功能」）

行為：
```
1. 讀 docs/status.md（目前狀態）
2. 讀 docs/decisions.md（為什麼這樣設計）
3. 讀 memory/delegation-patterns.md（模組經驗）
4. 讀 memory/lessons-learned.md（技術陷阱）
5. ls docs/specs/（動態發現相關 spec）
   ↓
6. 判斷方向是否明確
   ├── 明確 → 選對應 skill + 用 Agent tool 派工
   │         回報 CEO：派了什麼、預期結果
   └── 不明確 → 問 CEO 釐清
```

**與原案差異**：
- 不查 Notion（改讀本地 `docs/decisions.md`）
- 新增 `memory/lessons-learned.md` 讀取（避免已知陷阱）
- 新增 `ls docs/specs/` 動態發現（不硬編碼 spec 列表）
- 選擇 skill 執行（systematic-debugging / brainstorming / writing-plans 等），不自寫 prompt template

### 2-2. `/update-docs` 擴充 — ✅ 完成（2026-03-04）

**檔案**：`.claude/commands/update-docs/SKILL.md`

**原案沒有此項**。Pivot 後決定把 decisions + patterns 更新整合至已有的 `/update-docs` skill。

新增：
- `decisions` 參數 — 追加新決策至 `docs/decisions.md`
- `patterns` 參數 — 從 delegation 結果更新 `memory/delegation-patterns.md`
- `all` 參數執行順序：specs → docs → architecture → progress → decisions → patterns
- 所有路徑修正至搬遷後位置

### 2-3. `/decide` 和 `/briefing` — 不做

原案 Phase 2 包含 `/decide` + `/briefing`，但：
- `/decide` 功能已被 `/update-docs decisions` 覆蓋
- `/briefing` 功能已被 `/status` skill 覆蓋
- 獨立 skill 價值不足，不新增

### 2-4. `/zoe` Skill — Zoe 模式啟動 — ✅ 完成（2026-03-04）

**檔案**：`.claude/commands/zoe.md`

觸發：CEO 輸入 `/zoe`

行為：
1. 平行讀取 status + decisions + patterns + lessons + spec 列表
2. 輸出簡短 briefing（目前狀態、進行中、待處理）
3. 進入 CTO 人格模式，後續對話以 Zoe 身份回應
4. CEO 指令自動路由至對應工具（delegate / update-docs / plan-discuss 等）
5. Session 結束前提醒更新文件和記錄決策

---

## Phase 3：LINE 通知 + Session 追蹤 — ✅ 完成（2026-03-05）

> Phase 2 驗證後簡化：不需要獨立 `/monitor` skill 和 `active-tasks.json`

### 設計 Pivot

原案設計了獨立的 `/monitor` skill + `active-tasks.json` 追蹤檔。但 Phase 2 驗證後發現：
- Zoe 在 session 中已經是 monitor — 她派工、等結果、review、再派工
- Claude Code 內建 Task 工具（TaskCreate/TaskList/TaskUpdate）已覆蓋 session 內追蹤
- 不需要額外的 JSON 追蹤檔

### 3-1. LINE MCP 整合 — ✅ 完成

**設定**：`claude mcp add line-bot` — LINE Messaging API，推播至 CEO 的 LINE

**觸發時機**：
- subagent 完成重要工作，需要 CEO review
- 遇到需要 CEO 決策的問題
- CEO 說「做完叫我」「通知我」

**訊息格式**：`[Zoe] {一句話摘要} — 詳情回 Claude Code 看。`

### 3-2. Session 內追蹤 — 用 Task 工具

- `TaskCreate`：派工時建立任務
- `TaskUpdate`：subagent 回來後標完成
- `TaskList`：CEO 問進度時列出

不需要 `active-tasks.json`，Task 工具就是 session 內的追蹤系統。

---

### Phase 4：自動化排程（未來）

- Windows Task Scheduler 定時呼叫 `/monitor`
- 主動掃描：Sentry errors、git log 變更
- 自動化 PR review + merge

---

## 風險評估

| 風險 | 影響 | 緩解 |
|------|------|------|
| `claude -p` Windows 行為不一致 | 高 | 先手動測試單個 agent 再自動化 |
| Delegation pattern 不夠 → agent 做錯 | 中 | 學習迴圈持續累積 pattern；初期 CEO review |
| LINE 免費額度 200 則/月 | 低 | 彙總通知，非逐 task |
| Worktree 檔案衝突 | 中 | Task 設計時確保 files_scope 不重疊 |

## 里程碑

| Phase | 交付物 | 狀態 |
|-------|--------|------|
| **1** | Delegation patterns + 決策日誌（本地 markdown） | ✅ 完成 |
| **2** | `/delegate` + `/update-docs` 擴充 + `/zoe` 模式啟動 | ✅ 完成 |
| **3** | LINE 通知 + Task 工具追蹤（簡化版） | ✅ 完成 |
| **4** | 自動化排程 | 待實作 |

**建議**：Phase 2 完成後用 1-2 週驗證體驗，再決定 Phase 3-4。

---

*Based on: Elvis @elvissun "OpenClaw + Codex/Claude Code Agent Swarm" article analysis*
*Adapted for: Claude Code native capabilities (Skills + Agent tool)*
*Pivoted: Notion DB → local markdown, `.claude/` → `docs/` 體系*
