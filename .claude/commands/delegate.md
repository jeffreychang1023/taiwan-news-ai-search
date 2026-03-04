---
name: delegate
description: |
  Zoe 的核心派工能力。分析 CEO 指令，收集必要上下文，選擇正確的 skill 或 agent 執行任務。
  觸發時機：CEO 下達需要派工的指令（功能開發、bug 修復、重構、文件更新等）。
  用法：/delegate <CEO 指令>
---

# Delegate

CEO 指令的智慧派工。收集上下文 → 判斷方向 → 選擇 skill → 派工 → 回報。

## 執行流程

### Step 1: 收集上下文（必做，全部平行讀取）

```
同時讀取以下檔案：
1. docs/status.md              — 目前狀態，避免衝突
2. docs/decisions.md           — 為什麼這樣設計，避免走回頭路
3. memory/delegation-patterns.md — 模組經驗，知道 agent 需要什麼
4. memory/lessons-learned.md   — 技術陷阱，避免已知地雷
```

### Step 2: 發現相關 Spec

```bash
ls docs/specs/
```

從列表中判斷哪些 spec 與 CEO 指令相關。**不憑記憶列舉**，每次動態發現。

### Step 3: 判斷方向

根據收集到的上下文，判斷：

| 問題 | 判斷依據 |
|------|----------|
| 涉及哪些模組？ | delegation-patterns.md 的模組分類 |
| 有無相關決策？ | decisions.md 中是否有相關 entry |
| 有無已知陷阱？ | lessons-learned.md 中相關 pattern |
| 需要哪些 spec？ | Step 2 發現的 spec 列表 |
| 目前狀態是否允許？ | status.md 中有無衝突的進行中工作 |

**如果方向不明確**：向 CEO 提出具體問題釐清，不要猜測。

### Step 4: 選擇執行方式

根據任務性質選擇 skill 或直接派工：

| 任務性質 | 選擇 |
|----------|------|
| Bug 修復 | `systematic-debugging` skill |
| 新功能（需設計） | `brainstorming` skill → 再派工 |
| 多步驟實作計畫 | `writing-plans` skill |
| 多個獨立子任務 | `dispatching-parallel-agents` skill |
| 單一明確修改 | 直接用 Agent tool 派工 |
| 文件更新 | `update-docs` skill |
| 程式碼品質 | `simplify` skill 或 `requesting-code-review` skill |

### Step 5: 組裝 Agent Prompt

從 delegation-patterns.md 取得對應模組的指引：

```
1. 優先閱讀的程式碼（從 patterns 查）
2. 相關 spec 檔案路徑（從 Step 2 查）
3. 模組特定考量（從 patterns 查）
4. 已知陷阱（從 lessons-learned 查）
5. CEO 的原始指令
```

**model 選擇**：交給 Agent tool 的 model 參數，根據任務複雜度判斷：
- Haiku：單檔案小修改、格式化
- Sonnet：一般功能開發、跨 2-5 檔案
- Opus：架構決策、複雜推論、困難 debug

### Step 6: 派工並回報

派工後，向 CEO 回報：

```
## 派工回報

**任務**：[一句話描述]
**執行方式**：[選擇的 skill 或 Agent tool]
**涉及模組**：[模組名稱]
**涉及檔案**：[主要檔案列表]
**相關 Spec**：[相關 spec 檔案]
**已知風險**：[從 lessons-learned 中找到的相關陷阱，若無則省略]
**預期結果**：[完成後應該看到什麼]
```

---

## 注意事項

1. **不寫 prompt template** — 選擇正確的 skill，讓 skill 本身引導流程
2. **不手動列 spec** — 每次 `ls docs/specs/` 動態發現
3. **Docs 一致性** — 任務完成後提醒 CEO 是否需要 `/update-docs`
4. **學習迴圈** — 如果 delegation 過程中發現新的 pattern 或 lesson，提醒記錄
