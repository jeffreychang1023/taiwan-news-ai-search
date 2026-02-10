# Indexing Module Upgrade Plan

> 2026-02-06 討論確認的所有修改項目

---

## 背景

對 `indexing-spec.md` 和 `crawler-dashboard-spec.md` 進行專業審查後，發現多項設計問題、文件不一致、和實作缺陷。本計劃記錄所有已確認的修改決策。

---

## 修改項目總覽

| # | 項目 | 改動範圍 | 優先級 |
|---|------|---------|--------|
| 1 | Qdrant Payload 重新設計 | `qdrant_uploader.py`, `dual_storage.py`, `pipeline.py` | P0 (Backfill 前必須完成) |
| 2 | Chunk Dedup（方案 B：合併） | `core/retriever.py` | P0 |
| 3 | Crawler `_mark_as_crawled` 順序修正 | `crawler/core/engine.py` | P1 |
| 4 | Pipeline Reconciliation 工具 | `indexing/pipeline.py` | P1 |
| 5 | CrawledRegistry WAL + Timeout | `crawler/core/crawled_registry.py` | P1 |
| 6 | 停止條件常數統一 | `crawler/core/settings.py`, `engine.py` | P1 |
| 7 | Data Lineage（task_id/batch_id） | `crawled_registry.py`, `engine.py` | P1 |
| 8 | Blocked URL Retry 保守策略 | `engine.py`, `dashboard_api.py` | P2 |
| 9 | 文件修正與同步 | `indexing-spec.md`, `crawler-dashboard-spec.md` | P2 |

---

## P0：Backfill 前必須完成

### 1. Qdrant Payload 重新設計

**問題**：目前 `qdrant_uploader.py` 的 payload 與 retriever/ranking/reasoning 期望的格式不相容。

**目前 payload**（qdrant_uploader.py）：
```python
{
    "url": chunk_id,              # "article_url::chunk::0" ← retriever 期望文章 URL
    "name": chunk_summary,
    "site": site,
    "schema_json": json.dumps({   # chunk metadata ← retriever 期望文章 metadata
        "article_url": ...,
        "chunk_index": 0,
        "char_start": 0,
        "char_end": 170,
        "@type": "ArticleChunk",
        "version": 2,
    })
}
```

**新 payload 設計**：
```python
payload = {
    # ─── Retriever/Ranking/Reasoning 相容欄位 ───
    "url":         article_url,        # 文章 URL（citation 連結、dedup key、前端顯示）
    "name":        chunk_summary,      # "標題。代表句1。代表句2。"（BM25 + 顯示）
    "site":        site,               # 來源代號（filter + 顯示）
    "schema_json": json.dumps({        # 文章層級 metadata
        "@type": "NewsArticle",
        "headline":      headline,
        "datePublished": date_published,
        "author":        author,
        "publisher":     publisher,
        "keywords":      keywords,
        "description":   first_200_chars,  # 文章前 200 字，給 BM25 更多信號
    }),

    # ─── Chunk 專用欄位（新增）───
    "chunk_id":    "article_url::chunk::0",  # Vault 查詢 key
    "article_url": article_url,              # 明確的文章 URL
    "chunk_index": 0,
    "char_start":  0,
    "char_end":    170,
    "keywords":    ["關鍵字1", "關鍵字2"],   # 頂層 array → Qdrant 原生 array match
    "indexed_at":  "2026-02-06T12:00:00",   # 索引時間戳（維護用）
    "task_id":     "backfill_ltn_87_xxx",   # 來源任務 ID（purge by task 用）
    "version":     2,
}
```

**設計理由**：
- `url` = 文章 URL → citation 連結正確、dedup 自然 work
- `schema_json` = 文章 metadata → 時間過濾、作者過濾、BM25 全部正常
- chunk metadata 提升為頂層欄位 → 不需 JSON.parse() 就能存取
- `article_url` 頂層欄位 → Qdrant 原生 filter 可用（刪除同篇所有 chunks）

**改動檔案**：
- `code/python/indexing/qdrant_uploader.py` — 重寫 payload 構建
- `code/python/indexing/dual_storage.py` — `MapPayload` class 重構
- `code/python/indexing/pipeline.py` — 傳遞 CDM 的 article metadata 到 payload；datePublished 統一為 ISO 8601 格式

