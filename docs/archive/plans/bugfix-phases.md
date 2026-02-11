# Bugfix Phases — 淨化版執行策略

> 基於 bug-fix-plan.md 中 5 個 Agent 的調查、爭議與最終裁決
> 建立日期：2026-01-29
> 用途：**指揮 Claude Code 分批執行 25 個 Bug 修復**

---

## 使用說明

每個 Bug 包含三個要素：

- **Implementation**：要做什麼（Agent 5 最終確認的正確做法）
- **Constraints**：絕對不要做什麼（Agent 們爭論後否決的方案）
- **Files**：涉及的檔案

每個 Phase 結束後，建議**開啟新對話**以重置 context。

---

## Phase 1：Prompt 修改 + 輕量前端修復（低風險，一次 PR）

> 檔案集中在 `generate_answer.py`、`writer.py`、`news-search.js`
> 預估改動量：文字插入為主，邏輯變動極小

### Bug #1：日期謊稱問題

**Implementation**：
- 檔案：`code/python/methods/generate_answer.py`
- 位置：`synthesize_free_conversation()` 方法（~line 631）
- 做法：在三個 prompt 變體（`has_research_report`、`has_cached_articles`、`else`）開頭加入當前日期
  ```python
  from datetime import datetime
  current_date = datetime.now().strftime("%Y-%m-%d")
  date_context = f"\n\n**今天的日期是：{current_date}**\n如果用戶詢問日期相關問題，請使用此日期，不要從搜尋結果中推測日期。\n"
  ```

**Constraints**：
- 不要從搜尋結果中推測日期，要用 `datetime.now()`

**驗證**：Free Conversation 模式問「今天幾月幾號？」，確認回答正確日期

---

### Bug #3：合理化錯誤答案

**Implementation**：
- 檔案：`code/python/methods/generate_answer.py`
- 位置：`synthesize_free_conversation()` 的三個 prompt 變體（與 Bug #1 同函數）
- 做法：加入系統元資訊
  ```
  **重要系統限制**：
  - 你只能存取資料庫中已收錄的新聞，不代表所有新聞。
  - **如果用戶問「為什麼只有某日期/某主題的新聞」，最可能的原因是資料庫收錄範圍有限。**
  - **絕對不要猜測或合理化新聞數量/日期分布的原因。**
  - 誠實回答：「這可能是因為資料庫收錄範圍的限制，建議調整搜尋條件或時間範圍重新搜尋。」
  ```

**Constraints**：
- 不要讓 LLM 猜測或編造資料庫限制以外的原因

---

### Bug #9：「無法存取即時新聞」的錯誤回覆

**Implementation**：
- 檔案：`code/python/methods/generate_answer.py`
- 位置：`synthesize_free_conversation()` 的三個 prompt 變體（與 Bug #1 同函數）
- 做法：加入系統能力說明
  ```
  **你的能力範圍**：
  - 你可以分析和討論已搜尋到的新聞文章
  - 你可以回答基於搜尋結果的問題
  - 如果用戶的問題超出目前搜尋結果的範圍，建議他們：修改搜尋關鍵字重新搜尋、調整時間範圍、或使用深度研究模式
  - 不要說「我無法存取即時新聞」，而是說「目前搜尋結果中沒有相關資訊，建議您重新搜尋 [具體建議]」
  ```

**Constraints**：
- 不要說「無法存取」，而是引導使用者重新搜尋

---

### Bug #24：回覆沒有排版換行

**Implementation**：
- 檔案：`code/python/methods/generate_answer.py`
- 位置：`synthesize_free_conversation()` 的三個 prompt 變體（與 Bug #1 同函數）
- 做法：加入 Markdown 格式要求
  ```
  請使用 Markdown 格式回答。段落之間用空行分隔，列表使用 - 或 1. 2. 3. 格式，重要概念可用 **粗體** 強調。
  ```

