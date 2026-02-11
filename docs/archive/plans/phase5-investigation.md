# Phase 5 調查報告

> 調查日期：2026-01-30
> 來源：`docs/bugfix-phases.md` Phase 5 全部 7 個 Bug
> 狀態：調查完成，待逐一決策

---

## 總覽

| Bug | 標題 | 難度 | 阻擋項 | 建議優先序 |
|-----|------|------|--------|-----------|
| #4 | Clarification 加入自由聚焦選項 | 低 | 無 | 1 |
| #5 | 深度研究歧義檢測 | — | 暫不修改 | — |
| #14 | 回饋按鈕 modal + DB | 中 | 無 | 2 |
| #7 | LLM_KNOWLEDGE 標記太少 | 中 | 無 | 3 |
| #12 | Query Expansion（治安→張文） | 中高 | 無 | 4 |
| #8 | 聚合型查詢（十大新聞） | 高 | 功能限制 | 5 |
| #15 | 抽象股票查詢失敗 | 高 | 依賴 #12 | 6 |
| #21 | 記者查詢跑不出結果 | 中 | 依賴 Phase 3 #18-20 | 7 |

---

## Bug #4：Clarification 加入自由聚焦選項

### 現狀發現

- `addClarificationMessage()` 位於 `news-search.js:2993`
- 每個 question block **已有**自訂文字輸入（line 3066-3078，placeholder「或自行輸入...」）
- Submit 按鈕（"開始搜尋"）在 line 3085
- `attachClarificationListeners()` 在 line 3103 處理所有互動邏輯

### 需要的變更

在所有 question blocks 之後、submit 按鈕之前（line ~3083），插入全局附加區塊：

```
┌─────────────────────────────────────────┐
│  [現有 question blocks...]              │
│                                         │
│  ── 新增區塊 ──                          │
│  「有沒有其他你想更具體聚焦的內容？」         │
│  [________________自由文字輸入__________]  │
│                                         │
│  [沒有，直接開始研究]   [開始搜尋]          │
└─────────────────────────────────────────┘
```

### 涉及檔案

| 檔案 | 變更 |
|------|------|
| `static/news-search.js` | `addClarificationMessage()` 加入 HTML；`attachClarificationListeners()` 加入事件處理 |

### 實作細節

1. **HTML**：在 line ~3083（submit button 之前）插入：
   - 分隔線 + 提示文字
   - `<input>` 自由文字輸入（class `clarification-extra-focus`）
   - 「沒有，直接開始研究」按鈕（class `skip-clarification`）

2. **JS 邏輯**：
   - 「沒有，直接開始研究」：呼叫 `submitClarification()` 時帶所有已選答案 + `allComprehensive = true`
   - 自由文字有值時：將值作為額外 query_modifier 附加到 clarified query

3. **注意**：現有 per-question 自訂輸入（「或自行輸入...」）是針對單一問題的。新增的是**跨問題的全局附加聚焦**，兩者不衝突。

### 難度：低

---

## Bug #5：暫不修改

文件明確指示：「暫不修改，待更多使用者回報」。跳過。

---

## Bug #7：LLM_KNOWLEDGE 紫色虛線標記太少

### 現狀發現

**觸發鏈完整**（5/5 環節已實作）：

```
Analyst prompt → gap_resolutions[resolution=llm_knowledge]
    → orchestrator.py:1336 建立 virtual_doc (urn:llm:knowledge:xxx)
    → source_urls 傳到前端
    → addCitationLinks() 渲染為紫色 AI 標記
```

**問題在 Analyst prompt 太窄**：

`analyst.py:734` `_build_gap_enrichment_instructions()` 將 `llm_knowledge` 限定為：
- 定義、原理（「什麼是 EUV」）
- 創辦人、歷史事實
- 科學/技術概念
- 公司靜態關係（「Google 母公司是 Alphabet」）

**安全紅線**（line 858-876）進一步限縮：時效性、具體數字、80% 以下把握的資訊都禁用 llm_knowledge。

**結果**：Analyst 撰寫分析報告時，大量使用 LLM 背景知識做推理連接、行業趨勢判斷、因果推論，但這些都**不會被標記為 `llm_knowledge`**，因為它們不是嚴格的「定義」或「歷史事實」。

### 修復方向

