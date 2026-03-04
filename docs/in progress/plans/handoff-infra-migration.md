# Handoff: Infrastructure Migration + Hybrid Search

> 這份文件是 session 交接用的 context。請完整閱讀後再開始討論。

---

## 背景：兩個問題，一個解法

### 問題 1：偽 Hybrid Search

我們的搜尋架構是「偽 hybrid」：

```
現狀：
Query → Embedding → Qdrant vector search (top 500) → Python BM25 re-rank 同一批 500 篇 → post-filter → output
```

BM25 只是 re-ranker，不是獨立 retriever。keyword-heavy 查詢（作者名、法案名、專有名詞）如果不在 vector top-500 裡，就完全搜不到。這是作者搜尋失敗的根本原因。

正確的 hybrid search 需要兩路獨立 retrieval + fusion。

### 問題 2：架構過度複雜

目前使用 3 個資料庫：
- **Qdrant Cloud**：向量搜尋（語意）
- **SQLite**：文章全文儲存 + crawler registry
- **Neon PostgreSQL**：analytics / query log

加上 Render PaaS 做 web server，OpenAI API 做 embedding。每月成本 ~$30-50，且各元件間的資料流複雜。

### 解法：PostgreSQL 一體化 + VPS

外部顧問建議（且 CEO 已同意方向）：

1. **Embedding 模型**：從 OpenAI（繁中排名 #27）換成更好的模型
2. **資料庫**：全部整合到 PostgreSQL（pgvector 做向量搜尋 + tsvector 做全文搜尋）
3. **部署**：從 PaaS 搬到 Hetzner VPS，一台機器搞定
4. **關鍵洞察**：PostgreSQL 原生支援 vector search + full-text search，hybrid search 變成一個 SQL query 的事，不需要額外架構

---

## 已確認的決策

| 決策 | 結論 | 原因 |
|------|------|------|
| Embedding 模型 | **Qwen3-Embedding-4B**（開源，繁中 #6） | 97.05% hit rate vs OpenAI 90.44%。CEO 的 RTX 3060 6GB 跑得動（INT8）。8B 未有 benchmark 數據且 VRAM 風險高 |
| 資料庫 | **PostgreSQL + pgvector + tsvector** | 一個 DB 解決向量搜尋 + 全文搜尋 + analytics + 文章全文 |
| 部署 | **Hetzner VPS** | 月費 €15-22 全包，比目前便宜 |
| 遷移時機 | **現在**（無正式上線產品，有時間） | CEO 原話：「不用慢慢搬」 |

---

## 繁體中文 Embedding Benchmark（關鍵數據）

資料來源：外部顧問提供的實測 benchmark（繁體中文 retrieval task）

### Top 10 + 我們的模型

| 排名 | 模型 | Hit Rate | MRR | 維度 | 類型 | 備註 |
|------|------|----------|-----|------|------|------|
| #1 | Google gemini-embedding-001 | 98.77% | 93.79% | 3072 | API $0.15/1M | |
| #2 | Voyage voyage-3-large | 98.77% | 93.64% | 1024 | API $0.18/1M | |
| #5 | Cohere Embed 4 | 97.25% | 90.74% | 1536 | API $0.12/1M | 多模態 |
| **#6** | **Qwen3-Embedding-4B** | **97.05%** | **90.22%** | 2560 | **開源** | **我們選的** |
| #7 | Voyage voyage-3.5 | 96.65% | 90.06% | 1024 | API $0.06/1M | 性價比高 |
| #9 | 微軟 multilingual-e5-large | 95.79% | 88.50% | 1024 | 開源 | |
| **#11** | **bge-m3** | **95.62%** | **87.84%** | 1024 | **開源** | **我們目前本地方案** |
| #18 | Qwen3-Embedding-0.6B | 93.47% | 84.05% | 1024 | 開源 | 輕量版 |
| **#27** | **OpenAI 3-large (1536d)** | **90.21%** | **78.21%** | 1536 | API $0.13/1M | **我們目前線上方案** |

完整 benchmark（48 個模型）見本文件底部附錄。