**Constraints**：
- **絕對不要在後端做 `\n` → `<br>` 替換**，這會與前端 `marked.parse()` 衝突
- 前端已用 `marked.parse()` 做 Markdown 渲染，問題在 prompt 沒要求格式

---

### Phase 1 整合說明：Bug #1 + #3 + #9 + #24

> 這四個 Bug 都修改 `synthesize_free_conversation()` 的 prompt。
> **必須一次性修改**，避免多次 PR 衝突。
> 讀取 `generate_answer.py`，找到三個 prompt 變體，在每個變體開頭/適當位置插入上述所有內容。

---

### Bug #10：Mac 輸入法 Enter 問題

**Implementation**：
- 檔案：`static/news-search.js`
- 位置：用 `searchInput.addEventListener('keydown'` 定位（**不要依賴行號**，已從 1218 偏移至 ~1235）
- 做法：加入 `!e.isComposing` 檢查
  ```javascript
  if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) {
  ```
- 搜尋和 Free Conversation 共用同一個 `searchInput`（5 輪 Agent 確認），修復一處即覆蓋所有模式

**Constraints**：
- 不要手動追蹤 `compositionstart`/`compositionend` event，直接用 `e.isComposing` 屬性（現代瀏覽器廣泛支援）
- 不需要找其他 keydown handler，搜尋和 FC 共用同一個 input
- Lines 4131/4451 的 rename input 也有同樣問題但低優先，Phase 1 不用修

**驗證**：Mac 上使用注音/倉頡輸入法，按 Enter 選字時不觸發搜尋

---

### Bug #13：引用連結 private:// 問題

**Implementation**：
- 檔案：`static/news-search.js`、`static/news-search.css`
- 位置：`addCitationLinks()` 函數，在 `urn:llm:knowledge:` 處理之後、一般 URL 處理之前
- 做法：加入 `private://` 處理
  ```javascript
  if (url.startsWith('private://')) {
      return `<span class="citation-private" title="私人文件來源">[${num}]<sup>📁</sup></span>`;
  }
  ```
- CSS：在 `news-search.css` 加入 `.citation-private` 樣式（類似 `.citation-urn`）

**Constraints**：
- 不要嘗試把 `private://` 轉成可點擊的連結，它本身就不是瀏覽器可導向的 URL
- 在 `urn:llm:knowledge:` 判斷之後、一般 URL `<a>` 連結之前插入

**驗證**：上傳私人文件 → 深度研究 → 確認私人文件引用顯示為不可點擊的特殊標記

---

### Bug #22：引用格式不通順

**Implementation**：
- 檔案：`code/python/reasoning/prompts/writer.py`
- 位置：`build_compose_prompt()` 方法的 f-string 中，line ~249（「Sources Used 限制」區段之後）
- 做法：加入引用語法風格指引
  ```
  ### 引用語法風格

  引用標記 [N] 應自然嵌入句子中，不要讓引用破壞閱讀流暢性。

  ✅ 正確範例：
  - 「台積電股價上漲 3%[1]。」
  - 「根據報導[1]，台積電股價上漲 3%。」
  - 「多項研究顯示[2][3]，AI 產業持續成長。」

  ❌ 錯誤範例（絕對禁止）：
  - 「根據報導，在[1]中提到，台積電股價上漲 3%。」
  - 「在[1]報導中，提到台積電股價上漲 3%。」
  - 「依據[1]所述的內容來看，...」

  原則：引用標記放在句末或緊跟在來源描述之後，不要拆開句子。
  ```

**Constraints**：
- **不要找 `_citation_rules()` 方法**，此方法不存在（5 輪 Agent 確認，3:2 裁決）
- 只存在設計文件 archive 中，實際 `writer.py` 沒有這個方法
- 正確位置是 `build_compose_prompt()` 的 f-string，在 Sources Used 限制（line ~249）之後插入
- 插入在「輸出要求」區段（line 249 附近），而不是「輸入資料」區段（line 198 附近），因為這是「如何寫引用」的輸出約束

