# Claude Code 配置升級實作計劃

> 基於 [everything-claude-code](https://github.com/affaan-m/everything-claude-code) 的最佳實踐，針對 NLWeb 專案客製化

---

## 現況分析

### 已有配置（不重複）

| 項目 | 位置 | 功能 |
|------|------|------|
| `CONTEXT.md` | `.claude/` | 專案狀態、目前重點、下一步 |
| `PROGRESS.md` | `.claude/` | 里程碑、已完成功能、Bug 修復 |
| `NEXT_STEPS.md` | `.claude/` | 短中長期計劃 |
| `systemmap.md` | `.claude/` | M0-M6 模組總覽、Data Flow、API |
| `codingrules.md` | `.claude/` | 命名規範、錯誤處理、安全規範 |
| `tools/indexer.py` | 專案根目錄 | SQLite FTS5 程式碼索引（優於 Grep） |
| `systematic-debugging` | `~/.claude/skills/` | 4 階段除錯流程 |
| `code-reviewer` | `~/.claude/skills/` | 程式碼審查清單 |

### 缺失配置（需新增）

| 項目 | 價值 | 優先順序 |
|------|------|----------|
| **hooks.json** | 自動載入 context、強制用索引 | P0 |
| **planner agent** | 複雜任務拆解、防止迷路 | P1 |
| **token-optimization rules** | 節省 AI context window | P1 |
| **commands** | 快捷指令 | P2 |
| **performance rules** | 模型選擇指南 | P2 |

---

## 實作項目

### Phase 1：Hooks 系統（P0 - 立即節省 Token）

#### 1.1 建立 `NLWeb\.claude\hooks.json`

```json
{
  "hooks": [
    {
      "matcher": {
        "type": "event",
        "event": "session_start"
      },
      "hooks": [
        {
          "type": "command",
          "command": "echo '=== NLWeb Context Loaded ===' && cat .claude/CONTEXT.md | head -50"
        }
      ]
    },
    {
      "matcher": {
        "type": "tool",
        "tool": "Grep"
      },
      "hooks": [
        {
          "type": "prompt",
          "message": "STOP: 使用 `python tools/indexer.py --search \"關鍵字\"` 而非 Grep，以節省 Token 並獲得更精準結果。"
        }
      ]
    },
    {
      "matcher": {
        "type": "tool",
        "tool": "Edit",
        "path": "**/*.py"
      },
      "hooks": [
        {
          "type": "command",
          "command": "python -m py_compile $CLAUDE_FILE_PATH 2>&1 || echo 'Python 語法錯誤，請修正'"
        }
      ]
    }
  ]
}
```

**效果**：
- Session 開始自動顯示 CONTEXT.md（前 50 行）
- 嘗試 Grep 時提醒用索引系統
- Python 檔案編輯後自動語法檢查

---

### Phase 2：Planner Agent（P1 - 複雜任務必備）

#### 2.1 建立 `NLWeb\.claude\agents\planner.md`

```markdown
# NLWeb Planner Agent

## 角色
你是 NLWeb 專案的架構規劃師。在開始任何複雜任務前，你必須：
1. 分析需求
2. 查閱相關模組狀態
3. 輸出結構化計劃

## 必讀資源
開始規劃前，必須閱讀：
- `.claude/systemmap.md` - 了解模組 M0-M6 的狀態與依賴
- `.claude/CONTEXT.md` - 目前工作重點
- `.claude/PROGRESS.md` - 避免重複已完成工作

## 輸出格式

### 需求摘要
[用一句話描述目標]

### 影響模組
| 模組 | 狀態 | 需要修改的檔案 |
|------|------|----------------|
| M3: Ranking | 🟢 完成 | `core/ranking.py` |

### 實作步驟
1. **[步驟名稱]**
   - 檔案：`具體檔案路徑`
   - 修改：具體要做什麼
   - 驗證：如何確認完成

### 風險與依賴
- [列出潛在風險]
- [列出需要先完成的前置工作]

### 預估複雜度
- [ ] 簡單（單檔案修改）
- [ ] 中等（2-5 個檔案）
- [ ] 複雜（跨模組修改）

