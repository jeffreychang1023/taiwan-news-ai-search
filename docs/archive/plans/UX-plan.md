# UX 效能優化計劃：Search Mode SSE 統一

> 最終決策文件。濃縮自 7 個 Agent 的獨立審查結論。

---

## 問題

前端 Search Mode 使用兩次 sequential HTTP request：

```
Call 1: GET /ask?generate_mode=summarize&streaming=false  → JSON blob (articles + summary)
Call 2: GET /ask?generate_mode=generate&streaming=true    → SSE (AI answer)
Total perceived latency: ~12s (8s + 4s sequential)
```

## 方案

新增 `unified` mode — 單次 SSE call，依序送出 articles → summary → answer。

- **不修改**現有 summarize / generate mode（新增獨立分支）
- 前端複用已存在的 `handlePostStreamingRequest()`（fetch + ReadableStream）
- 預估感知延遲：~10s（Phase 1-2），~6-8s（Phase 4 progressive rendering）

---

## 驗證矩陣

以下為實作前必須處理的已驗證技術約束：

### 資料格式

| SSE event | 後端送出格式 | 前端期望格式 | 需要轉換？ |
|-----------|-------------|-------------|-----------|
| articles | `message_type: "result"`, `content: [...]` | `combinedData.content: [...]` | 是 — unified mode 改用 `message_type: "articles"` |
| summary | `message_type: "result"`, `@type: "Summary"`, `content: "text"` | `combinedData.summary.message: "text"` | 是 — 前端需 `{ message: data.content }` 轉換 |
| answer | `message_type: "nlws"`, `answer: "text"`, `items: [...]` | `combinedData.nlws.answer: "text"` | 是 — unified mode 改用 `message_type: "answer"` |

### 函數行為

| 函數 | 關鍵行為 | 影響 |
|------|---------|------|
| `populateResultsFromAPI()` (js:1103) | **每次呼叫清空 DOM**（`innerHTML = ''`） | 不能分階段重複呼叫，Phase 1-2 需在 `complete` 時一次渲染 |
| `synthesizeAnswer()` (py:838+879) | **送出 TWO 個 `nlws` message**（初始 answer → enriched answer with descriptions） | 前端 `case 'answer'` 必須 idempotent 覆蓋式更新 |
| `GenerateAnswer.runQuery()` (py:48) | **完全覆寫** baseHandler.runQuery()，有獨立 analytics lifecycle | 不能呼叫 runQuery()，只能呼叫 synthesizeAnswer() |

### 生命週期（Unified Mode SSE 序列）

```
NLWebHandler.runQuery():
  → begin-nlweb-response (含 query_id, conversation_id)
  → articles (ranking 完成後 batch 送出)
  → summary (PostRanking 完成後)
  [skip end-nlweb-response — 由 api.py 控制]

GenerateAnswer.synthesizeAnswer():
  → answer #1 (初始 answer, 無 item descriptions)
  → answer #2 (enriched answer, 含 item descriptions) [2-4s 後]

api.py:
  → end-nlweb-response
  → complete
```

### 並發與順序

| 訊息 | 送出方式 | 亂序風險 |
|------|---------|---------|
| articles | `asyncio.create_task` (fire-and-forget) | 有，但 `write_stream` 內建 `sleep(0)` yield |
| summary | `asyncio.create_task` (fire-and-forget) | 有，同上 |
| answer | `await self.send_message()` (同步等待) | 無 |

**安全措施**：在 runQuery() 返回後、synthesis 開始前插入 `await asyncio.sleep(0)`。

### 錯誤降級

| 失敗點 | 已送出的資料 | 處理方式 |
|--------|-------------|---------|
| Retrieval/Ranking 失敗 | 無 | SSE error event → 前端顯示錯誤 |
| PostRanking 失敗 | articles 已送出 | articles 仍渲染，summary 為空 |
| Synthesis 失敗 | articles + summary 已送出 | 送出 error event，前端顯示「AI 回答生成失敗」 |
| Description enrichment 超時 | answer #1 已送出 | answer #1 保持顯示，跳過 enrichment |

