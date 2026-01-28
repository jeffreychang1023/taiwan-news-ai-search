# Claude Code 配置使用手冊

> 基於 [everything-claude-code](https://github.com/affaan-m/everything-claude-code) 最佳實踐，針對 NLWeb 專案客製化的配置系統

---

## 目錄

1. [概述](#概述)
2. [檔案結構](#檔案結構)
3. [Hooks 自動化](#hooks-自動化)
4. [Memory System](#memory-system)
5. [Planner Agent](#planner-agent)
6. [Commands 快捷指令](#commands-快捷指令)
7. [Rules 規則系統](#rules-規則系統)
8. [維護指南](#維護指南)
9. [常見問題](#常見問題)

---

## 概述

### 設計目標

1. **節省 Token**：只在需要時載入 context，避免浪費
2. **防止迷路**：複雜任務有結構化規劃流程
3. **自動化**：減少重複操作，自動載入專案狀態
4. **一致性**：確保 AI 遵循專案規範

### 核心理念

```
先讀文件 → 再讀程式碼 → 最後修改
     ↓
   索引優先於全文搜尋
     ↓
   漸進式精煉，非一次載入全部
```

---

## 檔案結構

### NLWeb 專案級配置

```
NLWeb\.claude\
├── CONTEXT.md              # 目前工作狀態（手動維護）
├── PROGRESS.md             # 里程碑記錄（手動維護）
├── NEXT_STEPS.md           # 計劃清單（手動維護）
├── systemmap.md            # M0-M6 模組總覽（手動維護）
├── codingrules.md          # 編碼規範（手動維護）
├── hooks.json              # 🆕 自動化觸發器
├── agents\
│   └── planner.md          # 🆕 任務規劃代理
├── memory\
│   └── lessons-learned.md  # 🆕 累積的專案知識
├── rules\
│   └── token-optimization.md  # 🆕 Token 節省規則
└── commands\
    ├── plan.md             # 🆕 /plan 指令
    ├── index.md            # 🆕 /index 指令
    ├── search.md           # 🆕 /search 指令
    ├── status.md           # 🆕 /status 指令
    └── learn.md            # 🆕 /learn 指令
```

### 全域配置

```
~\.claude\
├── rules\
│   └── performance.md      # 🆕 模型選擇與效能指南
└── skills\
    ├── systematic-debugging\   # 除錯技能（已有）
    └── code-reviewer\          # 審查技能（已有）
```

---

## Hooks 自動化

### 位置
`NLWeb\.claude\hooks.json`

### 功能說明

| Hook | 觸發時機 | 功能 |
|------|----------|------|
| Session Start | 開啟新 session | 自動顯示 CONTEXT.md 前 50 行 |
| Session End | 結束 session | 提醒執行 /learn 記錄 lesson |
| Grep 攔截 | 嘗試使用 Grep | 提醒使用索引系統 |
| Python 檢查 | 編輯 .py 檔案後 | 自動執行語法檢查 |

### 實際效果

**Session 開始時**：
```
=== NLWeb Context Loaded ===
[CONTEXT.md 內容自動顯示]
```

**嘗試 Grep 時**：
```
STOP: 使用 `python tools/indexer.py --search "關鍵字"`
而非 Grep，以節省 Token 並獲得更精準結果。
```

**編輯 Python 後**：
```
# 如果有語法錯誤會顯示：
Python 語法錯誤，請修正
```

**Session 結束時**：
```
Session 即將結束。如果這次對話有解決非平凡的問題，
請執行 /learn 記錄到 lessons-learned.md。
```

### 自訂 Hooks

如需新增 hook，編輯 `hooks.json`：

```json
{
  "hooks": [
    {
      "matcher": {
        "type": "tool",
        "tool": "工具名稱"
      },
      "hooks": [
        {
          "type": "prompt",
          "message": "提示訊息"
        }
      ]
    }
  ]
}
```

---

## Memory System

### 概述

Memory System 讓 Claude 能跨 session 累積專案知識。當解決非平凡問題時，自動或手動記錄到 `lessons-learned.md`，供未來參考。

```
┌─────────────────────────────────────────┐
│  Session 結束                           │
│  Hook 提醒："有 lesson 要記錄嗎？"        │
└─────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────┐
│  /learn 指令                            │
│  分析對話 → 分類 → 評估信心 → 寫入       │
└─────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────┐
│  lessons-learned.md                     │
│  累積的專案知識，依領域分類              │
└─────────────────────────────────────────┘
```

### 檔案位置

| 檔案 | 說明 |
|------|------|
| `.claude/memory/lessons-learned.md` | 儲存累積的 lessons |
| `.claude/commands/learn.md` | /learn 指令定義 |

### Lesson 格式

每個 lesson 包含：

```markdown
### [簡短標題]
**問題**：遇到什麼問題
**解決方案**：如何解決
**信心**：低/中/高
**檔案**：`相關檔案路徑`
**日期**：YYYY-MM
```

### 領域分類

| 領域 | 涵蓋內容 |
|------|----------|
| **Reasoning** | orchestrator、agents |
| **Ranking** | ranking、xgboost、mmr |
| **Retrieval** | retriever、bm25、qdrant |
| **API / Frontend** | webserver、static、SSE |
| **Infrastructure** | DB、cache、config |
| **開發環境 / 工具** | Python、套件、開發流程 |

### 信心等級

| 等級 | 條件 |
|------|------|
| **低** | 第一次遇到，解法可能不完整 |
| **中** | 解決過 2-3 次，或有文件佐證 |
| **高** | 多次驗證，確定有效 |

### 使用方式

**自動**：Session 結束時，hook 會提醒執行 `/learn`

**手動**：隨時執行 `/learn` 記錄當前對話的 lesson

### 記錄條件

**值得記錄**：
- 解決了非顯而易見的 bug
- 發現了框架/套件的陷阱
- 找到了效能優化方法
- 踩過的坑（避免下次再犯）

**不記錄**：
- 瑣碎修復（typo、格式）
- 一次性問題
- 尚未驗證的假設

---

## Planner Agent

### 位置
`NLWeb\.claude\agents\planner.md`

### 使用時機

- 新功能開發（跨多個檔案）
- 重大架構變更
- 複雜重構
- 不確定從何開始時

### 觸發方式

```
/plan 實作 XXX 功能
```

或直接描述需求，Claude 會自動判斷是否需要規劃。

### 輸出格式

Planner 會輸出：

```markdown
### 需求摘要
[一句話描述]

### 影響模組
| 模組 | 狀態 | 需要修改的檔案 |
|------|------|----------------|
| M4: Reasoning | 🟢 完成 | `reasoning/orchestrator.py` |

### 實作步驟
1. **[步驟名稱]**
   - 檔案：`具體路徑`
   - 修改：具體內容
   - 驗證：如何確認

### 風險與依賴
- [潛在風險]

### 預估複雜度
- [x] 中等（2-5 個檔案）
```

### 重要規則

- Planner **不寫程式碼**，只輸出計劃
- 必須等使用者確認後才開始實作
- 必須引用具體檔案路徑（不可模糊）

---

## Commands 快捷指令

### /plan

**用途**：啟動 Planner Agent 規劃任務

**語法**：
```
/plan 實作用戶上傳功能
/plan 優化 Ranking 效能
```

**流程**：
1. 讀取 systemmap.md 了解模組
2. 讀取 CONTEXT.md 了解目前狀態
3. 輸出結構化計劃
4. 等待確認

---

### /index

**用途**：重建程式碼索引

**語法**：
```
/index
```

**執行**：
```bash
python tools/indexer.py --index
```

**使用時機**：
- 大量檔案修改後
- 新增模組後
- 搜尋結果不準確時

---

### /search

**用途**：使用索引搜尋程式碼

**語法**：
```
/search orchestrator
/search "gap detection"
```

**執行**：
```bash
python tools/indexer.py --search "關鍵字"
```

**優點**：
- SQLite FTS5 全文搜尋
- 結果精準且排序
- 比 Grep 節省大量 Token

---

### /status

**用途**：顯示專案狀態摘要

**語法**：
```
/status
```

**輸出**：
```
=== NLWeb 專案狀態 ===

目前重點：Production 優化

模組狀態：
- M0 Indexing: 🔴 規劃中
- M1 Input: 🟡 部分完成
- M2 Retrieval: 🟡 部分完成
- M3 Ranking: 🟢 完成
- M4 Reasoning: 🟢 完成
- M5 Output: 🟡 部分完成
- M6 Infrastructure: 🟢 完成

下一步：
1. [項目 1]
2. [項目 2]
```

---

### /learn

**用途**：記錄本次對話學到的 lesson

**語法**：
```
/learn
```

**流程**：
1. 分析對話，尋找非平凡問題的解決方案
2. 判斷是否值得記錄
3. 分類到對應領域
4. 評估信心等級
5. 追加到 `lessons-learned.md`

**輸出範例**：
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

**觸發時機**：
- 手動：隨時執行
- 自動：Session 結束時 hook 會提醒

---

## Rules 規則系統

### Token 優化規則

**位置**：`NLWeb\.claude\rules\token-optimization.md`

**核心規則**：

| 規則 | 說明 |
|------|------|
| 搜尋用索引 | 禁止 Grep，必須用 `tools/indexer.py` |
| 先讀文件 | 修改前先讀對應的 `docs/algo/*.md` |
| 漸進式讀取 | 設計文件 → 模組總覽 → 具體程式碼 |
| 限制讀取量 | 單檔案 < 500 行，單次最多 3 個檔案 |

**模組對應表**：

| 要修改 | 先讀 |
|--------|------|
| Reasoning | `docs/algo/reasoning_system.md` |
| Ranking | `docs/algo/ranking_pipeline.md` |
| 查詢分析 | `docs/algo/query_analysis.md` |
| API | `.claude/API_ENDPOINTS.md` |

---

### 效能規則（全域）

**位置**：`~\.claude\rules\performance.md`

**模型選擇**：

| 模型 | 適用場景 |
|------|----------|
| **Haiku** | 單檔案修改、格式化、簡單問答 |
| **Sonnet** | 日常開發、2-5 檔案修改、審查 |
| **Opus** | 架構設計、複雜推論、困難 debug |

**Context 管理**：

| 使用率 | 狀態 | 建議 |
|--------|------|------|
| < 60% | 🟢 | 正常工作 |
| 60-80% | 🟡 | 避免大量讀取 |
| > 80% | 🔴 | 總結後開新對話 |

---

## 維護指南

### 日常維護

| 檔案 | 頻率 | 內容 |
|------|------|------|
| `CONTEXT.md` | 每週 | 更新目前重點、最近完成 |
| `PROGRESS.md` | 完成里程碑時 | 記錄功能、Bug 修復 |
| `NEXT_STEPS.md` | 每週 | 更新計劃清單 |

### 定期維護

| 檔案 | 頻率 | 內容 |
|------|------|------|
| `systemmap.md` | 新增/修改模組時 | 更新狀態表、Data Flow |
| `docs/algo/*.md` | 修改核心演算法後 | 同步文件與程式碼 |
| 索引 (`/index`) | 大量修改後 | 重建搜尋索引 |

### 月度檢查清單

- [ ] `systemmap.md` 的模組狀態是否正確？
- [ ] `CONTEXT.md` 的「目前重點」是否過時？
- [ ] `codingrules.md` 是否需要新增規則？
- [ ] `docs/algo/` 的文件是否與程式碼一致？
- [ ] 索引是否包含所有新增的檔案？

---

## 常見問題

### Q: Hooks 沒有生效？

**檢查**：
1. 確認 `hooks.json` 語法正確（JSON 格式）
2. 確認在 NLWeb 目錄下啟動 Claude Code
3. 重新啟動 Claude Code session

---

### Q: /plan 輸出太簡略？

**解決**：
1. 提供更詳細的需求描述
2. 明確指出涉及的模組或功能
3. 說明預期的輸出或行為

---

### Q: 搜尋結果不準確？

**解決**：
1. 執行 `/index` 重建索引
2. 嘗試不同的關鍵字
3. 使用引號包含多字詞：`/search "gap detection"`

---

### Q: Context 使用率太高？

**解決**：
1. 總結目前進度到 `PROGRESS.md`
2. 更新 `CONTEXT.md` 的目前狀態
3. 開新對話，讓 hooks 自動載入 context
4. 避免一次讀取多個大檔案

---

### Q: 如何新增自訂 Command？

在 `NLWeb\.claude\commands\` 新增 `.md` 檔案：

```markdown
---
description: 指令描述
---

# /指令名稱

說明這個指令做什麼。

## 執行步驟
1. 步驟一
2. 步驟二

## 使用時機
- 情況一
- 情況二
```

---

## 參考資源

- [everything-claude-code](https://github.com/affaan-m/everything-claude-code) - 原始配置庫
- `.claude/IMPLEMENTATION_PLAN_CLAUDE_CODE_UPGRADE.md` - 實作計劃
- `.claude/systemmap.md` - NLWeb 模組總覽

---

*建立日期：2026-01-27*
*基於 everything-claude-code 最佳實踐*
