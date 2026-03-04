# NLWeb 全專案 Code Review 報告

**審查範圍**：251 個 Python 檔案，涵蓋 5 個模組
**審查日期**：2026-02-23
**發現總數**：83 項（7 CRITICAL、17 HIGH、35 MEDIUM、24 LOW）

---

## 修復狀態（2026-02-23 執行）

**修復範圍**：21 個檔案、~50 項修復
**語法驗證**：20/20 通過（19 Python + 1 JS）

### Phase 1 修復狀態

| # | ID | 狀態 | 備註 |
|---|-----|:----:|------|
| 1 | SEC-1 + SEC-9 | **延後** | JWT 尚未設定，等登入系統完成 |
| 2 | SEC-2 | **已修** | CORS origin 白名單（localhost + *.onrender.com + CORS_ALLOWED_ORIGINS env） |
| 3 | SEC-10 | **已修** | DOMPurify CDN + 4 處 innerHTML sanitize |
| 4 | SEC-5 + RSN-1 | **已修** | citation 驗證 ⊆ source_map + 空 draft 攔截 |
| 5 | ENG-1 | **已修** | save 失敗回傳 FETCH_ERROR |
| 6 | IDX-4 | **已修** | resumable mode 加 flush + checkpoint 不前進 on flush failure |
| 7 | SEC-3 | **已修** | table/column 白名單驗證 |
| 8 | IDX-1 | **已修** | finally: client.close() |
| 9 | RNK-3 | **已修** | dict/object 雙模式支援 |

### Phase 2 修復狀態

| # | ID | 狀態 | 備註 |
|---|-----|:----:|------|
| 1 | ENG-6 | **無需修** | Agent 調查後發現 TimeoutError 已正確處理（回傳 FETCH_ERROR） |
| 2 | ENG-7 | **已修** | parse exception → FETCH_ERROR，不計入 blocked |
| 3 | IDX-7 | **已修** | INSERT ON CONFLICT DO UPDATE 原子操作 |
| 4 | SEC-6 | **延後** | 獨立架構重構任務（Lossless Agent Isolation） |
| 5 | IDX-6 | **已修** | RLock 保護所有 SQL 操作 |
| 6 | RSN-7 | **已修** | response = None 初始化 |
| 7 | ENG-4 | **已修** | 移除 _process_article 的 failed 計數 |
| 8 | RNK-10 | **已修** | name = "unknown" 初始化 |
| 9 | IDX-3 | **已修** | 原子寫入 temp+os.replace + asyncio Lock |
| 10 | RSN-4 | **已修** | CoV 失敗 → verification_status:"unverified" + verification_message |
| 11 | RSN-2 | **已修** | inner timeout = self.timeout - 10 |
| 12 | RSN-3 | **不修** | 保留取消機制設計 |
| 13 | RNK-4 | **已修** | gather return values → sequential append |
| 14 | IDX-8+9 | **已修** | list → set + discard + snapshot broadcast |
| 15 | IDX-10 | **已修** | buffer swap pattern |

### Phase 3 修復狀態

| # | ID | 狀態 | 備註 |
|---|-----|:----:|------|
| 1 | RNK-2 | **已修** | 預計算 similarity matrix（numpy 矩陣乘法） |
| 2 | RNK-12 | **已修** | 移除讀操作 lock，保留寫操作 lock |
| 3 | ENG-9 | **已修** | crawled_ids set → SQLite registry.is_crawled() |
| 4 | IDX-5 | **已修** | exponential backoff retry（3 attempts） |

### Phase 4 修復狀態

| # | ID | 狀態 | 備註 |
|---|-----|:----:|------|
| 1 | ENG-5 | **已修** | get_event_loop → get_running_loop（3 處） |
| 2 | ENG-8+17 | **已修** | _process_url 加 _ensure_date |
| 3 | ENG-10 | **已修** | close() 清理 FileHandler |
| 4 | ENG-11 | **已修** | Big5 fallback encoding |
| 5 | ENG-12 | **已修** | engine.close() try/except 包住 |
| 6 | IDX-11 | **已修** | 只保留最近 50 筆完成任務 |
| 7 | IDX-12 | **已修** | subprocess 失敗時 close stderr file |
| 8 | IDX-13 | **已修** | flush 後 truncate buffer.jsonl |
| 9 | IDX-14 | **已修** | checkpoint 記錄 line_num + 1 |
| 10 | IDX-15 | **已修** | 精確 LIKE pattern（boundary-aware） |
| 11 | IDX-16 | **已修** | close() 前 flush _nf_buffer |
| 12 | IDX-17 | **已修** | len(embeddings) != len(texts) 檢查 |
| 13 | IDX-21 | **已修** | docstring 修正 |
| 14 | SEC-13 | **已修** | OAuth state TTL 600s |
| 15 | SEC-18 | **延後** | 併入 SEC-1 |
| 16 | SEC-19 | **延後** | 併入 SEC-1 |
| 17 | SEC-20 | **已修** | urllib.parse.urlencode() |
| 18 | SEC-24 | **已修** | finally: conn.close() |
| 19 | RNK-1+9 | **已修** | cache 分離 + query_params 加入 key |
| 20 | RNK-5 | **已修** | dimension mismatch warning log |
| 21 | RNK-7 | **已修** | title boost multiplier 取代 doc_length 膨脹 |
| 22 | RNK-8 | **已修** | NaN → 0.0 |
| 23 | RNK-11 | **已修** | 移除 runtime pip install → ImportError |
| 24 | RNK-14 | **已修** | > 改 >= |
| 25 | RNK-15 | **已修** | ranking.get("score", 0) |
| 26 | RNK-20 | **已修** | except: → except Exception: |
| 27 | RSN-8 | **已修** | 統一用 WriterPromptBuilder |
| 28 | RSN-10 | **已修** | getattr(tracer, 'start_time', None) |
| 29 | RSN-11 | **已修** | 空 context → 回傳「查無相關資料」 |
| 30 | RSN-12 | **已修** | total_iterations ≤ 0 → 1 |