### 其他已驗證約束

| 項目 | 結論 |
|------|------|
| **Early send** | Phase 1 禁用（`generate_mode == 'unified'` 時跳過），避免前端收到重複文章 |
| **Cache 寫入** | 保留不變（`baseHandler.py:280-288`），提供 fallback 安全網 |
| **150ms sleep** | `log_query_start` 是同步寫入 + FK retry 機制已足夠，可降至 `sleep(0)` 或移除 |
| **Request cancel** | 前端 AbortController 已支援；後端在 synthesis 前加 `connection_alive_event` check |
| **Total timeout** | 單一 SSE 連線 12-19s，低於 proxy idle timeout (60-120s)，非 blocking issue |
| **EventSource URL 長度** | 改用 `handlePostStreamingRequest`（POST body）自動解決，非新增問題 |
| **`deep_research_handler` 雙重 begin** | 不複製此 pattern，讓 `runQuery()` 自然送出 begin |

---

## 後端實作（Phase 1）

**檔案**：`api.py`、`baseHandler.py`

```python
# api.py — handle_streaming_ask() 新增分支
elif generate_mode == 'unified':
    from core.baseHandler import NLWebHandler
    handler = NLWebHandler(query_params, wrapper)
    handler.skip_end_response = True          # 由 api.py 控制 end 時機
    await handler.runQuery()                  # retrieval + ranking + PostRanking

    await asyncio.sleep(0)                    # flush pending create_tasks

    # Check connection before synthesis
    if not handler.connection_alive_event.is_set():
        logger.info("Client disconnected before synthesis, skipping")
    else:
        # 建立 GenerateAnswer，注入狀態，只呼叫 synthesizeAnswer
        gen_handler = GenerateAnswer(query_params, wrapper)
        gen_handler.final_ranked_answers = handler.final_ranked_answers
        gen_handler.items = [
            [r['url'], json.dumps(r.get('schema_object', {})), r['name'], r['site']]
            for r in handler.final_ranked_answers
        ]
        gen_handler.decontextualized_query = handler.decontextualized_query
        gen_handler.conversation_id = handler.conversation_id
        gen_handler.connection_alive_event = handler.connection_alive_event
        await gen_handler.synthesizeAnswer()

    # 手動送出 end
    await handler.message_sender.send_end_response()
```

```python
# baseHandler.py:296 — 加入 skip 判斷
if not getattr(self, 'skip_end_response', False):
    await self.message_sender.send_end_response()
```

**額外修改**：
- `ranking.py:172` — unified mode 禁用 early send
- `ranking.py:301` / `post_ranking.py:112` — unified mode 使用新 message_type（`articles` / `summary`）
- 或：保持後端不變，前端做 message_type mapping（更低風險）

**驗證**：`curl` 測試 SSE 訊息序列：begin → articles → summary → answer #1 → answer #2 → end → complete

---

## 前端實作（Phase 2）

**檔案**：`news-search.js`

`performSearch()` 改為：
```js
// 取代 Call 1 + Call 2，改用單次 POST SSE
const body = {
    query, site: getSelectedSitesParam(),
    generate_mode: 'unified', streaming: 'true',
    session_id: currentSessionId,
    prev: prevQueriesForThisTurn
};
const unifiedData = await handlePostStreamingRequest('/ask', body, query, currentSearchAbortController.signal);
```

`handlePostStreamingRequest()` 新增 case 分支：
```js
case 'articles':       // ranking 結果
    accumulatedArticles = data.content || [];
    break;
case 'summary':        // PostRanking 摘要
    accumulatedSummary = { message: data.content };  // 格式轉換
    break;
case 'answer':         // AI answer（會收到兩次：初始 + enriched）
    accumulatedAnswer = data;
    break;
case 'end-nlweb-response':
    break;             // 明確忽略
case 'complete':
    // 組裝 combinedData → 一次渲染（避開 destructive DOM clearing）
    const combinedData = {
        content: accumulatedArticles,
        nlws: accumulatedAnswer?.answer ? { answer: accumulatedAnswer.answer } : null,
        summary: accumulatedSummary
    };
    return combinedData;
```