---

## 技術評估摘要

### pgvector + PostgreSQL

**優點**：
- 一個 SQL query 做 hybrid search（vector similarity + text match + 結構化 filter）
- 作者搜尋 = `WHERE author = '郭又華'`，時間過濾 = `WHERE date >= X`
- tsvector + zhparser 做中文全文搜尋（成熟方案）
- 一個 DB 取代三個，維護成本大降

**隱憂**：
- VPS 規格需求比顧問建議的大：6M vectors × 1024D 需要 ~16-32GB RAM，不是 4GB
- HNSW index 建置需數小時，建置期間吃大量 RAM
- zhparser 不是 PostgreSQL 預設 extension，需手動安裝
- 自管 DB（備份、更新、監控）
- 未來 30M vectors（1000 萬篇）需升級到 64GB+ RAM

### Hetzner VPS 規格建議

| 方案 | RAM | SSD | 月費 | 評估 |
|------|-----|-----|------|------|
| CX23（顧問建議）| 4GB | 40GB | €3.49 | 放不下 6M vectors |
| CCX23 | 16GB | 160GB | €15.49 | 最低可用配置 |
| **CAX41 (ARM)** | **32GB** | **320GB** | **€21.49** | **建議配置，有餘裕** |

### Qwen3-Embedding-4B

- 維度可自訂 32-2560，我們用 1024 即可（與 bge-m3 相同，減少儲存）
- CEO 桌機 RTX 3060 6GB 可跑 INT8 推論（indexing 用）
- Query-time embedding 單一短 query，CPU 也能秒殺
- 需要用 transformers 或 sentence-transformers 載入

---

## 執行計畫

### 總覽

```
Phase 1: 本機驗證          Phase 2: 遷移準備         Phase 3: 上線
(CEO 桌機)                (改程式碼)                (Hetzner VPS)
───────────────          ───────────────          ───────────────
PostgreSQL Docker         改寫 retriever           開 VPS
Qwen3-4B 測試            改寫 indexing pipeline    部署 PostgreSQL
Hybrid search SQL         改寫 embedding 模組       全量資料匯入
品質對比 → 確認 OK        遷移腳本                  DNS / server 切換
                         XGBoost 確認/重訓
```

每個 Phase 之間有 go/no-go 檢查點。Phase 1 結果不好可以退回。

### Phase 1：本機驗證（目前階段）

**目的**：證明新方案比現在好，再投入大量開發時間。

**已確認決策**：
- PostgreSQL 本機用 **Docker**（避免 Windows 上裝中文分詞 extension 的痛苦）
- 驗證資料集：**CNA + LTN** 全量（幾十萬篇，夠測品質又不會太慢）
- Embedding 同時測 **Qwen3-4B** 和 **pplx-embed-v1-4B**（見下方說明）

四個子步驟：

| 步驟 | 驗證什麼 | 預估時間 | 依賴 |
|------|---------|---------|------|
| **S1: Qwen3-4B embedding** | RTX 3060 跑得動？速度多快？ | 半天 | 無 |
| **S2: PostgreSQL 環境** | pgvector + 中文分詞在 Docker 跑起來 | 半天 | 無 |
| **S3: 資料匯入 + Hybrid Search** | Schema 設計 → 匯入子集 → 寫 hybrid SQL | 1-2 天 | S1 + S2 |
| **S4: 品質對比** | 同樣 query，新舊系統搜尋結果比較 | 半天 | S3 |

S1 和 S2 可以同時做（互不依賴）。

**S1 細節**：
- INT8 量化後 VRAM 用量（預期 ~4-5GB，RTX 3060 = 6GB）
- Embedding 速度：每秒幾篇文章的 chunk
- 輸出維度設 1024（與 bge-m3 相同，減少儲存）
- 同時測 pplx-embed-v1-4B，用同一批繁中 query 比較

**S2 細節**：
- Docker Compose 起 PostgreSQL + pgvector + 中文分詞（zhparser 或 pg_jieba）
- 跟 VPS 環境一致，驗證過的設定可直接搬上去