### 統計

| 狀態 | 數量 |
|------|:----:|
| 已修復 | **47** |
| 延後（JWT） | 4 |
| 不修（設計保留） | 1 |
| 無需修（已正確） | 1 |
| **合計** | **53** |

### 待後續處理

- **SEC-1 + SEC-9 + SEC-18 + SEC-19**：等 JWT/登入系統設定完成
- **SEC-6**：Lossless Agent Isolation 架構重構（獨立任務）
- **RNK-7 注意**：BM25 corpus stats 已改變（不再 3x title），需重建 corpus stats
- **RSN-4 前端**：需讀取 `verification_status` / `verification_message` 顯示未驗證提示

---

## 統計總覽

| 模組 | CRITICAL | HIGH | MEDIUM | LOW | 合計 |
|------|:--------:|:----:|:------:|:---:|:----:|
| **WebServer + Security** | 3 | 6 | 8 | 5 | **22** |
| **Indexing + Dashboard** | 1 | 6 | 8 | 4 | **19** |
| **Crawler Engine** | 0 | 3 | 7 | 7 | **17** |
| **Reasoning System** | 3 | 4 | 7 | 4 | **18** |
| **Core Ranking** | 0 | 3 | 7 | 7 | **17** |
| **合計** | **7** | **17** | **35** | **24** | **83** |

---

## CRITICAL（必須立即修復）

### SEC-1. JWT 認證形同虛設 — 無效 token 直接放行

**檔案**：`webserver/middleware/auth.py:135`

```python
except jwt.InvalidTokenError as e:
    # If JWT validation fails, allow the token through for backward compatibility
    # but log the error
    logger.debug(f"JWT validation failed for token: {e}")
```

**問題**：`jwt.InvalidTokenError` 被 catch 後仍設 `authenticated: True`。任何人送任意字串當 Bearer token 即可通過認證。「backward compatibility」註解表明是刻意的，但完全否定了 JWT 認證。

**修復**：無效 JWT 回傳 401。若需相容舊 token 格式，另建獨立驗證路徑。

---

### SEC-2. CORS 萬用字元 + Allow-Credentials

**檔案**：`webserver/middleware/cors.py:21`

```python
cors_headers = {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Credentials': 'true',
    ...
}
```

**問題**：`*` + `Allow-Credentials: true` 是 CORS 規格中的無效組合。瀏覽器會拒絕帶憑證的跨域請求，但 wildcard `*` 本身就允許任何網站呼叫 API 並讀取回應（搜尋結果、對話、analytics）。

**修復**：改為明確 origin 白名單，移除 `Allow-Credentials: true` 或搭配 origin 反射白名單。

---

### SEC-3. SQL 注入風險 — 動態 table/column 名稱

**檔案**：`core/query_logger.py:646`

```python
def _write_to_db(self, table_name: str, data: Dict[str, Any]):
    columns = ", ".join(data.keys())
    query = f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})"
```

**問題**：values 有參數化（安全），但 `table_name` 和 `data.keys()` 直接 f-string 插入 SQL。目前呼叫端用 hardcoded keys，但此方法是通用內部 API，未來任何呼叫者傳入使用者控制的 dict keys 即構成注入。

**修復**：驗證 `table_name` 與 `data.keys()` 是否在白名單內，或使用 SQL builder。

---

### SEC-4. Prompt Injection — 使用者查詢直接進入 LLM prompt

**檔案**：
- `reasoning/prompts/analyst.py:72`（query 在 f-string）
- `reasoning/agents/writer.py:61-98`（plan prompt）
- `reasoning/prompts/cov.py:31`（draft 在 f-string）
- `reasoning/prompts/analyst.py:116-119`（revision prompt）

**問題**：所有 user-supplied query 直接 f-string 插入 prompt，無 sanitization 或結構性隔離。攻擊者可提交 "Ignore all previous instructions..." 類查詢。

**修復**：將 user input 包裹在 XML tag（如 `<user_query>...</user_query>`）提供結構隔離，或加入 sanitization 層。

---

### SEC-5. 幻覺防護漏洞 — Analyst citations 未驗證

**檔案**：`reasoning/orchestrator.py:899-1020`

```python
analyst_citations = response.citations_used  # LLM 生成，從未對 source_map 驗證

# Line 1003: 只檢查 Writer ⊆ Analyst，不檢查 Analyst ⊆ source_map
if not set(final_report.sources_used).issubset(set(analyst_citations)):
```

**問題**：幻覺防護只確保 Writer 的引用是 Analyst 引用的子集，但 Analyst 的 citation IDs 可能根本不存在於 `source_map`。Phantom citations 存活到前端時會產生空 URL。

