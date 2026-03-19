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
