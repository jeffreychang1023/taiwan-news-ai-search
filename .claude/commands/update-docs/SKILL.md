---
name: update-docs
description: |
  定期維護專案文件，同步程式碼與文件的一致性。結合 git 分析、對話摘要、程式碼結構掃描來更新文件。
  觸發時機：(1) 用戶輸入 /update-docs，(2) 完成功能開發後需要記錄進度，(3) 架構變更後需要更新文件。
  支援參數：all（全部）、progress（進度相關）、architecture（架構相關）、specs（規格文件）、docs（docs/ 目錄文件）、decisions（決策日誌）、patterns（delegation 經驗）。
---

# Update Docs

同步專案文件與程式碼的一致性。

## 參數

| 參數 | 更新範圍 |
|------|----------|
| `all` 或無參數 | 全部文件（specs + docs + architecture + progress + decisions + patterns）|
| `progress` | `docs/status.md`, `CLAUDE.md` |
| `architecture` | `docs/reference/systemmap.md`, `docs/reference/architecture/` |
| `specs` | `docs/specs/*-spec.md` |
| `docs` | `docs/` 下活躍文件（排除 `archive/`） |
| `decisions` | `docs/decisions.md` |
| `patterns` | `memory/delegation-patterns.md` |

## 文件分工

| 文件 | 定位 | 更新策略 |
|------|------|----------|
| `CLAUDE.md` | 專案入口指引 | 更新模組狀態表、開發重點 |
| `docs/status.md` | 當前工作上下文 + 進度 + 下一步 | 從對話摘要 + git log 更新 |
| `docs/archive/completed-work.md` | 已完成工作歸檔 | 追加新完成項目 |
| `docs/reference/systemmap.md` | 靜態結構 | 模組清單、API、檔案對應 |
| `docs/reference/architecture/state-machine-diagram.md` | 動態流程 | **半自動**：偵測變更區塊，提示更新 |
| `docs/specs/*-spec.md` | 模組規格 | 根據對應模組變更更新 |
| `docs/*.md`（非 spec、非 archive） | 指南與說明 | 根據對應功能變更更新 |
| `docs/decisions.md` | 架構/商業/產品決策日誌 | 追加新決策、標記 superseded |
| `memory/delegation-patterns.md` | Delegation 經驗手冊 | 從 delegation 結果更新模組指引 |
| `static/architecture.html` | 視覺化 | **手動維護**，skill 會提醒 |

---

## Source of Truth 與更新優先順序

```
程式碼 → Spec 文件 → Docs 指南 → State Machine Diagram / Systemmap → Progress 文件
```

| 層級 | 文件 | 說明 |
|------|------|------|
| **L1: 程式碼** | `code/python/**/*.py` | 最終真相 |
| **L2: Spec 文件** | `docs/specs/*-spec.md` | 模組級規格，貼近實作 |
| **L2.5: Docs 指南** | `docs/*.md`（非 spec） | 功能指南、使用說明，從 L1/L2 推導 |
| **L3: 架構文件** | `docs/reference/architecture/`, `docs/reference/systemmap.md` | 系統級視圖，從 L2 推導 |
| **L4: 進度文件** | `docs/status.md` | 工作追蹤，從對話/git 推導 |
| **L5: 決策/經驗** | `docs/decisions.md`, `memory/delegation-patterns.md` | 從對話中提取 |

**更新原則**：
- 高層級文件（L3/L4/L5）根據低層級文件（L1/L2）更新
- 如果 spec 與 state-machine-diagram 衝突，**以 spec 為準**
- 如果 systemmap 與 spec 衝突，**以 spec 為準**

---

## 執行流程

### 1. 收集資訊

```bash
# Git 變更分析
git diff --stat HEAD~10
git log --oneline -20

# 程式碼結構掃描
python tools/indexer.py --index
```

掃描以下目錄的結構變化：
- `code/python/` - 主要程式碼
- `code/python/reasoning/` - Reasoning 系統
- `code/python/core/` - 核心模組
- `code/python/indexing/` - Indexing 模組
- `code/python/crawler/` - Crawler 模組

### 2. 分析變更

比較現有文件與實際程式碼：
- 檢查模組是否新增/刪除/重命名
- 檢查 API 端點是否變更
- 檢查狀態機流程是否變更
- 檢查 spec 文件對應的模組是否變更

### 3. 更新文件

依參數決定更新範圍，直接編輯文件。

---

### progress 範圍

更新目標：`docs/status.md`, `CLAUDE.md`

1. 從對話中提取完成的工作 → 追加至 `docs/archive/completed-work.md`
2. 從對話 + git log 提取目前狀態 → 更新 `docs/status.md`
3. 移除已完成項目、新增待辦 → 更新 `docs/status.md` 的下一步段落
4. 更新 `CLAUDE.md` 模組狀態表與開發重點