**修復**：在 line 899 後加：`analyst_citations = [c for c in response.citations_used if c in self.source_map]`，並 warning log 被移除的 IDs。

---

### SEC-6. 無界 Context 可超出 LLM token 上限

**檔案**：`reasoning/orchestrator.py:656-676`

**問題**：Gap resolution 迴圈中 `current_context` 無限累積，`source_map` build 時註明 "no limit"。Writer compose 路徑無 draft 截斷。system hints 跨 iteration 累積。可能導致 LLM API 400 錯誤或靜默截斷。

**修復方向（討論定案）**：Lossless Agent Isolation + Structured Working Memory

不使用 LLM 摘要（多 agent 下累積資訊損失太大）。改為每個 agent 只注入它需要的 context：

**1. Analyst Gap Loop 改造**：
- Round 1: query + docs 全文
- Round N: query + 上輪 `extracted_knowledge` + 上輪 `draft` + 新檢索的 docs 全文
- 不重複注入已讀過的 docs → context 大小不隨輪次無限增長

**2. Analyst Structured Output 強化**（防止「後知後覺」資訊遺失）：
```json
{
  "current_draft": "...",
  "identified_gaps": ["..."],
  "citation_map": {},
  "extracted_knowledge": [
    {"fact": "事實描述", "source": "doc_id"}
  ]
}
```
`extracted_knowledge` 記錄所有值得保留的事實（不只跟 draft 直接相關的），供下一輪 Analyst 使用。
`extracted_knowledge` 跨輪由 Orchestrator 累積 merge（確定性邏輯，非 LLM），不是每輪覆蓋，避免 Round N 的 Analyst 遺漏 Round N-1 記錄的事實。

**3. Critic On-Demand Context**：
- Orchestrator 解析 draft 中的 citation IDs
- 從 source_map 抓取被引用的 chunks（不是全文、不是只有 metadata）
- 組成 Reference Sheet 給 Critic 做 fact checking

**4. Writer Minimal Context**：
- 只收 query + approved draft + citation metadata + plan
- 不需要原始文件（Critic 已驗證過事實）

**5. system hints 每輪重建**（同時解決 RSN-5）

**原始資料保存**：source_map 作為 Single Source of Truth，完整保存所有文件，不進 LLM context 除非被特定 agent 需要。

---

### IDX-1. QdrantClient 連線洩漏

**檔案**：`indexing/dashboard_api.py:151`

```python
def _sync_qdrant():
    client = QdrantClient(url=qdrant_url, timeout=3)
    try:
        info = client.get_collection(collection_name)
        return {...}
    except Exception:
        return {...}
    # client 從未 close()
```

**問題**：每次 `GET /api/indexing/stats` 建立新 client 但不關閉。Dashboard auto-refresh 累積未關閉連線直到 fd 耗盡。

**修復**：加 `finally: client.close()`。

---

## HIGH（應盡快修復）

### Security 類

#### SEC-7. WebSocket 無 Origin 驗證
**檔案**：`webserver/routes/chat.py:939-1042`

任何網站可建立 WS 連線至 `/chat/ws`。搭配 anonymous user 支援，構成 Cross-Site WebSocket Hijacking（CSWSH）。

**修復**：檢查 `request.headers.get('Origin')` 對比白名單。

#### SEC-8. WebSocket 允許 Client 冒充任意 User ID
**檔案**：`webserver/routes/chat.py:1084-1091, 1247-1253`

```python
join_user_id = data.get('user_id', user_id)  # client 可指定任意 ID
connection.participant_id = join_user_id
```

**修復**：`participant_id` 必須從 server-side auth state 取得，不信任 client-supplied identity。

#### SEC-9. WebSocket JWT 不驗簽
**檔案**：`webserver/routes/chat.py:976-991`

手動 base64 decode JWT payload 不驗 signature。任何人可偽造任意 claims。

**修復**：使用 `jwt.decode(token, secret, algorithms=['HS256'])`。

#### SEC-10. XSS — marked.parse() 輸出未消毒
**檔案**：`static/news-search.js:2081-2099`

```javascript
let reportHTML = marked.parse(report || '...');
reportContainer.innerHTML = reportHTML;  // 無 DOMPurify
```

Deep Research 報告含使用者查詢和新聞內容，可能含惡意 HTML。

**修復**：`reportContainer.innerHTML = DOMPurify.sanitize(reportHTML);`

#### SEC-11. 無 WS Message Size / Rate Limit
**檔案**：`webserver/routes/chat.py:1041`

`WebSocketResponse(heartbeat=30)` 未設 `max_msg_size`，無 rate limiting。

**修復**：`max_msg_size=64*1024`，加 per-connection rate limiting。

#### SEC-12. API 端點無 Rate Limiting
**檔案**：`webserver/routes/api.py`

`/ask`（LLM 推論）、`/api/deep_research`（多 agent）無速率限制，可造成成本攻擊。

**修復**：加 rate limiting middleware，按端點成本設定不同限制。

### Bug 類

#### ENG-1. Pipeline Save 失敗仍回傳 SUCCESS
**檔案**：`crawler/core/engine.py:772-778`

```python
if self.auto_save:
    success = await self.pipeline.process_and_save(url, data)
    if not success:
        self.stats['failed'] += 1
        self._mark_failed(url, "save_error", "Pipeline save failed")
        return CrawlStatus.SUCCESS  # BUG: 應為 FETCH_ERROR 或新的 SAVE_ERROR
```