**S3 細節**：
- Schema 大致結構：articles 表（文章 metadata）+ chunks 表（chunk embedding + tsvector）
- Hybrid search = 一個 SQL query 同時走 vector + tsvector + 結構化欄位

**S4 細節**：
- 20-30 個代表性 query（含作者搜尋、專有名詞、一般語意搜尋）
- 新舊系統各跑一次，人工比較

**Phase 1 成功標準**：hybrid search 結果明顯優於現有系統（特別是作者搜尋、專有名詞）。

### Phase 2：遷移準備（改程式碼）

**目的**：把現有系統的 Qdrant / BM25 / OpenAI 全部換掉。

主要改動：

| 改什麼 | 從 | 到 |
|--------|----|----|
| 向量搜尋 | Qdrant | PostgreSQL pgvector |
| 全文搜尋 | Python BM25 re-rank | PostgreSQL tsvector |
| Embedding | OpenAI API | Qwen3-4B（或 pplx-embed）本地推論 |
| 文章儲存 | SQLite | PostgreSQL |
| Analytics | Neon PostgreSQL | 同一個 PostgreSQL |

砍掉的程式碼：`core/bm25.py`、Qdrant 相關程式碼、OpenAI embedding 呼叫。

XGBoost ranker 的 BM25 feature 來源會從 Python BM25 score 變成 tsvector score，可能需要重新訓練。Phase 2 確認。

### Phase 3：上線

**目的**：搬到 Hetzner VPS 正式運行。

- 開 CAX41（32GB RAM, ARM, €21.49/月）
- 部署 PostgreSQL + 應用程式
- 全量 re-index（~200 萬篇，用選定的模型重新 embed）
- 切換 DNS，關掉 Render / Qdrant Cloud / Neon

**最終狀態**：

| 砍掉 | 保留 |
|------|------|
| Qdrant Cloud | PostgreSQL（統一 DB） |
| Neon PostgreSQL | Hetzner VPS（統一部署） |
| Render PaaS | 選定的 embedding 模型（本地推論） |
| OpenAI embedding API | Crawler（不變） |
| SQLite（文章儲存） | Chunking engine（不變） |
| Python BM25 | XGBoost + MMR ranking（微調） |

---

## pplx-embed-v1-4B（2026-02-26 發布，待測）

Perplexity 開源的 embedding 模型，底層就是 Qwen3 再 fine-tune。

| | pplx-embed-v1-4B | Qwen3-Embedding-4B |
|--|---|---|
| 參數量 | 4B | 4B |
| 維度 | 2560（可降） | 2560（可降） |
| 底層 | Qwen3 + Perplexity fine-tune | Qwen3 原版 |
| 授權 | MIT | Apache 2.0 |
| 訓練資料 | 250B tokens，30 語言，一半英文 | 未公開，阿里中文資料多 |
| MTEB Multilingual nDCG@10 | 69.66% | 69.60% |
| 繁中 benchmark | **未測** | 97.05% hit rate（#6） |

通用多語言表現打平，但繁中沒有數據。Phase 1 S1 一起測就知道。

---

## 現有系統關鍵檔案

| 元件 | 檔案 | 遷移影響 |
|------|------|---------|
| Qdrant 搜尋 | `retrieval_providers/qdrant.py` | 重寫為 PostgreSQL query |
| Python BM25 | `core/bm25.py` | 刪除，由 tsvector 取代 |
| Indexing pipeline | `indexing/pipeline.py` | 改寫 embedding 產生 + 寫入 PostgreSQL |
| Chunking | `indexing/chunking_engine.py` | 不變 |
| Analytics DB | `core/query_logger.py` | 改連線到同一個 PostgreSQL |
| 全文 DB | `core/fulltext_store.py`（如有）| 整合到 PostgreSQL |
| Embedding | `core/embedding.py` | 從 OpenAI API 改為 Qwen3-4B 本地推論 |
| XGBoost ranking | `core/xgboost_ranker.py` | 可能需調整 feature（BM25 score 來源改變） |
| MMR | `core/mmr.py` | 不變 |
| Server | `webserver/aiohttp_server.py` | 部署方式改變，程式碼可能不變 |

