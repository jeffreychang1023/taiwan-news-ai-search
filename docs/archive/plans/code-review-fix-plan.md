# Code Review: Risky Fix Investigation & Plan

> 2026-02-09 Code Review 產出
> 這些修復需要額外調查或有 breaking 風險，不能直接改

---

## C1: `_run_parse_in_thread()` exception handling

### 問題
`engine.py:30-42` — coroutine 若拋出非 `StopIteration` 的 exception，會被 `finally: coro.close()` 吞掉，caller 拿到 `None`。

### 風險分析
- 直接改成 raise → **會 break**。所有 caller 預期回傳 `None` 代表解析失敗，會在 `_process_article()` 裡被 `if data is None: stats['not_found'] += 1` 處理。
- 如果改成 raise，`asyncio.gather(return_exceptions=True)` 的 batch 會收到 Exception object 而非 None。

### 建議方案（安全）
```python
def _run_parse_in_thread(parser, html, url):
    coro = parser.parse(html, url)
    try:
        coro.send(None)
    except StopIteration as e:
        return e.value
    except Exception as e:
        # 記錄但不 raise，保持現有 caller 行為
        logging.getLogger("CrawlerEngine").error(
            f"Parser exception for {url}: {e}", exc_info=True
        )
        return None
    finally:
        coro.close()
```

### 調查項目
- [ ] 確認所有 caller 都用 `if data is None` 處理失敗
- [ ] 檢查 `_process_article()` 和 `_process_url()` 的 None 處理
- [ ] 確認 `_evaluate_batch_results()` 能正確處理

### 預估影響
- 零行為改變（只加 logging）
- 可以安全實施

---

## C3: Qdrant Point ID — MD5 → UUID5 migration

### 問題
`qdrant_uploader.py:165-172` — MD5 截斷為 64-bit integer 作為 Qdrant point ID。百萬級 chunks 下碰撞機率不可忽略。

### 風險分析
- 改 ID 生成算法 → **一定會 break**
- 現有 Qdrant 資料全部用舊 ID，新資料用新 ID → 同一 chunk 出現兩份
- `check_exists()` 用新 ID 查不到舊資料 → reconciliation 失效

### 建議方案（分階段）

**Phase 1: 評估碰撞率（立即）**
```python
# 一次性腳本：掃描所有 chunk_id，計算碰撞數
from collections import Counter
import hashlib

def check_collisions(chunk_ids):
    point_ids = [int(hashlib.md5(cid.encode()).hexdigest()[:16], 16) for cid in chunk_ids]
    counter = Counter(point_ids)
    collisions = {pid: cnt for pid, cnt in counter.items() if cnt > 1}
    print(f"Total chunks: {len(chunk_ids)}, Collisions: {len(collisions)}")
    return collisions
```

**Phase 2: 決定方案**
- 如果碰撞數 = 0 且 chunk 總數 < 50 萬 → 暫不處理，下次 re-index 時改
- 如果碰撞數 > 0 → 需要 migration

**Phase 3: Migration（下次 re-index 時）**
1. 改用 Qdrant UUID string ID（`uuid.uuid5(NAMESPACE_URL, chunk_id)`）
2. 刪除舊 collection
3. 重新上傳全部資料

### 調查項目
- [ ] 目前 Qdrant 有多少 points？
- [ ] 執行碰撞檢測腳本
- [ ] 確認 Qdrant client 版本是否支援 string UUID ID

### 預估影響
- Phase 1: 零風險（只讀）
- Phase 3: 需要完整 re-index（數小時 downtime）

---

## C4: XSS — `innerHTML` sanitization

### 問題
`news-search.js` 多處使用 `innerHTML` 插入後端回傳的 `title`, `publisher`, `description`。

### 風險分析
- 對所有欄位加 `escapeHTML()` → 如果某些欄位刻意包含 HTML（如 `<em>` highlight）會被破壞
- 需要先確認哪些欄位是 plain text、哪些是 intentional HTML

### 調查項目
- [ ] 後端 `message_senders.py` 和 reasoning 回傳的欄位有哪些可能包含 HTML？
  - `result.content` 裡的 `title`, `description` → 來自 Qdrant payload → 來自 parser → **plain text**
  - `reasoning_report` → 來自 LLM → **可能包含 markdown/HTML**
  - `clarification.question` → 來自 LLM → **plain text**
- [ ] 前端 `renderArticleCard()` 的每個欄位來源
- [ ] 前端 `renderResearchReport()` 是否已有 sanitization

### 建議方案
1. **Parser 輸出欄位**（title, author, publisher, description, keywords）→ 全部加 `escapeHTML()`
2. **LLM 輸出欄位**（reasoning report, chain analysis）→ 使用 markdown renderer（已有？）或 DOMPurify
3. **URL 欄位** → 只允許 `http://` 和 `https://` schema

### 預估影響
- Parser 欄位：零風險（全是 plain text）
- LLM 欄位：需要確認現有 rendering 方式

---

## C5: ESG_BT redirect detection

### 問題
`esg_businesstoday_parser.py` 的 `is_not_found_redirect()` 定義了但 engine 沒呼叫。

### 風險分析
- 修改 engine 在 `_fetch()` 裡呼叫 `is_not_found_redirect()` → 可能改變現有判斷邏輯
- 目前 ESG_BT 用 HTML-based 檢測（`articleBody` 不存在 + 首頁連結 ≥ 5）

### 調查項目
- [ ] engine `_fetch()` 是否已有 redirect detection？
- [ ] `is_not_found_redirect()` 的 request_url / response_url 在 aiohttp 和 curl_cffi 中怎麼取得？
- [ ] 現有 HTML-based 檢測的 false positive 率是多少？