URL 被標記為 failed 但回傳 SUCCESS，caller 不當成失敗處理。

#### ENG-2. _run_parse_in_thread 手動 exhaust coroutine — parser 加 await 會 silent fail
**檔案**：`crawler/core/engine.py:34-56`

```python
def _run_parse_in_thread(parser, html, url):
    coro = parser.parse(html, url)
    try:
        coro.send(None)
    except StopIteration as e:
        return e.value
```

假設所有 parser.parse() 是 async def 但不含 await。若任何 parser 加入 await，`send(None)` 不會 raise StopIteration，silent return None。

**修復**：改用 `asyncio.run_coroutine_threadsafe()` 或讓 parser 直接提供 sync 方法。

#### ENG-3. SSL 驗證無條件關閉
**檔案**：`crawler/core/engine.py:374-378`

```python
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE
```

`settings.py` 定義了 `SSL_VERIFY` 和 `SSL_CA_BUNDLE` 但 engine 完全忽略。

#### IDX-2. Command Injection + PID Reuse Race
**檔案**：`indexing/dashboard_api.py:696`

```python
os.system(f"taskkill /F /PID {pid} >nul 2>&1")
```

`pid` 來自 JSON 檔案，未驗證為 int。且 PID reuse 可能殺掉無關進程。

**修復**：`subprocess.run(["taskkill", "/F", "/PID", str(int(pid))])` + 驗證 process cmdline。

#### IDX-3. _save_tasks Fire-and-Forget
**檔案**：`indexing/dashboard_api.py:705-733`

`run_in_executor` 回傳的 Future 未 await，寫入失敗無聲丟資料。多個並行呼叫可能 race 造成 JSON 損壞。

**修復**：原子寫入（temp file + os.replace）+ asyncio.Lock。

#### IDX-4. Resumable Mode 從未 Flush Qdrant Buffer
**檔案**：`indexing/pipeline.py:174`

`process_tsv_resumable` 完全沒有 `_flush_qdrant_buffer()` 呼叫。Resumable mode 處理的文章永遠不會上傳到 Qdrant。

**調查結論**：這是 bug，不是刻意設計。Resumable mode 從 normal mode 複製而來，加了 checkpoint 但漏掉 flush。

**修復方向**：合併為單一模式，同時支援 checkpoint + 正常 flush：
- 每 100 chunks flush Qdrant（同 normal mode）
- 每 N 篇文章存 checkpoint（resumable 能力）
- flush 失敗時 checkpoint 不前進，避免 SQLite/Qdrant 不一致
- 異常關閉最多丟 100 chunks，重跑從 checkpoint 繼續

**時機**：排在大量 indexing 開始前修復。目前尚未使用 resumable mode，無資料遺失。

#### IDX-5. embed_texts 失敗整批丟失
**檔案**：`indexing/qdrant_uploader.py:132`

Embedding API 失敗（network error、rate limit）無 retry，exception 直接 propagate，已 chunk 的文章不反映在 Qdrant。

#### IDX-6. SQLite 連線跨 Thread 共用無 Operation-Level Locking
**檔案**：`crawler/core/crawled_registry.py:65-74`

Lock 只保護建立連線，不保護 SQL 操作。`check_same_thread=False` 關閉 Python 安全檢查但不讓連線 thread-safe。

#### IDX-7. mark_failed TOCTOU Race
**檔案**：`crawler/core/crawled_registry.py:393-433`

SELECT → INSERT/UPDATE 非原子。兩個 thread 同時 mark_failed 同一 URL 會 UNIQUE constraint 錯誤。

**修復**：`INSERT ... ON CONFLICT(url) DO UPDATE SET retry_count = retry_count + 1`。

#### RNK-1. 共享 _client_cache 存兩種物件
**檔案**：`core/retriever.py:76, 1210-1215`

`_client_cache` 同時快取 low-level DB clients（key 如 `"qdrant_endpoint1"`）和 high-level `VectorDBClient`（key 如 `"default"`）。Key 碰撞會回傳錯誤型別。

**修復**：分離為兩個 cache dict。

#### RNK-2. MMR O(k^2 * n * d) 未快取 Cosine Similarity
**檔案**：`core/mmr.py:250-261, 283-293`

每次 (candidate, selected) pair 都從頭 list→numpy→計算。Diversity logging 又重算一次全部。

**修復**：預計算 similarity matrix，一次 numpy 矩陣乘法。

#### RNK-3. XGBoost Production Mode 對 dict 設 attribute
**檔案**：`core/xgboost_ranker.py:449`

```python
result.xgboost_score = float(scores[i])  # result 是 dict，會 AttributeError
```

Phase C 上線時必 crash。Shadow mode 下不觸發。

#### RSN-1. 空 Draft 穿過 SEARCH_REQUIRED 到 Critic/Writer
**檔案**：`reasoning/orchestrator.py:610-714`

SEARCH_REQUIRED + failed gap search 路徑下，`response.draft` 可能為空字串。空 draft 送至 Critic review 後可能 PASS，再送至 Writer 產出低品質報告。

---

## MEDIUM（應排入修復計畫）

### Async / 並行問題