---

### architecture 範圍

更新目標：`docs/reference/systemmap.md`, `docs/reference/architecture/`

1. **先更新 spec**：確保 spec 文件與程式碼同步
2. **再更新 systemmap**：根據 spec 文件更新模組清單
3. **最後更新 state-machine-diagram**：根據 spec + 程式碼半自動更新（見下方詳細流程）

> **注意**：systemmap 和 state-machine-diagram 的內容應以 spec 為準，不是反過來。

---

### specs 範圍

更新目標：`docs/specs/*-spec.md`

1. 根據 git diff 判斷哪些 spec 需要更新
2. 檢查 spec 之間的關聯性，以最新的為主調整舊的
3. 更新對應的 spec 文件

---

### docs 範圍

更新目標：`docs/` 下所有活躍文件（排除 `docs/archive/`）

1. 掃描 `docs/` 目錄下所有活躍文件
2. 根據 git diff 判斷哪些 docs 需要更新
3. 檢查文件與對應程式碼/功能是否同步
4. 更新過時的指南、說明文件

---

### decisions 範圍

更新目標：`docs/decisions.md`

1. **回顧本次對話**：是否有新的架構/商業/產品決策？
2. **如果有新決策** → 追加至 `docs/decisions.md`，格式：

```markdown
### [Decision Title]
- **Category**: Architecture / Product / Business / Performance / Infrastructure
- **Modules**: M0-M6 中受影響的模組
- **Date**: YYYY-MM-DD
- **Status**: active
- **Decision**: [具體決策內容]
- **Reason**: [為什麼這樣決定]
- **Tradeoff**: [放棄了什麼、接受了什麼風險]
```

3. **如果有 superseded 的決策** → 將舊決策 Status 改為 `superseded`，加註 `Superseded by: [新決策標題]`

---

### patterns 範圍

更新目標：`memory/delegation-patterns.md`

1. **本次有 delegation 嗎？** — 回顧對話中是否使用了 `/delegate` 或手動派工
2. **結果如何？** — 成功/失敗/需要額外資訊
3. **有新的考量要加入嗎？** — 例如：
   - 某模組新增了重要的程式碼檔案
   - 發現新的陷阱或依賴關係
   - Spec 檔案新增/更名
4. **更新 delegation-patterns.md** 對應段落（模組特定指引）

---

### all 範圍（按優先順序執行）

1. **specs** — 先確保 spec 文件與程式碼同步
2. **docs** — 根據 spec 和程式碼更新 docs/ 下的指南文件
3. **architecture** — 根據 spec 更新 systemmap 和 state-machine-diagram
4. **progress** — 更新 status.md + CLAUDE.md
5. **decisions** — 記錄新決策
6. **patterns** — 更新 delegation 經驗
7. **CLAUDE.md** — 最後更新模組狀態表

---

## State Machine Diagram 半自動更新流程

### 檔案 → 區塊對應表

| 變更檔案 | 影響的狀態圖區塊 |
|----------|------------------|
| `webserver/aiohttp_server.py` | Section 1: 系統總覽 |
| `webserver/middleware/*`, `chat/websocket.py` | Section 2: 連接層狀態 |
| `core/baseHandler.py`, `core/state.py` | Section 3: 請求處理狀態 |
| `core/query_analysis/*.py` | Section 3: Pre-Retrieval |
| `core/retriever.py`, `core/bm25.py` | Section 3: Retrieval |
| `core/ranking.py`, `core/xgboost_ranker.py`, `core/mmr.py` | Section 4: 排序管道狀態 |
| `reasoning/orchestrator.py`, `reasoning/agents/*.py` | Section 5: Reasoning 系統狀態 |
| `chat/conversation.py`, `chat/websocket.py` | Section 6: Chat 系統狀態 |
| `core/utils/message_senders.py`, `core/schemas.py` | Section 7: SSE 串流狀態 |
| 錯誤處理相關 | Section 8: 錯誤處理狀態 |
| `core/state.py` | Section 9: Handler State |

### Section 10 特別處理

Section 10 是 **Sequence Diagram**（時序圖），與 Section 1-9 的 State Diagram 不同：

| 類型 | 用途 | 更新觸發 |
|------|------|----------|
| State Diagram (1-9) | 單一元件的狀態轉換 | 該元件內部邏輯變更 |
| Sequence Diagram (10) | 跨元件的互動流程 | 元件間**介面**變更 |

**觸發條件**：
- SSE 訊息類型改變（`core/schemas.py`）
- API 參數改變（`webserver/routes/*.py`）
- 新增/移除/重命名元件
- 元件間呼叫順序改變