**驗證**：深度研究任意主題，檢查引用格式是否自然

---

## Phase 2：前端架構修改（中高風險）

> 檔案集中在 `news-search.js`、`news-search.css`、`news-search-prototype.html`
> 涉及 JS 邏輯修改，需逐一驗證避免互相破壞

### Bug #17：知識圖譜收不起來（KG toggle 無效）

**Implementation**：
- 檔案：`static/news-search.js`、`static/news-search.css`、`static/news-search-prototype.html`
- 方案：**Wrapper 方案**（4:0 投票，5 輪共識）

1. **HTML 修改**：在 `kgDisplayContainer` 內部，`kg-display-header` 之後，加入 `<div id="kgContentWrapper">` 包裝以下 4 個元素：
   ```html
   <div id="kgContentWrapper">
       <div id="kgGraphView">...</div>
       <div id="kgDisplayContent">...</div>
       <div id="kgLegend">...</div>
       <div id="kgDisplayEmpty">...</div>  <!-- 計畫遺漏，Agent #2 發現 -->
   </div>
   ```
   **不包含** `kg-display-header`（header 裡有 toggle 按鈕，不能被隱藏）

2. **JS 修改**：`kgToggleButton` 的 click handler 改為操作 `kgContentWrapper`：
   ```javascript
   const wrapper = document.getElementById('kgContentWrapper');
   toggleButton.addEventListener('click', () => {
       const isCollapsed = wrapper.style.display === 'none';
       wrapper.style.display = isCollapsed ? '' : 'none';
       icon.textContent = isCollapsed ? '▼' : '▶';
       // 更新按鈕文字
   });
   ```

3. **CSS 清理**：移除 `.kg-display-content.collapsed { display: none; }` 規則（不再需要）

4. **JS 清理**：移除 toggle handler 中的 `classList.add/remove('collapsed')` 邏輯

**Constraints（關鍵 — Agent 爭議結果）**：
- **絕對不要隱藏 `kgDisplayContainer`**（Agent #1 的提案被否決，因為 container 包含 toggle 按鈕本身，隱藏 container 會同時隱藏按鈕，使用者無法重新展開）
- **不要用「遍歷子元素」方案**（Agent #3 的備選方案被否決，因為展開時需要追蹤 view mode 恢復各元素 display 值，邏輯太複雜）
- Wrapper 必須包含 `kgDisplayEmpty`（原計畫遺漏）
- 展開時 `wrapper.style.display = ''`（空字串），子元素自動恢復先前的 inline style 狀態

**問題全貌（理解後再動手）**：
1. Toggle handler 只操作 `kgDisplayContent` 的 `.collapsed` class
2. 圖形模式下：toggle 操作已 `display: none` 的 `kgDisplayContent`，`kgGraphView` 不受影響 → 無效
3. 列表模式下：view toggle 用 inline `style.display: block`，優先級高於 `.collapsed { display: none }` → 無效

**驗證**：圖形模式下按收起 → 整個 KG 隱藏；列表模式下按收起 → 整個 KG 隱藏；展開後恢復原狀

---

### Bug #23：暫停對話按鈕 + 防止重複發送

**Implementation**：
- 檔案：`static/news-search.js`

**Step 1 — 建立三個模式的 abort 基礎設施**：

| 模式 | 現狀 | 需要做的 |
|------|------|---------|
| **搜尋** | ✅ 已有 `cancelActiveSearch()`、`currentSearchAbortController`、`currentSearchEventSource`（模組級變數） | 直接復用 |
| **Deep Research** | ❌ EventSource 是局部 `const` 變數（~line 1530），無法外部 abort | 新增 `let currentDeepResearchEventSource = null`，將 line 1530 改為賦值給此變數 |
| **Free Conversation** | ❌ `handlePostStreamingRequest()` 的 `fetch()` 沒有 `signal` 參數 | 新增 `let currentFreeConvAbortController = null`，修改 `handlePostStreamingRequest()` 簽名加入 `abortSignal` 參數 |