| ID | 檔案 | 問題 |
|----|------|------|
| ENG-4 | `engine.py` | `stats['failed']` 雙重計數（`_process_article` + `_evaluate_batch_results`） |
| ENG-5 | `engine.py:606,643,653,677,1552` | `asyncio.get_event_loop()` deprecated，應用 `get_running_loop()` |
| RNK-4 | `ranking.py:183,224` | `rankedAnswers` 並行 mutation（asyncio.gather 中多 task append） |
| IDX-8 | `dashboard_api.py:851` | WebSocket `remove()` 若已移除會 ValueError |
| IDX-9 | `dashboard_api.py:829-876` | `_websockets` list 並行修改，應改 set + discard |
| IDX-10 | `crawled_registry.py:659-680` | `_nf_buffer` 非 thread-safe，`executemany` 和 `clear` 之間可丟資料 |
| RSN-2 | `reasoning/agents/base.py:377` | 雙重 timeout（inner ask_llm + outer wait_for）同值，行為不可預期 |
| RSN-3 | `orchestrator.py:311-325` | sync 方法 `_check_connection()` 檢查 async state，TOCTOU race。**調查結論：`_check_connection()` 是取消機制的核心（8 個 checkpoint），不可移除。TOCTOU gap = 一次 LLM call 時間，無法避免。現有機制已能阻止後續 LLM call，但進行中的 call 會跑完（被收費但結果丟棄）。未來可改 streaming LLM response 進一步省錢。** |

### 錯誤狀態映射

| ID | 檔案 | 問題 |
|----|------|------|
| ENG-6 | `engine.py:507` | `TimeoutError` 映射為 `NOT_FOUND`，永久跳過可能有效的文章 |
| ENG-7 | `engine.py:692` | Parse exception 映射為 `BLOCKED`，可觸發 false early stop |
| ENG-8 | `engine.py:1551` | `_process_url`（retry/sitemap mode）未呼叫 `_ensure_date` |

### 資源洩漏 / 無界成長

| ID | 檔案 | 問題 |
|----|------|------|
| ENG-9 | `engine.py:180` | `crawled_ids` 全量載入記憶體，大 source 可 OOM（GCP e2-micro） |
| ENG-10 | `engine.py:239` | Logger FileHandler 從未 close，長期運行洩漏 fd |
| IDX-11 | `dashboard_api.py` | `_crawler_tasks` dict 無界成長，JSON 序列化越來越慢 |
| IDX-12 | `dashboard_api.py:347` | `_stderr_log_file` 若 subprocess 建立失敗會洩漏 fd |
| IDX-13 | `pipeline.py:322` | `buffer.jsonl` 只 append 不 rotate |
| SEC-13 | `routes/oauth.py:92` | OAuth states 存記憶體無清理，可被攻擊者灌爆 |

### 資料正確性

| ID | 檔案 | 問題 |
|----|------|------|
| IDX-14 | `pipeline.py:203` | Checkpoint off-by-one，crash 後重複處理 checkpoint_interval 筆 |
| IDX-15 | `crawled_registry.py:777` | `LIKE %article_id%` false positive + full table scan |
| IDX-16 | `crawled_registry.py:864` | `close()` 不 flush `_nf_buffer`，丟失 buffered data |
| IDX-17 | `qdrant_uploader.py:132` | 未驗證 `len(embeddings) == len(texts)` |

### 安全 / 資訊洩漏

| ID | 檔案 | 問題 |
|----|------|------|
| SEC-14 | `middleware/error_handler.py:60` | dev mode（預設）回傳完整 stack trace |
| SEC-15 | `routes/api.py:168,200,309,462` | 多處 raw exception 暴露給 client |
| SEC-16 | `routes/chat.py:1320` | WS error message 含 exception details |
| SEC-17 | `routes/chat.py:930` | unvalidated conv_id 用於 redirect |
| SEC-18 | `aiohttp_server.py:208` | `verify_participant` 永遠 return True |
| SEC-19 | `routes/chat.py:1473` | 10MB upload 端點無認證 |

### 演算法 / 效能

| ID | 檔案 | 問題 |
|----|------|------|
| RNK-5 | `mmr.py:168` | dimension mismatch silent 回傳 0.0，Qdrant profile 切換時會觸發 |
| RNK-6 | `mmr.py:48-53` | constructor lambda_param 被 intent detection 覆蓋 |
| RNK-7 | `bm25.py:72-85` | N-gram tokenization 膨脹 doc_length ~3x，扭曲 BM25 參數效果 |
| RNK-8 | `xgboost_ranker.py:532` | `kendalltau` 回傳 NaN 未處理 |
| RNK-9 | `retriever.py:1206` | cache 忽略 `query_params`，dev mode 可能回傳錯誤端點 client |

### Reasoning 特有

| ID | 檔案 | 問題 |
|----|------|------|
| RSN-4 | `critic.py:361` | CoV 失敗 silent 降級無使用者通知（違反 Silent Fail 規則）。**CEO 指示：CoV 失敗必須主動 alert 使用者，不可只 log warning。前端需顯示明確提示（如「本報告未經完整驗證」）。** |
| RSN-5 | `orchestrator.py:687` | system hints 跨 iteration 累積（重複 token 浪費） |
| RSN-6 | `orchestrator.py:890` | graceful degradation 條件 `reject_count >= max_iterations` 永遠不成立（dead code） |
| RSN-7 | `orchestrator.py:869` | `response` 變數在首次 analyst 呼叫失敗時可能未綁定（UnboundLocalError） |

### 其他

