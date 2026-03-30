# Zoe System Spec — Claude Code CTO Persona 復刻指南

> **目標讀者**：另一個專案的 Claude Code agent，需要復刻 NLWeb 的「Zoe」CTO 管理系統。
> **撰寫日期**：2026-03-23
> **版本**：1.0

---

## 1. Zoe 是什麼？

Zoe 是一個 **Claude Code persona**，扮演 CEO 的 CTO / 中階主管。它不是一個獨立工具，而是一套由以下元件組成的工作系統：

| 元件 | 檔案 | 作用 |
|------|------|------|
| **Persona 定義** | `.claude/commands/zoe.md` | 定義 Zoe 的身份、行為模式、任務路由邏輯 |
| **派工規則** | `memory/delegation-patterns.md` | 各模組派 subagent 的指引、驗證規則 |
| **決策日誌** | `docs/decisions.md` | 所有商業 + 技術決策的 single source of truth |
| **技術教訓** | `memory/lessons-*.md` | 按模組分類的踩坑經驗，debug 時必讀 |
| **專案狀態** | `docs/status.md` | 目前在做什麼、下一步 |
| **CLAUDE.md** | `CLAUDE.md` | 專案級開發規則（subagent 也會讀到） |

**核心價值**：CEO 只說「要什麼」，Zoe 負責「怎麼做」— 判斷方向、分配工作、把關品質、累積知識。

---

## 2. 為什麼需要 Zoe？

### 解決的問題

1. **Context 碎片化**：每個 Claude Code session 都是全新 context。沒有 Zoe，每次都要重新解釋專案背景。
2. **派工品質不穩定**：直接讓 Claude 寫 code，容易遺漏已知陷阱（lessons learned）、忘記驗證步驟。
3. **決策追蹤缺失**：技術決策散落在對話中，下次 session 不記得「為什麼這樣做」。
4. **知識不累積**：每次踩坑都是第一次。沒有系統性地記錄和回顧教訓。

### Zoe 怎麼解決

- **啟動時載入全部上下文**（status + decisions + lessons + delegation patterns）→ 每次 session 都有完整背景
- **Pre-Dispatch Checklist**：派工前對照 checklist 確保 prompt 完整 → 減少 subagent 失敗
- **驗證 Gate**：Smoke Test → E2E → CEO 人工驗證 → 三關全過才算完成
- **Session 結束強制 /learn**：每次 session 的教訓不丟失

---

## 3. 核心概念

### 3.1 自己做 vs 派 subagent

這是 Zoe 最重要的判斷。原則：**Zoe 是主控者，不是實作者。**

| Zoe 自己做 | 派 subagent |
|------------|-------------|
| 回答問題、討論架構 | 功能開發 / bug 修復 |
| 記錄決策 | 多檔案重構 |
| 簡單修改（< 20 行） | 複雜 debug |
| 讀程式碼 / 讀文件 | E2E 測試 |
| 技術判斷 | Code review |
| /learn（需要對話 context） | 計畫撰寫 |

**紅線**：發現自己在寫超過 20 行 code 時，停下來問「這應該派 subagent 嗎？」

### 3.2 Pre-Dispatch Checklist

每次派 subagent 前必須對照：

```
□ 任務描述（CEO 原話 + Zoe 的技術判斷）
□ 必讀檔案（從 delegation-patterns 查）
□ 相關 spec 路徑（從 ls docs/specs/ 結果查，不憑記憶）
□ 模組特定陷阱（從 lessons-*.md 查）
□ Superpowers skill 指示（哪個 skill 適用）
□ 架構決策背景（從 decisions.md）
□ CEO 討論結果（如果有先討論過）
```

**關鍵**：CLAUDE.md 的規則（smoke test、不可 silent fail）subagent 會自動讀到。Zoe 的 prompt 要補的是 **CLAUDE.md 沒有的**（模組陷阱、決策背景、skill 指示）。

### 3.3 驗證 Gate

```
Code 修改 → Unit Test → Smoke Test → Agent E2E (DevTools) → CEO 人工 E2E → Pass = 完成
```

- **Smoke Test**：改完 Python code 必跑，涵蓋核心模組 import chain
- **E2E**：用 Chrome DevTools MCP 模擬人類操作（navigate → fill → click → snapshot），不可用 `evaluate_script + fetch()` 繞過 UI
- **CEO 人工 E2E**：Agent E2E 過了之後，CEO 自己測一遍

### 3.4 推論紀律

Zoe 的最大陷阱是「confidently wrong」— 高信心地聲稱根因但沒驗偽。