**Step 2 — 統一 abort 函數**：
```javascript
function cancelAllActiveRequests() {
    cancelActiveSearch();  // 已有
    if (currentDeepResearchEventSource) {
        currentDeepResearchEventSource.close();
        currentDeepResearchEventSource = null;
    }
    if (currentFreeConvAbortController) {
        currentFreeConvAbortController.abort();
        currentFreeConvAbortController = null;
    }
}
```
在任何新操作開始前呼叫此函數。

**Step 3 — UI 狀態機**：
- **閒置狀態**：顯示搜尋/發送按鈕，Enter 可送出
- **處理中狀態**：隱藏搜尋/發送按鈕，顯示「停止生成」按鈕，禁用 Enter 送出
- **Abort**：點擊停止 → `cancelAllActiveRequests()` → 回到閒置狀態
- 適用範圍：搜尋、深度研究、Free Conversation 三個模式

**Step 4 — `handlePostStreamingRequest` 修改**：
```javascript
async function handlePostStreamingRequest(url, body, query, abortSignal = null) {
    const response = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Accept': 'text/event-stream' },
        body: JSON.stringify(body),
        signal: abortSignal  // 新增
    });
    // abort 時 reader.read() 會自動 throw AbortError，不需額外呼叫 reader.cancel()
}
```

**Constraints**：
- **不要說「將 EventSource 和 AbortController 存為模組級變數」**，搜尋模式的已經是了，只有 DR 和 FC 需要新增
- 不要忽略跨模式 abort：DR 正在跑 → 用戶點搜尋 → 舊的 `cancelActiveSearch()` 不會取消 DR EventSource
- 加入 `signal` 給 fetch 後，abort 時 `response.body` 被 cancel，`reader.read()` 自動 throw `AbortError`，這是 Fetch API + ReadableStream 的標準行為

---

### Bug #25：引用數字太大沒有超連結

**Implementation（三管齊下，優先順序 C > B > A）**：

**Plan C — 前端降級顯示（唯一用戶可見的修復，最高優先）**：
- 檔案：`static/news-search.js`
- 位置：`addCitationLinks()` 函數，~line 1618 的 `return match`
- 做法：當 `index >= sources.length` 或 `url` 為空時，不是返回原文 `[20]`，而是顯示帶 tooltip 的特殊標記
  ```javascript
  return `<span class="citation-no-link" title="來源暫無連結">[${num}]</span>`;
  ```

**Plan B — Writer prompt 強化**：
- 檔案：`code/python/reasoning/prompts/writer.py`
- 位置：`build_compose_prompt()` 的 sources_used 限制區段（~line 247）
- 做法：加入更強的數字範圍約束：「你的 sources_used 中每個 ID 不得超過 {max(analyst_citations)}」

**Plan A — 後端 source_urls 擴展（診斷用）**：
- 檔案：`code/python/reasoning/orchestrator.py`
- 位置：~line 1115
- 做法：將 `max_cid` 改為覆蓋 Writer 實際使用的所有 citation ID
  ```python
  max_cid = max(
      max(self.source_map.keys(), default=0),
      max(final_report.sources_used, default=0)
  )
  ```

**Constraints（關鍵 — Agent #4 的發現）**：
- **Plan A 單獨實施對用戶端完全沒有可見效果**（5 輪確認）
  - 不做 A：`index >= sources.length` → `return match` → 純文字 `[15]`
  - 做了 A 不做 C：`sources[14] = ""` → `if (url)` falsy → `return match` → 純文字 `[15]`
  - 兩條路徑結果完全相同。Plan A 唯一價值是後端 logging
- **必須實作 Plan C 才能改變用戶體驗**

---

## Phase 3：後端架構修改（高複雜度）

> 涉及 retriever 抽象層、時間解析器等核心模組
> 需要先理解架構再修改