| ID | 檔案 | 問題 |
|----|------|------|
| IDX-18 | `dashboard_api.py:259,908` | `int()` cast 無 validation，non-numeric 回 500 而非 400 |
| IDX-19 | `dashboard_api.py:163` | deprecated `asyncio.get_event_loop()` |
| RNK-10 | `ranking.py:205` | exception handler 中 `name` 變數未綁定 |
| RNK-11 | `retriever.py:150` | runtime `pip install` — security + stability risk |
| RSN-8 | `writer.py:61-98` | inline prompt 與 `WriterPromptBuilder.build_plan_prompt()` 重複 |
| SEC-20 | `routes/oauth.py:127` | OAuth URL params 未 URL encode |

---

## LOW（可選修復）

### Crawler Engine

| ID | 檔案 | 問題 |
|----|------|------|
| ENG-11 | `engine.py:463` | `from_bytes().best()` 回傳 None 時 fallback 可能 garble non-UTF-8 |
| ENG-12 | `subprocess_runner.py:136` | `engine.close()` 在 except 內可能 raise，吞掉原始錯誤 |
| ENG-13 | `subprocess_runner.py:62` | class-level monkey-patch 可能 chain on repeated calls |
| ENG-14 | `settings.py:13` | `BASE_DIR` 依賴 5 層 `.parent` 遍歷，脆弱 |
| ENG-15 | `settings.py:23` | import time `mkdir` side effect |
| ENG-16 | `subprocess_runner.py:152` | `--params` JSON 中 URL 無驗證（SSRF 風險，需 dashboard API 層防護） |
| ENG-17 | `engine.py:1551` | `_process_url` 中 `_ensure_date` 未呼叫（sitemap/retry mode 文章可能無日期） |

### Indexing + Dashboard

| ID | 檔案 | 問題 |
|----|------|------|
| IDX-20 | `pipeline.py:195` | `datetime.utcnow()` deprecated（Python 3.12+） |
| IDX-21 | `qdrant_uploader.py:231` | `delete_by_article_url` docstring 說回傳 count，實際回傳 status enum |
| IDX-22 | `crawled_registry.py:210` | content_hash 截斷至 64 bits（碰撞風險低但無必要） |
| IDX-23 | `crawled_registry.py:871` | singleton `get_registry()` 非 thread-safe |

### Core Ranking

| ID | 檔案 | 問題 |
|----|------|------|
| RNK-12 | `retriever.py:952` | `_retrieval_lock` 序列化所有並行搜尋（throughput 瓶頸） |
| RNK-13 | `retriever.py:487` | API key 前 10 字元 logged at DEBUG level |
| RNK-14 | `ranking.py:502` | `num_results_sent` off-by-one（`>` vs `>=`） |
| RNK-15 | `ranking.py:172` | `ranking["score"]` 可能 KeyError（LLM malformed response） |
| RNK-16 | `ranking.py:145` | `json.loads` on malformed json_str 與 RNK-10 compound |
| RNK-17 | `mmr.py:127` | sync file I/O in async hot path（mmr_metrics.log） |
| RNK-18 | `mmr.py:184` | cosine similarity clamp [0,1] 丟失負相似度信號 |

### Reasoning

| ID | 檔案 | 問題 |
|----|------|------|
| RSN-9 | `base.py:61` | API key 前 8 字元 logged（OpenAI key `sk-proj-` 前綴全洩露） |
| RSN-10 | `orchestrator.py:1088` | `tracer.start_time` 可能未設定（AttributeError） |
| RSN-11 | `orchestrator.py:230` | empty context 只 warning 不 raise，下游可能幻覺 |
| RSN-12 | `orchestrator.py:83` | `total_iterations=0` 時 ZeroDivisionError |

### WebServer + Security

| ID | 檔案 | 問題 |
|----|------|------|
| SEC-21 | `routes/chat.py:948,1030,1069...` | 多處 `print()` 輸出 user data 到 stdout |
| SEC-22 | `routes/chat.py:1018` | Anonymous user ID 只 4 位數隨機（`random.randint(1000,9999)`），可碰撞 |
| SEC-23 | `routes/api.py`, `routes/chat.py` | POST 端點無 CSRF protection（CORS 設錯加劇） |
| SEC-24 | `core/query_logger.py:642` | DB connections 未用 context manager，exception 時洩漏 |
| SEC-25 | `chat/websocket.py:54` | `pong_timeout=600`（10 分鐘）過長，dead connection 長期佔用資源 |

### XGBoost / Feature Engineering

| ID | 檔案 | 問題 |
|----|------|------|
| RNK-19 | `training/feature_engineering.py:314` | tied scores 取 lowest percentile |
| RNK-20 | `training/feature_engineering.py:182` | bare `except:` catches SystemExit/KeyboardInterrupt |

---

## 修復優先建議（CEO 討論後定案 2026-02-23）

**背景**：產品將以 webapp 形式對外提供服務。SEC-12（rate limiting）和 SEC-4（prompt guardrail）已在進行中，不列入。

### Phase 1：上線前必修（Security + 資料正確性）