`complete` 後的邏輯（sessionHistory / conversationHistory / saveCurrentSession）保持不變。

**驗證**：端對端完整搜尋流程，確認 UI 正確顯示 articles + summary + AI answer

---

## Phase 3-5（後續）

| Phase | 內容 | 觸發條件 |
|-------|------|---------|
| **3. Loading UX** | Skeleton cards + typing indicator + fade-in | Phase 2 完成後 |
| **4. Progressive rendering** | 拆分 `populateResultsFromAPI()` 為獨立渲染函數，articles 到達即渲染 | Phase 2 效果不足（感知延遲 >8s） |
| **5. 微優化** | 150ms sleep 移除 + description enrichment timeout guard | 低優先 |

---

## 技術驗證結果

> 驗證日期：2026-01-30。基於原始碼逐項比對計劃內容。

### 驗證總覽

**發現 4 個問題，其中 1 個 blocking、3 個 non-blocking。**

### 完整驗證表

| 項目 | 結果 | 問題描述 | 程式碼位置 |
|------|------|---------|-----------|
| A.1 資料流：SSE message_type 對應 | 通過 | 所有 message_type 均有後端送出位置 | — |
| A.2 資料流：欄位名一致性 | **BLOCKING** | 見下方 Issue #1 | `generate_answer.py:838`, `UX-plan.md:140-141` |
| A.3 資料流：combinedData 消費 | 通過 | `{content, nlws.answer, summary.message}` 與 `populateResultsFromAPI()` 消費路徑一致 | `news-search.js:1056-1130` |
| B.1 函數契約：前置條件 | 通過 | `synthesizeAnswer()` 所需屬性均由注入或 `__init__` 提供 | `generate_answer.py:771-880` |
| B.2 函數契約：副作用 | 通過 | SSE 寫入和 description tasks 均為預期行為 | — |
| B.3 函數契約：__init__ 效果 | non-blocking | 見下方 Issue #2 | `baseHandler.py:111-114, 158-159` |
| C.1 生命週期：begin 唯一性 | 通過 | 第二個 handler 直接呼叫 `synthesizeAnswer()`，跳過 `send_begin_response()` | `generate_answer.py:204-207` |
| C.2 生命週期：end 在資料之後 | 通過 | `skip_end_response` 旗標正確延遲 end 到 synthesis 完成後 | `baseHandler.py:296` |
| C.3 生命週期：complete 最後 | 通過 | unified 分支結束後落入 api.py:102 送出 complete | `api.py:102` |
| C.4 生命週期：create_task flush | 通過 | `sleep(0)` + `runQuery()` 內部大量 await 點，風險極低 | `UX-plan.md:110` |
| D.1 錯誤路徑：已送出資料安全 | 通過 | SSE 單向流，已送出資料不可回收 | — |
| D.2 錯誤路徑：前端不 hang | 通過 | `reader.read()` 返回 `done:true` 時 Promise resolve | `news-search.js:792-794` |
| D.3 錯誤路徑：無 Silent Fail | 通過 | api.py 外層 try/except 捕獲並送出 error response | `api.py:104-106` |
| E.1 狀態：注入屬性完整性 | non-blocking | 見下方 Issue #3 | `generate_answer.py:182`, `UX-plan.md:118-125` |
| E.2 狀態：conversation_id 一致 | 通過 | 計劃第124行顯式同步 | `UX-plan.md:124` |
| E.3 狀態：analytics 不重複 | non-blocking | 見下方 Issue #4 | `baseHandler.py:299-317` |
| E.4 狀態：cache 行為 | 通過 | 第一個 handler cache，第二個不觸碰 | `baseHandler.py:280-288` |
| F.1 並發：fire-and-forget flush | 通過 | 同 C.4 | — |
| F.2 並發：訊息順序 | 通過 | asyncio 單線程 + `_send_lock` 保護 | `baseHandler.py:149` |
| F.3 並發：cancel 處理 | 通過 | 共享 `connection_alive_event`，synthesis 前後均檢查 | `ranking.py:178` |
| G.1 相容：summarize mode | 通過 | 新增 elif 分支，不修改原 else 分支 | `api.py:95-99` |
| G.2 相容：generate mode | 通過 | generate 分支不變 | `api.py:87-89` |
| G.3 相容：deep_research mode | 通過 | deep_research 分支和獨立 endpoint 均不變 | `api.py:90-94, 290` |
| G.4 相容：handleStreamingRequest | 通過 | EventSource 版函數完全不修改 | `news-search.js:688-767` |