### 建議方案
```python
# 在 _fetch() 的 aiohttp 分支加入 redirect detection
if hasattr(self.parser, 'is_not_found_redirect'):
    final_url = str(response.url)
    if self.parser.is_not_found_redirect(url, final_url):
        return None, CrawlStatus.NOT_FOUND
```

### 預估影響
- 中等風險：可能改變某些文章的判定結果
- 建議先收集 log 確認 redirect 頻率再決定

---

## H3: Chinatimes parser curl_cffi fallback

### 問題
`chinatimes_parser.py:80` — 只支援 curl_cffi，無 aiohttp fallback。

### 風險分析
- 加 aiohttp fallback → **低風險但可能影響爬取成功率**
- Chinatimes 可能有 Cloudflare 保護，aiohttp 可能被擋

### 調查項目
- [ ] 用 aiohttp 直接 fetch 一篇 chinatimes 文章測試是否被擋
- [ ] 其他 parser (einfo, esg_bt) 的 fallback 邏輯作為參考

### 建議方案
參考 `einfo_parser.py` 的 `_get_response_text()` 模式，加入 aiohttp fallback。

### 預估影響
- 低風險：只在 curl_cffi 不可用時才觸發 fallback
- 最壞情況：aiohttp 被 CF 擋 → 回傳 None → 跟現在一樣失敗

---

## H7: Chunk merging — empty title handling

### 問題
`retriever.py:631-660` — 如果所有 chunks 的 title/name 都是空，下游 citation 顯示空白。

### 調查項目
- [ ] Qdrant 裡有多少 points 的 `name` 欄位是空的？
- [ ] 前端 citation 顯示空白 title 時的 UX

### 建議方案
```python
# 在 _merge_chunk_group() 裡加 fallback
if not best.get('title') and not best.get('name'):
    # 使用 URL 的 path 作為 fallback title
    from urllib.parse import urlparse
    path = urlparse(best.get('url', '')).path
    best['name'] = path.split('/')[-1] or 'Untitled'
```

### 預估影響
- 低風險：只影響原本就是空的 case
- 需要確認改 `name` 欄位不會影響 BM25 ranking

---

## H8: Gemini timeout hardcoded

### 問題
`core/embedding.py:210` — Gemini batch 的 timeout 寫死 30s，不用 function parameter。

### 調查項目
- [ ] 呼叫 `get_batch_embeddings()` 的地方傳什麼 timeout？
- [ ] Gemini batch 通常需要多久？

### 建議方案
```python
result = await asyncio.wait_for(
    get_gemini_batch_embeddings(texts, model=model_id),
    timeout=timeout  # 使用 function parameter
)
```

### 預估影響
- 低風險：如果 caller 傳入的 timeout ≥ 30s → 行為不變
- 如果 caller 傳入 < 30s → 可能提早 timeout（需確認 caller）

---

## M3: Date floor — hardcoded source list

### 問題
`engine.py:671` — `is_date_based = source_name in ('cna', 'esg_businesstoday')` 沒包含 chinatimes。

### 風險分析
- 用 `FULL_SCAN_CONFIG` 替代 → 需要計算正確的 `suffix_digits`
- Chinatimes 用 6 位 suffix，生成的 floor_id 格式不同

### 建議方案
```python
config = FULL_SCAN_CONFIG.get(source_name, {})
if config.get("type") == "date_based":
    suffix_digits = config.get("suffix_digits", 4)
    floor_id = int(floor_date.strftime('%Y%m%d') + '0' * suffix_digits)
```

### 預估影響
- 低風險：只影響 `run_auto()` 的 `date_floor` 功能
- 對 chinatimes 的 `run_auto` 新增 date floor 支援（原本沒有）

---

## M6: Sitemap pattern format change

### 問題
UDN/LTN 的 `article_url_pattern` 從 `<loc>` extraction pattern 改為 raw URL pattern。

### 調查項目
- [ ] Engine 的 `_fetch_sitemap_urls()` 如何使用 `article_url_pattern`？
- [ ] 是否先提取 `<loc>` tag 內容，然後再 match pattern？

### 建議方案
讀取 engine 的 sitemap 處理邏輯，確認 pattern 的使用時機。如果 engine 先提取 URL 再 match pattern → 新格式正確。如果 engine 對整個 XML 做 match → 新格式不會命中。

### 預估影響
- 如果不一致 → sitemap crawl 零命中（嚴重）
- 如果一致 → 無影響

---

## 修復狀態

| Issue | 風險 | 狀態 | 結果 |
|-------|------|------|------|
| C1 (parser exception logging) | 零風險 | **已修** | 加 logging，保持回傳 None |
| H8 (Gemini timeout) | 低風險 | **已修** | 改用 function parameter |
| M3 (date floor config) | 低風險 | **已修** | 用 FULL_SCAN_CONFIG 查詢 |
| H3 (chinatimes fallback) | 低風險 | **已修** | 加 aiohttp 相容（status/text） |
| H7 (empty title fallback) | 低風險 | **已修** | URL path 作為 fallback |
| C4 (XSS innerHTML) | 中風險 | **已調查→不需大修** | 已用 escapeHTML()，只修 clarification question |
| M6 (sitemap pattern) | 可能嚴重 | **已調查→無問題** | engine 先提取 URL 再 match pattern，格式正確 |
| C5 (ESG_BT redirect) | 中風險 | **已調查→無問題** | engine _fetch() 已透過 hasattr() 呼叫 is_not_found_redirect() |
| C3 (Qdrant point ID) | 必定 break | **待討論** | 下次 re-index 時處理 |