**不需改動**：
- `reasoning/orchestrator.py` — 讀 `url`, `title`, `site` 格式不變
- `reasoning/agents/*.py` — 只看 `formatted_context` 文字
- `core/ranking.py` — 讀 `url`, `schema_json`, `title`, `site` 格式不變
- `core/mmr.py`, `core/post_ranking.py`, `message_senders.py`, 前端 — 格式不變

---

### 2. Chunk Dedup（方案 B：合併同文章 chunks）

**問題**：同一篇文章的 3-5 個 chunks 會獨立進入搜尋結果，浪費 LLM ranking token + 重複引用。

**位置**：`core/retriever.py`，Qdrant 搜尋後、ranking 前。

**方案 B 邏輯**：
```python
def _merge_chunks_by_article(self, results: List[Dict]) -> List[Dict]:
    """合併同一 article_url 的 chunks 為一個結果"""
    article_groups = {}
    for result in results:
        url = result.get('url', '')
        if url not in article_groups:
            article_groups[url] = []
        article_groups[url].append(result)

    merged = []
    for url, chunks in article_groups.items():
        # 取最高分的 chunk 為基底
        best = max(chunks, key=lambda x: x.get('retrieval_scores', {}).get('final_retrieval_score', 0))

        # 合併所有 chunks 的 name（摘要）
        all_names = [c.get('title', '') or c.get('name', '') for c in chunks]
        merged_name = _merge_summaries(all_names, max_length=500)
        best['title'] = merged_name
        best['name'] = merged_name

        # 保留所有 chunk_ids（Vault 查詢用）
        best['_chunk_ids'] = [c.get('chunk_id', '') for c in chunks if c.get('chunk_id')]
        best['_chunk_count'] = len(chunks)

        merged.append(best)

    return merged
```

**合併策略：方案 B+（去重合併）**：
- 所有 chunk summary 都以「標題。」開頭 → 只保留一次標題
- 收集各 chunk 的代表句，去除重複
- 合併後上限 500 字
- 保留 `_chunk_ids` 列表，讓 reasoning 可取多 chunk 全文

```python
def _merge_summaries(summaries: List[str], max_length: int = 500) -> str:
    """去重合併：標題只留一次 + 各 chunk 代表句去重"""
    headline = _extract_headline(summaries[0])
    unique_sentences = []
    seen = set()
    for summary in summaries:
        for sent in _remove_headline(summary, headline):
            if sent not in seen and len(sent) > 10:
                seen.add(sent)
                unique_sentences.append(sent)
    merged = headline
    for sent in unique_sentences:
        if len(merged) + len(sent) + 1 > max_length:
            break
        merged += sent
    return merged
```

**合併結果欄位**：
```python
best['title'] = merged_name              # 去重合併的摘要（display + LLM context 用）
best['name'] = merged_name
best['_best_chunk_name'] = original_name  # 最高分 chunk 的原始 name（未來 Reranker 用）
best['_chunk_ids'] = [chunk_ids]          # 保留所有 chunk_id → Vault 全文查詢
best['_chunk_count'] = len(chunks)        # chunk 數量
```

**BM25 影響**：無。Qdrant text index 對個別 chunk 建索引；合併只影響 client-side BM25，有 length normalization（b=0.75）。

---

## P1：核心修正

### 3. Crawler `_mark_as_crawled` 順序修正

**問題**：`engine.py` L532 先 mark_as_crawled，L538 才 save。如果 save 失敗，文章被標記「已爬」但從未進入 TSV/Indexing → 永久遺失。

**修正**：
```python
# 之前（錯誤）：
self._mark_as_crawled(url, data)     # L532: 先標記
success = await self.pipeline.process_and_save(url, data)  # L538: 後存

# 之後（正確）：
success = await self.pipeline.process_and_save(url, data)  # 先存
if success:
    self._mark_as_crawled(url, data)  # 存成功才標記
    self.registry.remove_failed(url)
else:
    self._mark_failed(url, "save_error", "Pipeline save failed")
```

**改動檔案**：`code/python/crawler/core/engine.py`

---

### 4. Pipeline Reconciliation 工具

**問題**：Vault 寫入成功但 Qdrant 上傳失敗時，checkpoint 會跳過這些文章 → 搜尋不到。