## 規則
- 不寫程式碼，只輸出計劃
- 必須引用具體檔案路徑（不可模糊）
- 必須標註影響的模組
- 等待使用者確認後才開始實作
```

---

### Phase 3：Token 優化規則（P1 - 核心節省策略）

#### 3.1 建立 `NLWeb\.claude\rules\token-optimization.md`

```markdown
# Token 優化規則（NLWeb 專用）

## 強制規則

### 1. 程式碼搜尋
❌ 禁止：直接使用 Grep 搜尋程式碼
✅ 必須：使用 `python tools/indexer.py --search "關鍵字"`

原因：索引系統使用 SQLite FTS5，回傳精準結果，避免大量無關檔案填充 context

### 2. 了解系統架構
❌ 禁止：遍歷目錄結構來了解專案
✅ 必須：先讀 `.claude/systemmap.md`

### 3. 了解目前狀態
❌ 禁止：問使用者「目前在做什麼」
✅ 必須：先讀 `.claude/CONTEXT.md` 和 `.claude/PROGRESS.md`

### 4. 修改 Reasoning 相關程式碼前
❌ 禁止：直接讀取所有 agent 檔案
✅ 必須：先讀 `docs/algo/reasoning_system.md` 了解架構

### 5. 修改 Ranking 相關程式碼前
❌ 禁止：直接讀取 ranking.py
✅ 必須：先讀 `docs/algo/ranking_pipeline.md` 了解流程

## 漸進式讀取策略

當需要了解某功能時：
1. 先讀對應的 `docs/algo/*.md` 文件
2. 再讀 `.claude/systemmap.md` 對應模組
3. 最後才讀具體程式碼（且只讀必要部分）

## 模組快速參考

| 要修改的功能 | 先讀這個文件 |
|--------------|--------------|
| Reasoning | `docs/algo/reasoning_system.md` |
| Ranking | `docs/algo/ranking_pipeline.md` |
| 查詢分析 | `docs/algo/query_analysis.md` |
| API | `.claude/API_ENDPOINTS.md` |
| 資料流 | `.claude/systemmap.md` 的 Data Flow 章節 |
```

---

### Phase 4：Commands 快捷指令（P2）

#### 4.1 建立 `NLWeb\.claude\commands\plan.md`

```markdown
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
5. 等待使用者確認後才開始實作

## 使用時機
- 新功能開發
- 重大架構變更
- 跨模組修改
- 不確定從何開始時
```

#### 4.2 建立 `NLWeb\.claude\commands\index.md`

```markdown
---
description: 更新程式碼索引
---

# /index

重建 NLWeb 程式碼索引。

## 執行
```bash
cd C:\users\user\NLWeb && python tools/indexer.py --index
```

## 使用時機
- 大量檔案修改後
- 新增模組後
- 搜尋結果不準確時
```

#### 4.3 建立 `NLWeb\.claude\commands\search.md`

```markdown
---
description: 搜尋程式碼
---

# /search <關鍵字>

使用索引系統搜尋程式碼。

## 執行
```bash
cd C:\users\user\NLWeb && python tools/indexer.py --search "<關鍵字>"
```

## 優於 Grep 的原因
- 使用 SQLite FTS5 全文搜尋
- 結果精準且排序
- 不會將大量無關內容填入 context
```

#### 4.4 建立 `NLWeb\.claude\commands\status.md`

```markdown
---
description: 顯示專案狀態
---

# /status

顯示 NLWeb 專案目前狀態。

## 執行
讀取並摘要顯示：
1. `.claude/CONTEXT.md` - 目前重點
2. `.claude/NEXT_STEPS.md` - 下一步計劃
3. `.claude/systemmap.md` 的模組狀態表