---

## 待討論 / 待規劃

### 已決定
- ~~Phase 1 本地驗證~~：已規劃（見上方執行計畫）
- ~~本機 PostgreSQL 安裝方式~~：Docker
- ~~驗證資料集~~：CNA + LTN
- ~~Embedding 候選~~：Qwen3-4B + pplx-embed-v1-4B 都測

### Phase 1 進行中會決定
1. **PostgreSQL schema 設計**：articles 表結構、index 策略、partition 策略
2. **Hybrid search SQL 設計**：vector score + text score 的權重怎麼調
3. **中文分詞選擇**：zhparser vs pg_jieba
4. **Qwen3-4B 整合方式**：sentence-transformers 還是直接 transformers？batch size？
5. **Embedding 最終選擇**：Qwen3-4B vs pplx-embed（測完決定）

### Phase 2 再處理
6. **遷移腳本**：從 Qdrant + SQLite 匯出 → 寫入 PostgreSQL
7. **XGBoost re-training**：BM25 feature 來源改變後需要重新訓練嗎？

### Phase 3 再處理
8. **Hetzner VPS 開機與設定**：OS 選擇、PostgreSQL 版本、security hardening

---

## CEO 溝通風格備註

- 直接、不廢話
- 中文為主
- 不要解釋他已經知道的東西
- 他不熟資料庫技術，需要用白話解釋 DB 相關概念
- 討論架構時用 CTO-CEO 模式（見 plan-discuss skill）
- 他偏好一次到位而非漸進式

---

## 附錄：完整繁中 Embedding Benchmark（48 模型）