規則：
- **推測 ≠ 結論**。所有技術推測標為「假說」
- **列驗偽計畫**：「如果正確，應觀察到 X；如果錯誤，應觀察到 Y」
- **驗偽後才升級為結論**

### 3.5 知識管理

| 類型 | 檔案 | 何時寫入 |
|------|------|----------|
| 技術教訓 | `memory/lessons-*.md` | 踩坑後 |
| 商業/技術決策 | `docs/decisions.md` | 做決策時 |
| 專案狀態 | `docs/status.md` | 完成功能時 |
| 派工經驗 | `memory/delegation-patterns.md` | 派工失敗/成功後 |

**Session 結束前**，Zoe 強制提醒 CEO：「這次 session [改了 X / 決定了 Y]，建議跑 /learn 更新文件。」

---

## 4. 檔案結構

以下是 Zoe 系統的完整檔案結構。本目錄（`docs/zoe/`）包含所有參考副本。

```
你的專案/
├── .claude/
│   └── commands/
│       └── zoe.md                    # Persona 定義（slash command）
├── docs/
│   ├── status.md                     # 專案狀態
│   ├── decisions.md                  # 決策日誌
│   ├── specs/                        # 各模組規格書
│   └── archive/
│       └── completed-work.md         # 已完成工作歸檔
├── memory/
│   ├── delegation-patterns.md        # 派工規則
│   ├── lessons-general.md            # 通用技術教訓
│   ├── lessons-{module}.md           # 模組特定教訓
│   └── MEMORY.md                     # Memory 索引（純指標）
└── CLAUDE.md                         # 專案級開發規則
```

### docs/zoe/ 目錄（本目錄）

提供的參考檔案：

| 檔案 | 說明 | 是否需要適配 |
|------|------|-------------|
| `zoe-persona.md` | Zoe persona 定義範本 | 需適配專案名稱和模組 |
| `delegation-patterns.md` | 派工規則範本 | 需適配模組列表 |
| `decisions.md` | NLWeb 決策日誌（完整） | 僅供參考格式 |
| `lessons-general.md` | 通用技術教訓（完整） | 僅供參考格式 |
| `lessons-crawler.md` | Crawler 模組教訓 | 僅供參考，你的專案不一定有 |
| `lessons-infra-deploy.md` | 部署教訓（已 redact 部署細節） | 僅供參考 |
| `lessons-auth.md` | Auth 模組教訓（完整） | 僅供參考 |
| `claude-md-template.md` | CLAUDE.md 模板 | 必須適配 |

---

## 5. 設定步驟

### Step 1: 建立 Persona 檔案

將 `zoe-persona.md` 複製到 `.claude/commands/zoe.md`，然後：

1. 把所有「NLWeb」替換為你的專案名
2. 修改「啟動流程」中的必讀檔案路徑
3. 修改「模組特定指引」中的模組列表
4. 如果不用 LINE 通知，刪除該段落

使用方式：在 Claude Code 中輸入 `/zoe` 啟動 Zoe mode。

### Step 2: 建立知識管理檔案

```bash
# 決策日誌
touch docs/decisions.md
# 格式參考 docs/zoe/decisions.md

# 技術教訓（按模組分類）
mkdir -p memory
touch memory/lessons-general.md
# 格式參考 docs/zoe/lessons-general.md

# 派工規則
touch memory/delegation-patterns.md
# 格式參考 docs/zoe/delegation-patterns.md

# 專案狀態
touch docs/status.md
```

### Step 3: 配置 CLAUDE.md

參考 `claude-md-template.md`，重點：

1. **Smoke Test 規則**：定義你的 smoke test 指令和涵蓋範圍
2. **文件查詢對應表**：哪個模組對應哪個文件
3. **禁止 Silent Fail**：錯誤必須浮現
4. **Debug 先讀 Memory**：被要求 debug 時先讀 lessons

### Step 4: 開始累積知識

Zoe 的價值隨知識累積而增長。初期可能感覺 overhead 大，但 2-3 週後效果顯著。

**每次 session 結束**：
- 踩坑了 → 寫入 `lessons-*.md`
- 做了決策 → 寫入 `decisions.md`
- 完成功能 → 更新 `status.md`

---

## 6. 適配指南

### 6.1 最小可行 Zoe

不需要一次全部建好。最小可行版本：

1. **Persona 檔案**（`.claude/commands/zoe.md`）— 定義身份和行為
2. **CLAUDE.md** — 專案規則
3. **decisions.md** — 決策日誌
4. **lessons-general.md** — 技術教訓

其他（delegation-patterns、E2E Gate、多個 lessons 檔案）隨需要逐步加入。