## 輸出格式
```
=== NLWeb 狀態 ===

目前重點：[從 CONTEXT.md 提取]

模組狀態：
- M0 Indexing: 🔴 規劃中
- M1 Input: 🟡 部分完成
- M2 Retrieval: 🟡 部分完成
- M3 Ranking: 🟢 完成
- M4 Reasoning: 🟢 完成
- M5 Output: 🟡 部分完成
- M6 Infrastructure: 🟢 完成

下一步：[從 NEXT_STEPS.md 提取前 3 項]
```
```

---

### Phase 5：通用效能規則（P2）

#### 5.1 建立 `~\.claude\rules\performance.md`

```markdown
# 模型選擇與效能指南

## 模型選擇框架

| 模型 | 適用場景 | 成本 |
|------|----------|------|
| **Haiku** | 簡單修改、單檔案編輯、格式化 | $ |
| **Sonnet** | 日常開發、中等複雜度任務 | $$ |
| **Opus** | 架構決策、複雜推論、研究 | $$$ |

## Context Window 管理

### 警戒線
- 當 context 使用超過 80%，考慮：
  - 總結目前進度
  - 清理不需要的檔案內容
  - 開新對話繼續

### 避免填充 Context 的行為
- 不要一次讀取多個大檔案
- 不要列出完整目錄樹
- 不要重複貼上相同內容
- 使用索引系統而非全文搜尋

## 效率最佳化

1. **先理解再行動**：讀文件 → 讀程式碼 → 修改
2. **最小修改原則**：只改必要的部分
3. **增量驗證**：每個步驟都驗證
```

---

## 目錄結構（完成後）

```
NLWeb\.claude\
├── CONTEXT.md              # 已有
├── PROGRESS.md             # 已有
├── NEXT_STEPS.md           # 已有
├── systemmap.md            # 已有
├── codingrules.md          # 已有
├── hooks.json              # 🆕 新增
├── agents\
│   └── planner.md          # 🆕 新增
├── rules\
│   └── token-optimization.md  # 🆕 新增
└── commands\
    ├── plan.md             # 🆕 新增
    ├── index.md            # 🆕 新增
    ├── search.md           # 🆕 新增
    └── status.md           # 🆕 新增

~\.claude\
└── rules\
    └── performance.md      # 🆕 新增（通用）
```

---

## 你需要做的事

### 一次性設定

| 任務 | 說明 | 預估時間 |
|------|------|----------|
| ✅ 確認計劃 | 審閱此文件，確認需要的項目 | 5 分鐘 |
| ⬜ 讓 Claude 建立檔案 | 確認後，Claude 會自動建立所有檔案 | 2 分鐘 |
| ⬜ 測試 hooks | 開新 Claude Code session，確認 CONTEXT.md 自動載入 | 2 分鐘 |
| ⬜ 測試 `/plan` | 輸入 `/plan 新增 XXX 功能`，確認輸出格式正確 | 2 分鐘 |

### 持續維護

| 任務 | 頻率 | 說明 |
|------|------|------|
| 更新 `CONTEXT.md` | 每週或每個 Sprint | 更新「目前重點」和「最近完成」 |
| 更新 `PROGRESS.md` | 完成里程碑時 | 記錄已完成的功能和 Bug 修復 |
| 更新 `systemmap.md` | 新增模組時 | 更新模組狀態表和 Data Flow |
| 執行 `/index` | 大量修改後 | 重建程式碼索引 |
| 檢查 `docs/algo/` | 修改核心演算法後 | 確保文件與程式碼同步 |

### 定期檢查清單

每月檢查一次：

- [ ] `systemmap.md` 的模組狀態是否正確？
- [ ] `CONTEXT.md` 的「目前重點」是否過時？
- [ ] `codingrules.md` 是否需要新增規則？
- [ ] `docs/algo/` 的文件是否與程式碼一致？
- [ ] 索引是否包含所有新增的檔案？

---

## 預期效益

| 效益 | 說明 |
|------|------|
| **Token 節省 30-50%** | 透過索引系統和漸進式讀取 |
| **減少迷路** | Planner 確保複雜任務有明確步驟 |
| **自動化 Context 載入** | Hooks 自動顯示專案狀態 |
| **快速導航** | Commands 提供常用操作捷徑 |
| **一致性** | Rules 確保 AI 遵循專案規範 |

---

*建立日期：2026-01-27*