| # | ID | 修復內容 | 難度 | 討論結論 |
|---|-----|---------|:----:|---------|
| 1 | **SEC-1 + SEC-9** | JWT 認證修復（HTTP + WS） | 中 | 無效 JWT → 401，WS 用 jwt.decode() 驗簽，共用驗證函式 |
| 2 | **SEC-2** | CORS origin 白名單 | 低 | 移除 `*`，設前端 domain 白名單 |
| 3 | **SEC-10** | XSS — 加 DOMPurify | 低 | 所有 innerHTML 加 DOMPurify.sanitize() |
| 4 | **SEC-5 + RSN-1** | 幻覺防護 | 低 | Analyst citations 驗證 ⊆ source_map + 空 draft 攔截 |
| 5 | **ENG-1** | Save 失敗回傳正確狀態 | 低 | 改回傳 FETCH_ERROR 或新增 SAVE_ERROR |
| 6 | **IDX-4** | Resumable mode flush Qdrant | 中 | 合併為單一模式：checkpoint + flush 並行，flush 失敗 checkpoint 不前進 |
| 7 | **SEC-3** | SQL 注入防禦 | 低 | table/column 白名單驗證 |
| 8 | **IDX-1** | QdrantClient 連線洩漏 | 低 | 加 finally: client.close() |
| 9 | **RNK-3** | XGBoost production mode crash | 低 | `result.xgboost_score` → `result['xgboost_score']` |

### Phase 2：穩定性修復

| # | ID | 修復內容 | 難度 | 討論結論 |
|---|-----|---------|:----:|---------|
| 1 | **ENG-6** | TimeoutError 映射修正 | 低 | → FETCH_ERROR（可 retry），不是 NOT_FOUND（永久跳過） |
| 2 | **ENG-7** | Parse exception 映射修正 | 低 | → PARSE_ERROR，不計入 blocked 計數器 |
| 3 | **IDX-7** | mark_failed TOCTOU | 低 | INSERT ... ON CONFLICT DO UPDATE |
| 4 | **SEC-6** | 無界 context | 高 | **Lossless Agent Isolation 方案**（見 SEC-6 條目詳細記錄）：Analyst structured output（含 extracted_knowledge）+ Critic on-demand chunk injection + Writer minimal context。extracted_knowledge 由 Orchestrator 跨輪累積 merge（確定性邏輯）。不使用 LLM 摘要。 |
| 5 | **IDX-6** | SQLite operation-level locking | 中 | Lock 包覆整個 SQL 操作，或改 threading.local() 獨立 connection |
| 6 | **RSN-7** | response 未綁定 | 低 | 初始化 response = None + None check |
| 7 | **ENG-4** | stats failed 雙重計數 | 低 | 移除 _process_article 的計數，統一在 _evaluate_batch_results |
| 8 | **RNK-10** | exception handler name 未綁定 | 低 | 初始化 name = "unknown" |
| 9 | **IDX-3** | _save_tasks fire-and-forget | 中 | 原子寫入（temp + os.replace）+ asyncio.Lock |
| 10 | **RSN-4** | CoV silent 降級 | 低 | **必須主動 alert 使用者**，前端顯示「本報告未經完整驗證」 |
| 11 | **RSN-2** | 雙重 timeout | 低 | Inner timeout < Outer timeout，明確分工 |
| 12 | **RSN-3** | _check_connection TOCTOU | — | **不修（保留）**。是取消機制核心（8 個 checkpoint）。未來可改 streaming LLM 進一步省錢。 |
| 13 | **RNK-4** | rankedAnswers 並行 mutation | 低 | 改用 asyncio.gather return values |
| 14 | **IDX-8+9** | WebSocket list 並行修改 | 低 | 改 set + discard + broadcast 前 snapshot |
| 15 | **IDX-10** | _nf_buffer 非 thread-safe | 低 | swap 取代 clear |

### 排除項目

| ID | 原因 |
|----|------|
| **SEC-12** | 已在進行中（rate limiting） |
| **SEC-4** | 已在進行中（prompt guardrail） |
| **IDX-2** | Crawler 內部工具，安全性非必要 |
| **RSN-3** | 不修，是取消機制核心 |
| **ENG-2** | 所有 parser 為 no-await async def，刻意設計 |

### Phase 3：效能優化

| # | ID | 修復內容 | 難度 | 討論結論 |
|---|-----|---------|:----:|---------|
| 1 | **RNK-2** | MMR cosine similarity 重複計算 | 中 | 預計算 similarity matrix（一次 numpy 矩陣乘法），消除 O(k²*n*d) |
| 2 | **RNK-12** | _retrieval_lock 序列化所有搜尋 | 低 | 移除 lock。讀操作不需要保護，_client_cache 有自己的 lock。寫操作如需保護可加 per-endpoint lock。是重構時的防禦性設計，非必要。 |
| 3 | **ENG-9** | crawled_ids 全量載入記憶體 | 中 | 改用 SQLite 查詢（`registry.exists(url)`）。不用 Bloom filter（額外依賴不值得）。HTTP 請求才是瓶頸，SQLite 0.3ms overhead 可忽略。批次可用 `WHERE url IN (...)`。 |
| 4 | **IDX-5** | embed_texts 失敗整批丟失 | 低 | 加 retry with exponential backoff（1s, 2s, 4s），max_retries 後才放棄 |

### Phase 4：MEDIUM/LOW 修復

