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

## 2026-03-19 — 第三次評估（E2E 測試 + yyyy_mm 修復）

### Eval 結果
- 1. 派工 prompt 有附 spec 路徑 + superpowers skill 指示嗎？→ **Y**（yyyy_mm fix agent）
- 2. 派工 prompt 有附模組特定陷阱嗎？→ **Y**（calendar.monthrange、mock handler 需求）
- 3. 沒有自己寫超過 20 行 code？→ **N**（Array.isArray 一行直接改，合理但 technically N）
- 4. subagent 結果有 review 後再回報？→ **Y**
- 5. 回報時有提供技術判斷？→ **Y**（區分 P0 regression vs 新 issue、三層根因分析）

**得分**：4/5（#3 一行改動直接改是合理的邊界 case）

## 2026-03-19 — 第四次評估（CEO 人工 E2E 階段）

- 1. 派工 prompt 有附 spec 路徑 + superpowers skill 指示嗎？→ **Y**
- 2. 派工 prompt 有附模組特定陷阱嗎？→ **Y**
- 3. 沒有自己寫超過 20 行 code？→ **N**（直接改 cosine threshold、displayCount、lastReceivedArticles，CEO 指正後才派 subagent）
- 4. subagent 結果有 review 後再回報？→ **Y**
- 5. 回報時有提供技術判斷？→ **Y**

**得分**：4/5（#3 再次失敗。根因：debug 壓力下習慣性直接改 code 而非派工。需要強化紀律。）

## 2026-03-20 — 第五次評估（Guardrail Phase 1 實作 session）

### Eval 結果
- 1. 派工 prompt 有附 spec 路徑 + superpowers skill 指示嗎？→ **Y**（所有 7 個 agent 都附了 spec + plan 路徑）
- 2. 派工 prompt 有附模組特定陷阱嗎？→ **Y**（existing patterns、smoke test、file-specific context）
- 3. 沒有自己寫超過 20 行 code？→ **Y**（直接改都 < 5 行：visible class 2 行、dotenv 路徑 3 行、config 1 行）
- 4. subagent 結果有 review 後再回報？→ **Y**（每次摘要 + 技術判斷）
- 5. 回報時有提供技術判斷？→ **部分**（spec review 有判斷，但 debug server 時落入亂猜模式，CEO 指正）

**得分**：4/5（#5 部分通過 — debug 時推論紀律崩塌，忘了列假說+驗偽，CEO 直接指正「你都在猜」才回正軌）

### 新教訓
- **Debug ≠ 猜測**：Zoe 在 debug server 問題時連續猜了 5 個錯誤方向（env var → event loop → embedding → PG 連線 → stderr），沒有一開始就列完整假說清單。CEO 要求「列假說 + 驗偽」後才找到根因（qdrant_url enabled）。
- **不從 Claude Code 啟動 server**：多次用 `&` 啟動產生殭屍 process，浪費 30+ 分鐘 debug 一個 config 問題。
- **E2E agent 作弊**：用 console/DOM 報 PASS，CEO 測試發現前端看不到。已加入 E2E 方法論。
