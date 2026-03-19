# /zoe Eval Changelog

## 2026-03-19 — 初版 eval 建立 + 第一次評估

### Eval 結果
- 1. 派工 prompt 有附 spec 路徑 + superpowers skill 指示嗎？→ **部分**（有些派工有，有些忘了）
- 2. 派工 prompt 有附模組特定陷阱嗎？→ **N**（多數派工沒附）
- 3. 沒有自己寫超過 20 行 code？→ **Y**
- 4. subagent 結果有 review 後再回報？→ **Y**
- 5. 回報時有提供技術判斷？→ **Y**

**得分**：3/5（#1 部分、#2 未通過）

### 根因分析
- #1 和 #2 都是「派工前準備不足」問題，根因相同：沒有強制的 Pre-Dispatch Checklist。
- 在 context 豐富時（剛讀完 spec），會自然附上路徑。但在多輪對話後容易忘。
- 模組特定陷阱（CLAUDE.md 以外的）需要主動查 memory/lessons-*.md，但派工時常常略過這步。

### Mutation（一次只改一個）
本次不修改 /zoe skill 本身（eval 才剛建立，先觀察一個 session）。下次 eval 若仍失敗，再加 Pre-Dispatch Checklist 到 /zoe。

## 2026-03-19 — 第二次評估（搜尋品質修復 session）

### Eval 結果
- 1. 派工 prompt 有附 spec 路徑 + superpowers skill 指示嗎？→ **Y**（5 個 agent 全附）
- 2. 派工 prompt 有附模組特定陷阱嗎？→ **Y**（P2 附 P1 的改動提醒、RSN-4 附 P0 的 guard 提醒）
- 3. 沒有自己寫超過 20 行 code？→ **Y**
- 4. subagent 結果有 review 後再回報？→ **Y**（每個結果摘要 + 技術判斷）
- 5. 回報時有提供技術判斷？→ **Y**（優先級排序、依賴分析、串行/並行決策）

**得分**：5/5（上次 3/5 → 本次 5/5）

### 觀察
- Pre-Dispatch Checklist 在 /zoe skill 本體中已存在，本次確實有逐項對照（spec 路徑、陷阱、skill 指示）。
- 關鍵改善：#1 和 #2 上次失敗，本次通過。根因：啟動時完整讀取 delegation-patterns.md + lessons，派工時有上下文可用。
- 串行化決策（P0→RSN-4、P1→P2）基於 delegation-patterns 的「同檔案禁止平行」原則，執行正確。