**實作**：在 `pipeline.py` 加 `reconcile()` 方法：
```python
def reconcile(self, site: str = None, batch_size: int = 10000) -> ReconcileResult:
    """比對 Vault chunk_ids vs Qdrant point_ids，修復缺口（batch iterator 避免 OOM）"""
    missing_total = 0
    orphan_total = 0

    # Batch iterate: 分批比對，避免 1.8M chunks 一次載入記憶體
    for vault_batch in self.vault.iter_chunk_ids(site=site, batch_size=batch_size):
        qdrant_batch = self.qdrant.check_exists(vault_batch)
        missing = vault_batch - qdrant_batch

        if missing:
            chunks = self.vault.get_chunks_by_ids(missing)
            self.qdrant.upload_chunks(chunks, ...)
            missing_total += len(missing)

    return ReconcileResult(missing_fixed=missing_total, orphans_found=orphan_total)
```

**觸發方式**：pipeline CLI 加 `--reconcile` flag。可指定 `--site` 限定範圍。

**改動檔案**：`code/python/indexing/pipeline.py`

---

### 5. CrawledRegistry WAL + Timeout

**問題**：crawled_registry.db 未啟用 WAL mode，多 crawler 並行寫入可能 lock。

**修正**：
```python
# crawled_registry.py
self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False, timeout=30.0)
self._conn.execute("PRAGMA journal_mode=WAL")
```

**改動檔案**：`code/python/crawler/core/crawled_registry.py`

---

### 6. 停止條件常數統一

**問題**：`settings.py` 定義了 3 個常數但完全沒被引用。所有停止條件硬編碼在 engine.py。

**新 settings.py 常數**：
```python
# ===== 通用 =====
BLOCKED_CONSECUTIVE_LIMIT = 5       # 連續 N 次 403/429 回應後停止（次數）

# ===== Auto Mode =====
AUTO_DEFAULT_STOP_AFTER_SKIPS = 10  # 連續 N 個已爬取文章後停止（篇數）

# ===== Backfill Mode =====
BACKFILL_NOT_FOUND_LIMIT = 50       # 連續 N 個 404 後停止（次數）

# ===== Date Range - Sequential ID =====
SEQ_BUFFER_ZONE_MISS_LIMIT = 30     # Buffer zone 連續 404 後跳到 main zone（次數）
SEQ_MAIN_ZONE_SKIP_LIMIT = 200      # Main zone 連續已爬取後停止（篇數）
SEQ_SMART_STOP_IDS = 500            # 掃描 N 個 ID 無成功後停止（ID 數量）
SEQ_MAIN_ZONE_MISS_MIN = 50         # main_zone_miss_limit 下界（次數）
SEQ_MAIN_ZONE_MISS_MAX = 500        # main_zone_miss_limit 上界（次數）

# ===== Date Range - Date-based ID =====
DATE_MISS_PER_DAY = 15              # 每日連續 miss 後跳到下一天（次數）
DATE_DAYS_WITHOUT_SUCCESS = 10      # 連續 N 天無成功後停止（天數）
DATE_SMART_STOP_IDS = 500           # 掃描 N 個 ID 無成功後停止（ID 數量）
```

**刪除未用常數**：`CONSECUTIVE_TOO_OLD_LIMIT`, `CONSECUTIVE_FAIL_LIMIT`, `MAX_CONSECUTIVE_MISSES`

**改動檔案**：`crawler/core/settings.py`, `crawler/core/engine.py`（所有硬編碼值改為引用常數）

---

### 7. Data Lineage（task_id / batch_id）

**問題**：crawled_articles 表無法追蹤文章來自哪個 backfill 任務。

**SQL 修改**：
```sql
ALTER TABLE crawled_articles ADD COLUMN task_id TEXT;
ALTER TABLE crawled_articles ADD COLUMN batch_id TEXT;
CREATE INDEX idx_task ON crawled_articles(task_id);
```

**程式碼修改**：
- `crawled_registry.py`: `mark_crawled()` 加 `task_id` 參數
- `engine.py`: 傳遞 `task_id` 到 `mark_crawled()`

---

## P2：改進與文件

### 8. Blocked URL Retry 保守策略

**問題**：retry `blocked` URL 用正常的 concurrent_limit + delay，可能再次觸發封鎖。

**修正**：`run_retry()` 偵測到 `error_type == "blocked"` 時：
- `concurrent_limit = 1`（單線程）
- `delay_range` 加倍
- 每批之間額外等待 5 秒

**改動檔案**：`crawler/core/engine.py`

---

### 9. 文件修正（兩份 spec）