修改 `analyst.py:_build_gap_enrichment_instructions()` 的 prompt，擴展適用範圍：

**目前**：只標記「定義類」靜態知識
**建議增加**：
- 行業常識與趨勢判斷（「半導體產業受地緣政治影響」）
- 因果推理連接（「因為 X 所以 Y」，當 X→Y 的關係不在搜尋結果中）
- 補充背景（文章沒提到但 Analyst 用來連接上下文的知識）

### 風險

擴展太寬 → 報告中大量紫色標記 → 可讀性下降。需要找到平衡點。

### 涉及檔案

| 檔案 | 變更 |
|------|------|
| `code/python/reasoning/prompts/analyst.py` | `_build_gap_enrichment_instructions()` 擴展 llm_knowledge 適用範圍描述 |

### 難度：中（prompt engineering，需迭代測試效果）

---

## Bug #8：聚合型查詢無法處理（十大新聞）

### 現狀發現

- `decontextualize.py` 是**去語境化**模組（代詞展開），不做查詢分解
- `query_rewrite.py` 做 keyword simplification（≤3 詞），不做語意拆解
- 系統**沒有**聚合查詢識別或多子查詢分解機制

### 本質：功能限制

「列出 12 月十大新聞」需要：
1. 跨類別搜尋（政治、財經、社會、國際...）
2. 定義「十大」的標準（影響力？報導量？）
3. 排名彙總

### 可行方向（如決定實作）

**方案 A — 最小可行**：
- 偵測聚合型查詢（「十大」「排名」「列出 N 個」等 pattern）
- 誠實回覆系統限制，建議改用「12 月重要新聞事件」搜尋

**方案 B — 完整實作**：
- 新模組 `AggregateQueryDetector`
- 偵測到聚合查詢 → 拆為多個類別子查詢
- 並行搜尋 → 從結果中取每類別 top-1 → 組合為「N 大新聞」
- 需要 LLM 做類別拆解和最終排名

### 涉及檔案（方案 B）

| 檔案 | 變更 |
|------|------|
| `code/python/core/query_analysis/` | 新增 `aggregate_query_detector.py` |
| `code/python/core/baseHandler.py` | 加入 aggregate query 處理流程 |
| `code/python/core/retriever.py` | 支援多查詢並行搜尋 |

### 難度：高（新功能，方案 B 需跨多檔案）

---

## Bug #12：治安政策搜不到張文事件（Query Expansion）

### 現狀發現

**QueryRewrite 模組**（`query_rewrite.py`）：
- 使用 LLM 將複雜查詢拆為 ≤5 個 keyword queries
- Prompt（`prompts.xml:103-128`）為**產品搜尋**設計（例："vegetable plates"）
- 結果存在 `handler.rewritten_queries`

**關鍵問題**：
- `rewritten_queries` **僅被 `shopify_mcp.py` 使用**
- **主 retriever 流程不使用 `rewritten_queries`**
- Prompt 不適合新聞搜尋場景

### 修復方向

**Step 1 — 改造 QueryRewrite prompt**：
- 目標：生成 2-3 個語意擴展查詢（非 keyword simplification）
- 範例：「治安政策」→ ["社會安全政策", "犯罪防治措施", "刑案調查"]
- 使用 LLM（Dev 明確指示，非 hardcoded 規則）

**Step 2 — 讓 retriever 使用 rewritten_queries**：
- `retriever.py` 的 `search()` 需接受多查詢
- 並行搜尋所有 rewritten_queries → 合併去重結果
- 或：將 rewritten_queries 作為額外的 vector search queries

### 涉及檔案

| 檔案 | 變更 |
|------|------|
| `config/prompts.xml` | 重寫 `QueryRewrite` prompt（新聞導向 + 語意擴展） |
| `code/python/core/query_analysis/query_rewrite.py` | 可能需調整後處理邏輯 |
| `code/python/core/retriever.py` | 支援多查詢搜尋 |
| `code/python/core/baseHandler.py` | 將 rewritten_queries 傳入 retriever |

### 難度：中高

---

## Bug #14：回饋按鈕無實際功能

### 現狀發現

**前端**：
- 兩處 feedback buttons（`news-search.js:1074` 和 `1091`）：`👍 有幫助` / `👎 不準確`
- Click handler（line 3839-3851）：**僅 2 秒視覺動畫**，無 API 呼叫、無資料儲存