### Bug #6：時間範圍計算錯誤（中文數字 + prefix 不一致）

**Implementation**：
- 檔案：`code/python/core/query_analysis/time_range_extractor.py`

**修改 1 — 中文數字映射**（新增 helper function）：
```python
CHINESE_NUMBERS = {
    '一': 1, '二': 2, '兩': 2, '三': 3, '四': 4, '五': 5,
    '六': 6, '七': 7, '八': 8, '九': 9, '十': 10
}

def parse_number(s):
    """解析阿拉伯數字或中文數字（含組合）"""
    if s.isdigit():
        return int(s)
    if s in CHINESE_NUMBERS:
        return CHINESE_NUMBERS[s]
    # 組合數字：十五=15, 二十=20, 二十五=25
    if '十' in s:
        parts = s.split('十')
        tens = CHINESE_NUMBERS.get(parts[0], 1) if parts[0] else 1
        ones = CHINESE_NUMBERS.get(parts[1], 0) if len(parts) > 1 and parts[1] else 0
        return tens * 10 + ones
    return int(s)  # fallback
```

**修改 2 — 更新所有 8 個 `_zh` regex**：
- 將 `(\d+)` 改為 `([一二兩三四五六七八九十\d]+)`

**修改 3 — 統一 prefix（語意分組，4:1 投票決定）**：
- `past_*_zh` 系列 → `(?:過去|近)` — 「過去」和「近」都可匹配
- `last_*_zh` 系列 → `(?:最近|近)` — 「最近」和「近」都可匹配

| Pattern | 現有 prefix | 修改後 |
|---------|------------|--------|
| `past_x_days_zh` | `過去` | `(?:過去\|近)` |
| `last_x_days_zh` | `最近` | `(?:最近\|近)` |
| `past_x_weeks_zh` | `過去` | `(?:過去\|近)` |
| `last_x_weeks_zh` | `最近` | `(?:最近\|近)` |
| `past_x_months_zh` | `過去` | `(?:過去\|近)` |
| `last_x_months_zh` | `(?:近\|最近)` ✅ | 不變 |
| `past_x_years_zh` | `過去` | `(?:過去\|近)` |
| `last_x_years_zh` | `(?:近\|最近)` ✅ | 不變 |

**修改 4 — 更新解析邏輯**：
- 將 lines 196/202/209/217 的 `int(match.group(1))` 改為 `parse_number(match.group(1))`

**Constraints**：
- **不要用 `cn2an` 外部套件**，`split('十')` 的輕量實作已足夠覆蓋新聞搜尋的實際需求（1-30天、1-12週、1-24月、1-10年）
- **不要把所有 prefix 統一為 `(?:近|最近|過去)`**（Agent #1 提案被否決，4:1），會導致 `past_*` 和 `last_*` 重複匹配同一表述
- 保持語意分組：`past_` = 確定的過去，`last_` = 最近/近期

**驗證**：「近兩年」→730天、「過去三個月」→90天、「最近五天」→5天、「近 2 年」→730天、「近三天」→3天

---

### Bug #11 + #16：時間過濾缺失（retriever 架構層級）

**Implementation**：
- 主要檔案：`code/python/core/retriever.py`、`code/python/core/baseHandler.py`
- 相關檔案：`code/python/core/query_analysis/time_range_extractor.py`

**Step 1 — 理解現狀**：
- `retriever.py:search()` 完全沒有時間過濾機制（5 輪確認）
- `time_range_extractor.py` 能正確解析時間範圍，結果存在 `handler.temporal_range`
- Reasoning module 的 temporal search 只是 prompt-level 約束（`analyst.py:47-50` 注入 `"Time Range: X to Y"` 文字），不是 retriever-level filter