### Issue #1 — BLOCKING：`message_type` 映射策略不完整

**問題**：計劃驗證矩陣（第37行）正確識別了三組 message_type 轉換需求：

| 原始 type | 目標 type | 計劃是否涵蓋實作方式？ |
|-----------|-----------|----------------------|
| `result`（文章） | `articles` | 提及但未決定（後端改 or 前端 mapping） |
| `result`（摘要） | `summary` | 提及但未決定（同上） |
| `nlws`（答案） | `answer` | **完全遺漏** |

前端已寫好 `case 'answer':`（第171行），但後端 `synthesizeAnswer()` 仍送出 `message_type: "nlws"`（`generate_answer.py:838`）。「額外修改」段（第138-141行）只提到 `ranking.py` / `post_ranking.py` 的轉換，未提及 `generate_answer.py` 的 `nlws` → `answer`。

**修復方向**：在「額外修改」段明確加入 `generate_answer.py:838,878` 的條件分支，或在前端 `handlePostStreamingRequest()` 加入 `case 'nlws':` 作為 mapping。二擇一需明確決策。

### Issue #2 — non-blocking：第二個 handler 的 initial_user_message 使用臨時 conversation_id

**問題**：`GenerateAnswer(query_params, wrapper)` 調用 `NLWebHandler.__init__()` → `_init_conversation()` 自動生成新 `conversation_id`（`baseHandler.py:113-114`），`_init_messaging()` 隨即用此臨時 ID 建立 `initial_user_message`（`baseHandler.py:158-159`）。計劃第124行隨後覆寫了 `conversation_id`，但 `self.messages[0]` 已記錄了錯誤的 ID。

**影響**：僅影響 `self.messages` 內部列表，不影響 SSE 輸出。若未來有邏輯讀取 `gen_handler.messages[0].conversation_id`，會取到錯誤值。

**修復方向**：確保 `query_params` 中包含正確的 `conversation_id`（從第一個 handler 取得後寫入），使 `__init__` 自然繼承。

### Issue #3 — non-blocking：第二個 handler 缺少 `query_id`

**問題**：`query_id` 僅在 `get_ranked_answers()`（`generate_answer.py:182`）或 `NLWebHandler.runQuery()`（`baseHandler.py:242`）中設定。計劃直接呼叫 `synthesizeAnswer()`，跳過了這兩個入口。`gen_handler` 沒有 `query_id` 屬性。

**影響**：若 `send_message()` 鏈路中有程式碼讀取 `self.query_id`，會拋出 `AttributeError`。目前 `synthesizeAnswer()` 本身未直接使用，但 analytics 追蹤路徑可能需要。

**修復方向**：在計劃第118-125行的注入列表中加入 `gen_handler.query_id = handler.query_id`。

### Issue #4 — non-blocking：Analytics 延遲不含 synthesis 時間

**問題**：第一個 handler 的 `log_query_complete()`（`baseHandler.py:307-317`）在 `runQuery()` 返回時觸發，此時 synthesis 尚未開始。記錄的 `total_latency_ms` 不包含 synthesis 時間（約 2-6 秒）。

**影響**：Unified mode 的 analytics 延遲數據系統性偏低，無法反映用戶真實等待時間。

**修復方向**：在 api.py 的 unified 分支末尾（send_end_response 之後）補記一筆包含完整延遲的 analytics log，或將 `log_query_complete` 移到 api.py 層級統一控制。