**後端**：無對應 API endpoint，無 feedback 資料表

### 修復方向

**前端**：
1. Click 👍/👎 → 彈出 modal（不是 alert）
2. Modal 內容：
   - 文字輸入區（`<textarea>`）
   - Placeholder：「感謝提供意見，有任何正面、負面體驗，或其他意見都歡迎回饋！」
   - 提交按鈕 + 關閉按鈕
3. 提交後：呼叫 `POST /api/feedback`

**後端**：
1. 新 API endpoint：`/api/feedback`
2. 新 DB table：

```sql
CREATE TABLE user_feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    query TEXT,
    answer_snippet TEXT,
    rating TEXT,          -- 'positive' or 'negative'
    comment TEXT,
    session_id TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

3. 支援 SQLite（本地）和 PostgreSQL（production）— 與現有 analytics 雙資料庫模式一致

### 涉及檔案

| 檔案 | 變更 |
|------|------|
| `static/news-search.js` | 新增 feedback modal HTML + JS 邏輯 |
| `static/news-search.css` | Modal 樣式 |
| `code/python/webserver/routes/api.py` | 新增 `/api/feedback` endpoint |
| `code/python/core/query_logger.py` | 新增 `log_feedback()` 方法 + DB table |

### 難度：中

---

## Bug #15：技術勞工股票查詢失敗

### 現狀發現

- Tier 6 API stock 路由邏輯正確（`analyst.py:768-781`）
- `stock_tw` 需要具體股票代碼（如 "2330"），`stock_global` 需要 ticker（如 "NVDA"）
- 查詢「技術勞工不被 AI 取代的產業」→ 無法對應任何股票代碼

### 問題本質

不是 API 路由 bug，而是**查詢太抽象**。需要先分解為具體公司/產業，才能查股價。

### 與 Bug #12 關聯

兩者本質相同 — 查詢理解/分解能力不足。Bug #12 的 LLM query expansion 如果實作，也能部分解決此問題。

### 可能的額外修復

在 Analyst prompt 中加入引導：當遇到抽象查詢時，先釐清用戶意圖（哪些產業？哪些公司？），而不是直接嘗試搜尋。

### 難度：高（依賴 Bug #12 的 query expansion）

---

## Bug #21：記者查詢跑不出結果

### 現狀發現

**已有的基礎設施**：
- `author_intent_detector.py` **已存在**（git untracked），實作了 regex-based 作者意圖偵測
- Qdrant payload 中**有 `author` 欄位**（`qdrant.py` 已 extract 和 store）
- `author_intent_detector.py` 定義了 6 個 regex pattern（中文 3 個 + 英文 3 個）

**缺失的關鍵環節**：
- **無 retriever-level payload filter 機制**（Phase 3 Bug #18-20 尚未完成）
- `author_intent_detector.py` 沒有被整合進 pre-check pipeline（`baseHandler.py` 沒有 import）
- 即使偵測到 author intent，也沒有辦法將 `author` filter 傳給 Qdrant

### 依賴鏈

```
Phase 3 Bug #18-20（通用 filter 架構）
    → retriever.search(filters=[{field: "author", ...}])
    → Qdrant FieldCondition payload filter
    → author_intent_detector 整合進 pipeline
    → Bug #21 解決
```

### 涉及檔案（Phase 3 完成後）

| 檔案 | 變更 |
|------|------|
| `code/python/core/baseHandler.py` | 整合 `AuthorIntentDetector` 進 pre-check |
| `code/python/core/retriever.py` | 接收 author filter 參數 |
| `code/python/retrieval_providers/qdrant.py` | 將 author filter 轉為 `FieldCondition` |

### 難度：中（但 blocked by Phase 3 #18-20）

---

## 建議執行順序

1. **Bug #4** — 低風險純前端，可獨立完成
2. **Bug #14** — 完整的前後端功能，但範圍明確
3. **Bug #7** — prompt 調整，需迭代測試
4. **Bug #12** — 核心 query expansion，影響面廣
5. **Bug #8** — 如決定實作方案 B，依賴 #12
6. **Bug #15** — 依賴 #12
7. **Bug #21** — blocked by Phase 3