**Step 2 — 在 retriever 加入通用 filter 參數**：
```python
async def search(self, query, site, num_results=50, endpoint_name=None, filters=None, **kwargs):
    # filters = [{"field": "datePublished", "operator": "gte", "value": "2026-01-01"}, ...]
```
各 provider 自行轉換為對應的 filter 格式（Qdrant → `FieldCondition`, Azure → OData filter 等）

**Step 3 — 資料流**：
`baseHandler.py` 取得 `handler.temporal_range` → 轉為通用 filter dict → 傳給 `retriever.search(filters=...)`

**Step 4 — Fallback 機制**：
嚴格時間過濾結果為 0 時，自動擴大範圍或移除 filter，並設 `time_filter_relaxed = True` flag

**Step 5 — 前端紅字提示**：
根據 flag 在搜尋結果上方顯示紅色提示：「系統找不到完全符合日期需求的資料，已擴大搜尋範圍」

**Constraints**：
- **不要直接在 `retriever.py` 中加入 Qdrant-specific 的 `FieldCondition`**，會破壞多後端抽象。用通用 filter 格式，各 provider 轉換
- **不要以為 reasoning module 的 temporal search 是 retriever-level filter**，它只是 prompt 文字注入（5:0 共識）
- Dev 說的「複用 reasoning temporal search」應理解為：複用 `time_range_extractor.py` 的解析結果，但 retriever filter 是全新實作

---

### Bug #18-20：記者文章搜尋問題

**Implementation**：
- 與 Bug #11/#16 使用相同的通用 filter 架構
- 在 `core/query_analysis/` 加入「作者搜尋」意圖識別
- 在 retriever filter 中加入 `author` 欄位的 payload filter
- 提供時間排序選項

**Constraints**：
- 與 Bug #11/#16 面臨相同的 retriever 抽象層問題，應一併設計通用 payload filter，不要分別處理 time 和 author
- 先確認 Qdrant collection 中 payload 是否有 `author` 欄位及其格式

**依賴**：需要 Bug #11/#16 的通用 filter 架構先完成

---

## Phase 4：功能完善

### Bug #2：Free Conversation 釘選文章擴展

**Implementation**：
- 檔案：`static/news-search.js`（前端）、`code/python/methods/generate_answer.py`（後端）

**Step 1 — 擴展釘選資料結構**：
```javascript
function togglePinNewsCard(url, title, description) {
    pinnedNewsCards.push({ url, title, description, pinnedAt: Date.now() });
}
```
呼叫方需傳入 description（從 news card 的 `schema.description` 取得）

**Step 2 — 修改 POST 協議**：
```javascript
if (pinnedNewsCards.length > 0) {
    requestBody.pinned_articles = pinnedNewsCards.map(p => ({
        url: p.url, title: p.title, description: p.description || ''
    }));
}
```

**Step 3 — 後端 context 注入**：
`synthesize_free_conversation()` 從 request 讀取 `pinned_articles`，注入 prompt

**Step 4 — 前端 placeholder**：
Free Conversation 輸入框加入灰色 placeholder：「研究助理會參考摘要內容及您釘選的文章來回答」

**Constraints**：
- `pinnedNewsCards` 也存在 localStorage（~lines 457, 472），擴展資料結構時需同步更新 localStorage 讀寫邏輯
- 舊格式 session 的向後兼容性：`description` 欄位可能不存在，讀取時用 `p.description || ''`
- 呼叫 `togglePinNewsCard()` 的地方（~line 2836）也需要傳入 description 參數

---

## Phase 5：需要調查後才能修復

> 這些 Bug 需要先深入調查，不能直接寫程式碼

### Bug #4 + #5：深度研究歧義檢測不完整

**方向**：
- Bug #4：前端 Clarification 選項列表最後加入「有沒有其他你想更具體聚焦的內容？」（附自由文字輸入）和「沒有，直接開始研究」按鈕
- Bug #5：暫不修改，待更多使用者回報

**需要調查**：確認 clarification 選項的渲染邏輯在 `news-search.js` 的哪個函數中

---

