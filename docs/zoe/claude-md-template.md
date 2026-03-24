# CLAUDE.md Template（Zoe 系統用）

> 這是 CLAUDE.md 的**模板**，供其他專案參考格式。需根據你的專案適配。
> 原始版本來自 NLWeb 專案。

---

## 專案概述

[一句話描述你的專案。目標、核心功能。]

**目前狀態**（YYYY-MM）：[一句話描述目前在做什麼。]

---

## 架構概述

**核心流程**：[描述你的系統的主要 data flow]

### 關鍵檔案對應

| 狀態區域 | 主要檔案 |
|----------|----------|
| [模組 A] | `path/to/files` |
| [模組 B] | `path/to/files` |
| ... | ... |

### 關鍵設計模式

[列出你的系統中重要的設計模式和架構決策]

---

## 文件查詢指令

**重要**：當被詢問特定模組或檔案時，必須先閱讀對應文件了解上下游模組關係：

| 詢問主題 | 需閱讀的文件 |
|----------|-------------|
| 系統總覽 | `docs/reference/systemmap.md` |
| 專案狀態 | `docs/status.md` |
| 已完成工作 | `docs/archive/completed-work.md` |
| 決策日誌 | `docs/decisions.md` |
| [模組] 規格 | `docs/specs/{module}-spec.md` |

---

## 重要開發規則

### Debug 與問題診斷：先讀 Memory

**關鍵**：被要求 debug 或診斷問題時，**必須**先讀取 memory 相關檔案，再開始調查。

**流程**：
1. 先讀 `memory/MEMORY.md`
2. 根據問題模組讀取對應 lessons 檔案
3. 確認是否為已知問題或類似 pattern
4. 若為新問題，才開始從程式碼調查

### 以盡速 debug 為前提，不可以 Silent Fail

**關鍵**：讓錯誤情況自然浮現，不可以 silently catch errors/exceptions。

- 可以優雅降級，但必須要有明確訊息表示已被降級。
- 絕對不可以讓錯誤被無視。

### Smoke Test：修改程式碼後必跑

**關鍵**：任何修改程式碼的操作完成後必須執行 smoke test。

```bash
# 替換為你的 smoke test 指令
cd your/project && python tools/smoke_test.py
```

FAILED 則立即修復，不可跳過。

**例外**：只修改 docs/、memory/、config、前端靜態檔案時不需要跑。

### 絕對禁止 Reward Hack

**關鍵**：必須尋求全面性解決方案。

- 從系統角度思考：上下游模組如何受影響？
- 不要在發現第一個問題就停下：目標是一次修復全部。

### 清理臨時檔案

完成任務後，務必刪除任何為了迭代而建立的臨時檔案、腳本或輔助檔案。

### 演算法變更

修改核心演算法時，**必須**更新 `docs/specs/` 目錄文件。

### Memory 更新規則

**禁止**將實質內容直接寫入 `MEMORY.md`。`MEMORY.md` 是純索引，只放檔案指標。

- 新的技術教訓 → 寫入對應的 `memory/lessons-*.md`
- 新的專案狀態 → 寫入對應的 `memory/project_*.md`
- 然後在 `MEMORY.md` 的 File Index 加一行指標