| 排名 | 模型 | Hit Rate | MRR | 維度 | tokens 上限 | 類型 |
|------|------|----------|-----|------|------------|------|
| 1 | Google gemini-embedding-001 | 0.9877 | 0.9379 | 3072 | 2048 | API $0.15 |
| 2 | Voyage voyage-3-large | 0.9877 | 0.9364 | 1024 | 32000 | API $0.18 |
| 3 | Voyage voyage-multimodal-3 | 0.9751 | 0.9062 | 1024 | 32000 | API $0.12 |
| 4 | Voyage voyage-multilingual-2 | 0.9737 | 0.9034 | 1024 | 32000 | API $0.12 |
| 5 | Cohere Embed 4 | 0.9725 | 0.9074 | 1536 | 128000 | API $0.12 |
| 6 | Qwen3-Embedding-4B | 0.9705 | 0.9022 | 2560 | 32000 | 開源 |
| 7 | Voyage voyage-3.5 | 0.9665 | 0.9006 | 1024 | 32000 | API $0.06 |
| 8 | Voyage voyage-3 | 0.9654 | 0.8945 | 1024 | 32000 | API $0.06 |
| 9 | 微軟 multilingual-e5-large | 0.9579 | 0.8850 | 1024 | 512 | 開源 |
| 10 | Voyage voyage-3.5-lite | 0.9579 | 0.8844 | 1024 | 32000 | API $0.02 |
| 11 | 智源 bge-m3 | 0.9562 | 0.8784 | 1024 | 8192 | 開源 |
| 12 | 微軟 multilingual-e5-small | 0.9551 | 0.8723 | 384 | 512 | 開源 |
| 13 | 微軟 multilingual-e5-base | 0.9522 | 0.8694 | 768 | 512 | 開源 |
| 14 | Nomic Embed Text V2 | 0.9513 | 0.8674 | 768 | 512 | 開源 |
| 15 | Voyage voyage-3-lite | 0.9485 | 0.8625 | 512 | 32000 | API $0.02 |
| 16 | JinaAI jina-embeddings-v4 | 0.9465 | 0.8578 | 2048 | 32768 | 開源 |
| 17 | Cohere embed-multilingual-v3.0 | 0.9350 | 0.8541 | 1024 | 512 | API $0.10 |
| 18 | Qwen3-Embedding-0.6B | 0.9347 | 0.8405 | 1024 | 8192 | 開源 |
| 19 | Cohere embed-multilingual-light-v3.0 | 0.9330 | 0.8422 | 384 | 512 | API |
| 20 | JinaAI jina-embeddings-v3 | 0.9244 | 0.8255 | 1024 | 8192 | 開源 CC-BY-NC |
| 21 | Google Vertex text-multilingual-002 | 0.9216 | 0.8272 | 768 | 2048 | API $0.10 |
| 22 | infgrad/stella-base-zh-v2 | 0.9190 | 0.8194 | 768 | 1024 | 開源 |
| 23 | Chuxin-Embedding | 0.9167 | 0.8180 | 1024 | ? | 開源 |
| 24 | infgrad/stella-large-zh-v2 | 0.9161 | 0.8135 | 1024 | 1024 | 開源 |
| 25 | 智源 bge-base-zh-v1.5 | 0.9061 | 0.8034 | 768 | 512 | 開源 |
| 26 | 智源 bge-large-zh-v1.5 | 0.9052 | 0.7999 | 1024 | 512 | 開源 |
| 27 | OpenAI text-embedding-3-large | 0.9044 | 0.7895 | 3072 | 8191 | API $0.13 |
| 28 | OpenAI text-embedding-3-large (1536d) | 0.9021 | 0.7821 | 1536 | 8191 | API $0.13 |
| 29 | Voyage voyage-large-2-instruct | 0.8975 | 0.7830 | 1024 | 16000 | API $0.12 |
| 30 | 网易有道 bce-embedding-base_v1 | 0.8932 | 0.7781 | 768 | 512 | 開源 |
| 31 | 合合信息 acge_text_embedding | 0.8883 | 0.7783 | 1792 | 1024 | 開源 |
| 32 | infgrad/stella-mrl-large-zh-v3.5 | 0.8806 | 0.7774 | 1792 | 512 | 開源 |
| 33 | 智源 bge-small-zh-v1.5 | 0.8775 | 0.7660 | 512 | 512 | 開源 |
| 34 | 台智雲 ffm-embedding | 0.8763 | 0.7586 | 1536 | 2048 | API |
| 35 | 阿里巴巴 gte-Qwen2-1.5B-instruct | 0.8743 | 0.7308 | 1536 | 32000 | 開源 |
| 36 | JinaAI jina-embeddings-v2-base-zh | 0.8735 | 0.7600 | 768 | 8192 | 開源 |
| 37 | OpenAI text-embedding-3-small | 0.8683 | 0.7533 | 1536 | 8191 | API $0.02 |
| 38 | Mistral mistral-embed | 0.8571 | 0.7357 | 1024 | 8192 | API $0.10 |
| 39 | OpenAI text-embedding-ada-002 | 0.8569 | 0.7433 | 1536 | 8191 | API $0.10 |
| 40 | 阿里巴巴 gte-base-zh | 0.8563 | 0.7308 | 768 | 512 | 開源 |
| 41 | 阿里巴巴 gte-small-zh | 0.8563 | 0.7303 | 512 | 512 | 開源 |
| 42 | 数元灵 Dmeta-embedding-zh | 0.8488 | 0.7248 | 768 | 1024 | 開源 |
| 43 | 阿里巴巴 gte-large-zh | 0.8348 | 0.7027 | 1024 | 512 | 開源 |
| 44 | Google embeddinggemma-300m | 0.7612 | 0.6183 | 768 | 2048 | 開源 |
| 45 | minishlab m2v_multilingual_output | 0.6118 | 0.4740 | 256 | ? | 開源 |
| 46 | Cohere embed-english-v3.0 | 0.4901 | 0.3662 | 1024 | 512 | API（英文模型）|
| 47 | Nomic embed-text-v1.5 | 0.4821 | 0.3582 | 768 | 8192 | 開源（英文為主）|
| 48 | SBERT all-MiniLM-L6-v2 | 0.2599 | 0.1691 | 384 | 128 | 開源（英文為主）|