### Bug #7：缺少紫色虛線標記 AI 知識

**方向**：
- 調查 `reasoning/prompts/analyst.py` 中 `GapResolutionType.LLM_KNOWLEDGE` 的觸發條件
- 放寬觸發條件：如果 claim 無法直接從搜尋結果找到支持（即使是「常識」），也應標記為 `LLM_KNOWLEDGE`

**需要調查**：完整的 gap analysis 流程，`orchestrator.py:1331-1350` 的觸發邏輯

---

### Bug #8：沒有真的列出 12 月十大新聞

**方向**：
- 調查 Decontextualization 的目前實作（`core/query_analysis/`）
- 判斷是否可加入「聚合型查詢」的識別和處理

**本質**：功能限制（語意搜尋引擎，無聚合統計能力）

---

### Bug #12：治安政策沒找到張文事件

**方向**：
- 在 Query Decomposition 階段加入 LLM-based query expansion
- 讓 LLM 生成 2-3 個相關的擴展查詢

**Constraints**：
- **使用 LLM（而非 hardcoded 規則）** 確保可擴展性（Dev 明確指示用第二個 Agent 建議）

---

### Bug #14：摘要回饋按鈕

**方向**：
- 點擊 👍/👎 後彈出小對話框（modal），包含文字輸入區和提交/關閉按鈕
- Placeholder：「感謝提供意見，有任何正面、負面體驗，或其他意見都歡迎回饋！」
- 存到資料庫（SQLite/PostgreSQL）或 Google Sheet

**需要**：啟動 /plan 進行完整設計

---

### Bug #15：技術勞工股票查詢失敗

**方向**：
- 調查 Tier 6 API 的 stock 查詢 prompt
- 調查 Analyst agent 在此查詢中的決策過程

**需要調查**：`reasoning/prompts/analyst.py` 中的 Tier 6 API 呼叫判斷邏輯

---

### Bug #21：深度研究記者查詢跑不出結果

**方向**：
- 用 author filter 搜尋該記者的所有文章
- 從結果中提取：服務媒體、撰寫主題領域、活躍時間範圍、代表作品

**依賴**：Bug #18-20 的 author filter 功能先完成

---

## 跨 Phase 整合提醒

### 整合 1：Free Conversation Prompt 全面升級（Phase 1）
Bug #1 + #3 + #9 + #24 都修改 `synthesize_free_conversation()`，**必須一次性修改**。

### 整合 2：Retriever 通用 Filter 架構（Phase 3）
Bug #11/#16（time filter）+ Bug #18-20（author filter）共用同一個通用 filter 機制。
**注意：Bug #17 不屬於此整合**（5 輪 Agent 一致確認，Bug #17 是前端 KG toggle 問題）。

### 整合 3：前端輸入體驗（Phase 1 + Phase 2）
Bug #10（IME）+ Bug #23（abort）+ Bug #13（private://）+ Bug #17（KG toggle）+ Bug #2 前端部分。

---

## 五輪 Agent 共識速查表

| Bug | 方案 | 票數 | 關鍵否決 |
|-----|------|------|---------|
| #17 方案 | Wrapper | 4:0 | 不要隱藏 container（會同時隱藏 toggle 按鈕） |
| #6 prefix | 語意分組 | 4:1 | 不要全部統一（會重複匹配） |
| #22 分類 | 需補充 | 3:2 | 不要找 `_citation_rules()`（不存在） |
| #25 優先順序 | C > B > A | 5:0 | Plan A 單獨實施對用戶端零效果 |
| #11/#16 實作 | 全新 retriever filter | 5:0 | Reasoning 的 temporal search 只是 prompt 文字 |
| #23 統一 abort | `cancelAllActiveRequests()` | 5:0 | 搜尋已有 abort，DR 和 FC 完全沒有 |

---

*建立日期：2026-01-29*
*來源：docs/bug-fix-plan.md（5 Agent 驗證報告提煉）*