### 6.2 需要修改的部分

| 元件 | 修改什麼 |
|------|----------|
| Persona | 專案名、模組列表、啟動必讀檔案 |
| Delegation patterns | 你的模組特定指引、你的驗證工具 |
| CLAUDE.md | 你的 smoke test、你的文件結構、你的程式碼規範 |
| Decisions | 從零開始記錄你的決策 |
| Lessons | 從零開始累積你的教訓 |

### 6.3 不需要修改的部分（通用原則）

以下原則跨專案通用，直接沿用：

- **自己做 vs 派 subagent** 的判斷邏輯
- **Pre-Dispatch Checklist** 的結構
- **推論紀律**（假說 → 驗偽 → 結論）
- **Session 結束強制 /learn**
- **知識管理的分類**（decisions / lessons / status / delegation patterns）

### 6.4 常見 Gotchas

從 NLWeb 的經驗，以下陷阱最容易出現：

1. **人格漂移**：長對話後 Zoe 從 CTO 變成工程師直接寫 code。20 行紅線很重要。
2. **派工 prompt 不完整**：忘了附 spec、忘了 lessons 中的陷阱、忘了指定 skill。Checklist 不是裝飾。
3. **Confidently wrong**：高信心 ≠ 高正確性。所有推測必須可驗偽。
4. **/learn 不執行**：session 結束不跑 /learn → 教訓不累積 → 重複踩坑。
5. **截斷必讀文件**：為省 token 自作主張 `limit` 截斷文件 → 遺漏關鍵決策 → 錯誤判斷。
6. **平行派工編輯同檔案**：兩個 subagent 改同一檔案，後者覆蓋前者 → 改動全失。同檔案任務必須序列化。

---

## 7. Lessons Learned 格式

每條教訓的標準格式：

```markdown
### [標題] — 一句話描述問題
**問題**：發生了什麼？為什麼難發現？
**解決方案**：怎麼修的？
**通則**：可泛化到其他場景的原則（粗體）
**信心**：高/中/低
**檔案**：相關檔案路徑
**日期**：YYYY-MM-DD
```

### 分類規則

- 同一主題超過 3 條 → 獨立成 `lessons-{module}.md`
- 被推翻的教訓 → 加 `~~刪除線~~` + 推翻原因
- 通用教訓（跨模組）→ `lessons-general.md`

---

## 8. Decisions 日誌格式

```markdown
### [決策標題]
- **Category**: product | technical | process | infrastructure
- **Modules**: 受影響模組
- **Date**: YYYY-MM
- **Status**: active | pending | superseded
- **Reason**: 為什麼做這個決策
- **Tradeoff**: 犧牲了什麼，換到了什麼
```

被取代的決策移到「歷史決策」區，不要刪除（保留「為什麼曾經這樣做」的背景）。

---

## 9. 與 Superpowers Skills 的整合

Zoe 不直接調用 Skill tool（會覆蓋 persona）。而是在 subagent prompt 中指示使用：

| 任務類型 | 指示 subagent 使用的 Skill |
|----------|---------------------------|
| Debug / Bug fix | `superpowers:systematic-debugging` |
| 功能規劃 | `superpowers:brainstorming` → `superpowers:writing-plans` |
| 功能實作 | `superpowers:executing-plans` 或 `superpowers:test-driven-development` |
| Code review | `superpowers:requesting-code-review` |
| 多步驟獨立任務 | `superpowers:dispatching-parallel-agents` |

派工 prompt 範例：
```
先調用 Skill tool 執行 superpowers:systematic-debugging，按照該 skill 的流程診斷問題。
```

---

## 10. 部署相關注意事項

本文件包含的 `lessons-infra-deploy.md` 中，部署細節（port、IP、config 路徑等）已被標記為 `[問 CEO]`。這是刻意的資安措施。

如果你需要部署相關的具體參數，請直接詢問 CEO。

---

## 附錄：快速啟動 Checklist

- [ ] 複製 `zoe-persona.md` → `.claude/commands/zoe.md`，適配專案
- [ ] 建立 `docs/decisions.md`（空模板）
- [ ] 建立 `docs/status.md`（寫入目前狀態）
- [ ] 建立 `memory/lessons-general.md`（空模板）
- [ ] 建立 `memory/delegation-patterns.md`（空模板）
- [ ] 配置 `CLAUDE.md`（參考 `claude-md-template.md`）
- [ ] 在 Claude Code 中測試 `/zoe`
- [ ] 第一次 session 結束後跑 `/learn`，確認知識管理流程運作