#### indexing-spec.md
- [ ] 修正 Qdrant payload 結構為新設計（P0 #1 的格式）
- [ ] 修正向量維度：統一為 1536（OpenAI text-embedding-3-small）
- [ ] 修正 L1211 的 payload 範例（刪除扁平化版本）
- [ ] 更新儲存估算（1536d → 6KB/vector，正確）
- [ ] 補充 overlap embedding_text 與 payload 的關係
- [ ] 補充 reconciliation 工具說明
- [ ] 更新停止條件章節，反映實際邏輯

#### crawler-dashboard-spec.md
- [ ] 修正 `/api/indexing/sources` 範例（刪除 setn, tvbs, chinatimes → 換成實際 6 個來源）
- [ ] 修正 `/api/indexing/stats` 範例同上
- [ ] 補充 WebSocket 效能優化章節的 retry backoff 說明
- [ ] 補充 Error Retry 的三層 backoff 機制說明
- [ ] 修正 API default limit 不一致（統一為 1000）
- [ ] 補充 moea 不支援 backfill 的說明
- [ ] 修正 Batch Backfill early-stop 條件數值

---

## 目前系統狀態（作為修改基準）

### 已爬取資料
- **126,145 篇文章**（UDN 93K, CNA 17K, LTN 14K, ESG_BT 1.6K, einfo 446）
- **157 個 TSV 檔案**（395 MB）
- **Local Qdrant：空的**（零向量，尚未跑 indexing pipeline）

### Retriever 目前配置
- 連接 Qdrant Cloud（AWS EU-WEST-2）
- Collection：`nlweb_collection`
- Embedding：OpenAI `text-embedding-3-small`（1536d）
- Payload：`url`（文章 URL）, `name`（標題）, `site`, `schema_json`（文章 metadata）

### 修改時機
Local Qdrant 是空的 → **payload 格式改動零成本**，不需要資料遷移。

---

## 已確認決策

- [x] Chunk Dedup 採方案 B+（去重合併），name 上限 500 字
- [x] 合併後保留 `_chunk_ids`，reasoning 可透過 Vault 取多 chunk 全文
- [x] 合併後保留 `_best_chunk_name`（原始最高分 chunk 的 name），供未來 Reranker 使用
- [x] Reconciliation 先做 CLI（`--reconcile` flag），batch iterator 10K/批避免 OOM
- [x] Payload 加 `keywords` 到頂層（Qdrant array match）+ `indexed_at` 時間戳
- [x] 停止條件常數加單位註釋
- [x] Point ID 冪等性已由 MD5(chunk_id) 保證，不需額外改動

---

## 外部審查紀錄（Gemini, 2026-02-06）

### 接受的建議
| 建議 | 處理方式 |
|------|---------|
| Reranker 影響 | 保留 `_best_chunk_name` 欄位 |
| Reconciliation 記憶體 | 改 batch iterator（10K/批） |
| `indexed_at` 時間戳 | 加到頂層 payload |
| `keywords` 到頂層 | 加到頂層（Qdrant array match） |
| 常數加單位 | 所有常數加註釋說明單位 |
| `task_id` 加到 Qdrant payload | 頂層欄位，支援 purge by task（filter delete） |
| datePublished 格式統一 | pipeline 構建 payload 時用 `TextProcessor.parse_iso_date()` 正規化 |

### 不採納 / 已處理
| 建議 | 理由 |
|------|------|
| Point ID 改 UUIDv5 | MD5(chunk_id) 已是 deterministic，功能等價 |
| URL 正規化 | 我們的 URL 由 parser 從 ID 構建，格式已 canonical |
| TSV 併發寫入 | 每個 task 寫獨立 TSV 檔，無競爭 |
| get_chunks_by_ids 效能 | Vault 是 SQLite（非 TSV），chunk_id 是 PK 索引查詢，不存在此問題 |
| task_id 加到 TSV 檔名 | TSV 是中間產物，已用 `source_month.tsv` 命名可追溯；不額外增加命名複雜度 |

### 注意事項（文件化）
- **Local ↔ Cloud 切換**：`config/config_retrieval.yaml` 中 `qdrant_url`（cloud）和 `qdrant_local` 二選一。Backfill 完成後需手動切換 `enabled: true/false`。
- **環境變數**：`QDRANT_URL` 和 `QDRANT_API_KEY` 控制 cloud 連線；local 不需要。

---

*建立：2026-02-06*
*更新：2026-02-06（加入 Gemini 審查建議）*
