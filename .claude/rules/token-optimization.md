# Token 優化規則（NLWeb 專用）

> 目標：只在需要的時候填充 AI context window，節省 token

---

## 強制規則

### 1. 程式碼搜尋

| 情況   | 做法                                       |
| ---- | ---------------------------------------- |
| ❌ 禁止 | 直接使用 Grep 搜尋程式碼                          |
| ✅ 必須 | `python tools/indexer.py --search "關鍵字"` |

**原因**：索引系統使用 SQLite FTS5，回傳精準且排序的結果，避免大量無關檔案填充 context。

---

### 2. 了解系統架構

| 情況   | 做法                               |
| ---- | -------------------------------- |
| ❌ 禁止 | 遍歷目錄結構、讀取多個檔案來了解專案               |
| ✅ 必須 | 先讀 `docs/reference/systemmap.md` |

---

### 3. 了解目前狀態

| 情況   | 做法                  |
| ---- | ------------------- |
| ❌ 禁止 | 問使用者「目前在做什麼」        |
| ✅ 必須 | 先讀 `docs/status.md` |

---

### 4. 修改特定模組前

| 要修改          | 先讀                                                                              |
| ------------ | ------------------------------------------------------------------------------- |
| Reasoning 相關 | `docs/reference/systemmap.md` Reasoning 章節                                      |
| Ranking 相關   | `docs/specs/bm25-spec.md`、`docs/specs/xgboost-spec.md`、`docs/specs/mmr-spec.md` |
| 查詢分析相關       | `docs/reference/systemmap.md` Pre-Retrieval 章節                                  |
| API 相關       | `docs/reference/api-endpoints.md`                                               |
| 資料流          | `docs/reference/systemmap.md` 的 Data Flow 章節                                    |

**禁止**：直接讀取所有 agent 檔案或整個目錄

---

## 漸進式讀取策略

當需要了解某功能時，依序執行：

```
1. 讀設計文件 → docs/specs/*-spec.md
         ↓
2. 讀模組總覽 → docs/reference/systemmap.md 對應段落
         ↓
3. 讀具體程式碼（只讀必要部分）
```

**禁止**：跳過步驟 1、2 直接讀程式碼

---

## 檔案讀取限制

### 單次讀取上限

- 
- 單次操作：最多 3 個檔案

### 禁止一次讀取

- 整個 `reasoning/agents/` 目錄
- 整個 `core/` 目錄
- 所有 config 檔案

### 正確做法

1. 先讀 systemmap.md 確定需要哪些檔案
2. 只讀取明確需要的檔案
3. 大檔案分段讀取

---

## 搜尋策略優先順序

1. **索引搜尋**（最佳）
   
   ```bash
   python tools/indexer.py --search "orchestrator"
   ```

2. **Glob 檔名搜尋**（次佳）
   
   ```
   Glob: **/orchestrator*.py
   ```

3. **Grep 內容搜尋**（最後手段）
   
   - 只有在索引系統無法使用時
   - 必須限定目錄範圍

---

## Context 管理

### 警戒信號

當出現以下情況，考慮清理 context：

- 對話變得緩慢
- 回應開始重複之前說過的話
- 無法記住對話早期的內容

### 清理策略

1. 總結目前進度到 `docs/status.md`
2. 更新 `docs/status.md` 的目前狀態
3. 開新對話繼續

---

## 檢查清單

每次開始任務前，確認：

- [ ] 已讀 `docs/status.md`？
- [ ] 已讀 `docs/reference/systemmap.md` 相關段落？
- [ ] 知道要修改哪些檔案？
- [ ] 沒有載入不必要的檔案？