| # | ID | 修復內容 | 難度 | 討論結論 |
|---|-----|---------|:----:|---------|
| 1 | **ENG-5** | asyncio.get_event_loop() deprecated | 低 | 改 get_running_loop()，機械性替換 |
| 2 | **ENG-8 + ENG-17** | _process_url 未呼叫 _ensure_date | 低 | 加 _ensure_date 呼叫，合併為一項 |
| 3 | **ENG-10** | Logger FileHandler 從未 close | 低 | engine.close() 中清理 handler |
| 4 | **ENG-11** | charset fallback 可能亂碼 | 低 | 加 Big5 fallback |
| 5 | **ENG-12** | engine.close() 在 except 可能 raise | 低 | try/except 包住 close，保留原始 exception |
| 6 | **IDX-11** | _crawler_tasks 無界成長 | 低 | 只保留最近 50 筆完成的任務 |
| 7 | **IDX-12** | _stderr_log_file 洩漏 fd | 低 | subprocess 建立失敗時 close file handle |
| 8 | **IDX-13** | buffer.jsonl 不 rotate | 低 | flush 成功後清空 |
| 9 | **IDX-14** | Checkpoint off-by-one | 低 | 記錄「下一行行號」，跟 IDX-4 一起修 |
| 10 | **IDX-15** | LIKE %article_id% false positive | 低 | 改更精確的 pattern |
| 11 | **IDX-16** | close() 不 flush _nf_buffer | 低 | close() 前先 flush，跟 IDX-10 一起修 |
| 12 | **IDX-17** | embed_texts 回傳數量未驗證 | 低 | 加 len(embeddings) != len(texts) 檢查 |
| 13 | **IDX-21** | delete_by_article_url docstring 不符 | 低 | 修 docstring 或回傳值 |
| 14 | **SEC-13** | OAuth states 無清理 | 低 | 加 TTL 600 秒自動清理 |
| 15 | **SEC-18** | verify_participant 永遠 True | — | 合併到 SEC-1 一起修 |
| 16 | **SEC-19** | 10MB upload 無認證 | — | 合併到 SEC-1 一起修 |
| 17 | **SEC-20** | OAuth URL params 未 URL encode | 低 | 用 urllib.parse.urlencode() |
| 18 | **SEC-24** | DB connections 未用 context manager | 低 | 改 with sqlite3.connect() |
| 19 | **RNK-1 + RNK-9** | _client_cache 混存 + 忽略 query_params | 中 | 分離兩個 cache dict + 加 params 到 cache key，跟 RNK-12 一起修 |
| 20 | **RNK-5** | dimension mismatch silent 回傳 0.0 | 低 | 加 warning log，或排除不匹配結果 |
| 21 | **RNK-7** | N-gram 膨脹 doc_length | 中 | title weighting 改為 score multiplier，**排在 XGBoost Phase C 前** |
| 22 | **RNK-8** | kendalltau NaN | 低 | NaN → 0.0 |
| 23 | **RNK-11** | runtime pip install | 低 | 移除，放 requirements.txt |
| 24 | **RNK-14** | num_results_sent off-by-one | 低 | `>` 改 `>=` |
| 25 | **RNK-15** | ranking["score"] KeyError | 低 | 改 ranking.get("score", 0) |
| 26 | **RNK-20** | bare except catches SystemExit | 低 | 改 except Exception |
| 27 | **RSN-8** | writer inline prompt 重複 | 低 | 統一用 WriterPromptBuilder |
| 28 | **RSN-10** | tracer.start_time 未設定 | 低 | 初始化時設定 start_time |
| 29 | **RSN-11** | empty context 只 warning | 低 | 回傳「查無相關資料」，不進 Analyst |
| 30 | **RSN-12** | total_iterations=0 ZeroDivisionError | 低 | 初始化檢查 ≤0 → 設為 1 |

### 確定非問題（不修）

| ID | 問題 | 理由 |
|----|------|------|
| RSN-6 | Dead code | 不影響功能 |
| ENG-13 | Monkey-patch chain | subprocess_runner 只跑一次 |
| ENG-14 | BASE_DIR 5 層 parent | 專案結構固定 |
| ENG-15 | Import-time mkdir | 無害 side effect |
| IDX-20 | datetime.utcnow() deprecated | Python 3.11 不受影響 |
| IDX-22 | content_hash 截斷 64 bits | 碰撞機率可忽略 |
| IDX-23 | singleton get_registry() 非 thread-safe | 每個 source 是獨立 process，不會碰撞 |
| RNK-6 | MMR lambda 被覆蓋 | 設計意圖（intent-based 調整） |
| RNK-13 + RSN-9 | API key 前幾碼 logged | 前綴是公開格式，不構成威脅。改 log 後幾碼反而更危險 |
| RNK-16 | json.loads malformed | json_str 來自 DB 不是 LLM，幾乎不會失敗 |
| RNK-17 | sync file I/O in async path | mmr_metrics.log 寫入很快，影響可忽略 |
| RNK-18 | Cosine clamp 丟負值 | 新聞搜尋不需要負相似度 |
| RNK-19 | Tied scores 取 lowest | 訓練資料特性 |
| SEC-21 | print() 輸出 user data | 不需改動 |
| SEC-22 | Anonymous user ID 4 位數 | 未來會有新登入系統 |
| SEC-23 | 無 CSRF | 等 SEC-1 定案，如用 Bearer token 則不需要 |
| SEC-25 | pong_timeout 600s | 暫不修 |
| ENG-16 | SSRF via subprocess params | Crawler 內部工具 |

---

*報告生成：2026-02-23，by Claude Code Review*
*CEO 討論定案：2026-02-23*