**不觸發**：單純內部邏輯變更（不影響介面）

### 更新流程

1. **偵測變更**：執行 `git diff --name-only HEAD~10` 取得變更檔案清單
2. **對應區塊**：根據上表找出受影響的區塊
3. **提示用戶**：輸出「以下區塊可能需要更新：Section X (名稱)」
4. **讀取程式碼**：讀取變更的程式碼檔案
5. **比較差異**：比較現有 Mermaid 圖與程式碼邏輯
6. **提出建議**：說明需要修改的狀態、轉換條件
7. **執行更新**：在用戶確認後更新 `docs/reference/architecture/state-machine-diagram.md`

---

## Spec 文件更新流程

### Spec 文件自動偵測

**偵測機制**：自動掃描 `docs/specs/*-spec.md`，不需要手動維護清單。

```bash
ls docs/specs/
```

### 已知 Spec 文件對應表

| Spec 文件 | 對應模組/目錄 | 觸發條件 |
|-----------|---------------|----------|
| `docs/specs/indexing-spec.md` | M0 Indexing | `indexing/`, `crawler/` 變更 |
| `docs/specs/crawler-dashboard-spec.md` | M0 Crawler | `crawler/`, `indexing/dashboard*` 變更 |
| `docs/specs/frontend-spec.md` | M5 Frontend | `static/`, `webserver/routes/` 變更 |
| `docs/specs/reasoning-spec.md` | M4 Reasoning | `reasoning/` 變更 |
| `docs/specs/reranking-spec.md` | M3 Ranking | `core/ranking.py`, `core/mmr.py`, `core/xgboost*` 變更 |

**新 spec 處理**：如果偵測到未在對應表中的 spec，提示用戶確認對應模組。

### 關聯性處理

當多個 spec 需要更新時：

1. **檢查最後更新日期**：從文件末尾的 `*更新：YYYY-MM-DD*` 取得
2. **以最新為主**：如果 spec A 比 spec B 新，且兩者有關聯內容，以 A 為準調整 B
3. **關聯性定義**：
   - `indexing-spec` <-> `crawler-dashboard-spec`：共享 Crawler 資料流
   - `indexing-spec` <-> `reasoning-spec`：共享資料格式（payload schema）
   - `reranking-spec` <-> `reasoning-spec`：共享排序結果處理

---

## Docs 文件更新流程

### Docs 文件自動偵測

**偵測機制**：自動掃描 `docs/` 下活躍文件，排除 archive 和 specs。

```bash
# 偵測活躍 docs（排除 archive 和 specs）
ls docs/*.md
ls docs/reference/
ls docs/in\ progress/
```

### 已知 Docs 文件對應表

| Docs 文件 | 對應模組/功能 | 觸發條件 |
|-----------|---------------|----------|
| `docs/reference/code-in-sqlite.md` | 程式碼索引工具 | `tools/indexer.py` 變更 |
| `docs/reference/architecture/state-machine-diagram-explained.md` | 狀態機說明 | `state-machine-diagram.md` 變更 |

**新文件處理**：如果偵測到未在對應表中的 docs，根據檔名和內容推斷對應模組。

---

## 文件格式規範

### docs/status.md 格式

```markdown
# 專案狀態

## 目前狀態
[簡述目前在做什麼]

## 最近完成
- [項目1]
- [項目2]

## 下一步
- [待辦1]
- [待辦2]

## 待解決問題
- [問題1]
```

### docs/decisions.md 格式

```markdown
### [Decision Title]
- **Category**: Architecture / Product / Business / Performance / Infrastructure
- **Modules**: M0-M6
- **Date**: YYYY-MM-DD
- **Status**: active / superseded
- **Decision**: [內容]
- **Reason**: [原因]
- **Tradeoff**: [取捨]
```

### systemmap.md 靜態結構重點

- 模組清單（M0-M6）及狀態
- 關鍵檔案對應表
- API 端點清單
- SSE 訊息類型

### state-machine-diagram.md 動態流程重點

- Mermaid 狀態圖（10 個區塊）
- 狀態轉換條件
- 錯誤處理流程
- 關鍵檔案對應表

### Spec 文件格式重點

- 模組概述
- 核心元件說明
- 資料流與介面
- 設定參數
- CLI 使用方式（如適用）
- 最後更新日期

---

## 完成後提醒

完成後輸出：
```
文件更新完成。

以下文件需要手動維護：
- static/architecture.html - 請在瀏覽器中開啟並編輯視覺化架構圖

是否要 commit 這些文件變更？(y/n)
```

若用戶同意，執行：
```bash
git add CLAUDE.md docs/ memory/delegation-patterns.md
git commit -m "docs: update project documentation"
```
