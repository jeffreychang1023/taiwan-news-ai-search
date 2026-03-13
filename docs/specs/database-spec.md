# Database Specification

## Overview

單一 PostgreSQL instance，單一 database（`nlweb`），所有表在 `public` schema。

**PostgreSQL 17 + pgvector + pg_bigm**，運行於 Hetzner VPS（CAX31, 16GB RAM, ARM64）Docker container。

---

## 架構決策

### 單一 Database，不分庫不分 Schema

- 50M chunks + 20 orgs 規模，單一 PostgreSQL database 綽綽有餘
- Analytics 需要 JOIN articles/chunks，跨 database JOIN 需 dblink/FDW，不值得
- Schema 分離是組織工具不是擴展工具，增加 migration 複雜度
- VPS 50 max_connections，共用 connection pool 更省資源

### 多租戶策略

- **新聞文章（articles/chunks）**：公共資料，所有 org 共享，不需 org_id
- **User uploads（未來）**：`org_id` 欄位 + PostgreSQL RLS 隔離
- **Analytics**：`org_id` 欄位，per-org 用量統計（帳單依據）
- **Auth**：已有 org_id 設計

### 擴展路徑

```
目前規模        → table partitioning      → read replica        → 拆 database
(< 10M chunks)   (chunks 按 source/日期)   (搜尋走 replica)       (極端情況)
                  觸發：查詢 >100ms        觸發：QPS >100        觸發：TB 級+合規需求
```

每一步不需要改前面的決定，加就好。

---

## 表分類總覽

| 分類 | 表名 | 管理方式 | 狀態 |
|------|------|----------|------|
| **Search** | articles, chunks | `infra/init.sql` | 生產中 |
| **Auth** | organizations, users, org_memberships, invitations, refresh_tokens, login_attempts | Alembic migration `9df501ad` | 生產中 |
| **Session** | search_sessions, org_folders, org_folder_sessions, session_shares, user_preferences | Alembic migration `c1c6deac` | 生產中 |
| **Audit** | audit_logs | Alembic migration `a3f8c2e5` | 生產中 |
| **Analytics** | queries, retrieved_documents, ranking_scores, user_interactions, tier_6_enrichment | `analytics_db.py` CREATE IF NOT EXISTS | 待遷移至 VPS PG |
| **User Uploads** | user_sources, user_documents, user_chunks | 未建立 | 規劃中 |

---

## Search 表

### articles

新聞文章主表。由 indexing pipeline 寫入。

| 欄位 | 型別 | 說明 |
|------|------|------|
| id | BIGSERIAL PK | |
| url | TEXT UNIQUE | 文章 URL（dedup key） |
| title | TEXT | 標題 |
| author | TEXT | 作者（nullable） |
| source | TEXT | 來源（chinatimes, ltn, udn 等） |
| date_published | TIMESTAMPTZ | 發佈日期 |
| content | TEXT | 全文（Reasoning 用） |
| metadata | JSONB | 彈性欄位 |
| created_at | TIMESTAMPTZ | 寫入時間 |

**Indexes**: source (B-tree), date_published DESC (B-tree), author (partial, WHERE NOT NULL), title (pg_bigm GIN)

### chunks

文章分塊 + embedding。由 indexing pipeline 寫入。

| 欄位 | 型別 | 說明 |
|------|------|------|
| id | BIGSERIAL PK | |
| article_id | BIGINT FK→articles | |
| chunk_index | INTEGER | 在文章中的位置（0-based） |
| chunk_text | TEXT | 分塊文字（~170字/句號邊界） |
| embedding | vector(1024) | Qwen3-Embedding-4B 向量 |
| tsv | TEXT | pg_bigm LIKE 搜尋用 |
| created_at | TIMESTAMPTZ | |

**Indexes**: article_id (B-tree), embedding (IVFFlat, lists=1000, probes=50), tsv (pg_bigm GIN)

**UNIQUE**: (article_id, chunk_index)

---

## Auth 表

由 Alembic migrations 管理。詳細欄位見 `docs/specs/login-spec.md`。

| 表 | 用途 |
|----|------|
| organizations | B2B 組織（第一位 admin bootstrap 建立） |
| users | 使用者帳號（email/password） |
| org_memberships | 使用者 ↔ 組織關聯 |
| invitations | 員工邀請（admin 開帳、activation email） |
| refresh_tokens | JWT refresh token（rotation 機制） |
| login_attempts | 登入嘗試記錄（brute force 防護） |

## Session 表

| 表 | 用途 |
|----|------|
| search_sessions | 搜尋/研究對話記錄（含 conversation history, research report） |
| org_folders | 組織內資料夾 |
| org_folder_sessions | 資料夾 ↔ session 關聯 |
| session_shares | session 分享（user ↔ session） |
| user_preferences | 使用者偏好設定（per org） |

## Audit 表

| 表 | 用途 |
|----|------|
| audit_logs | 使用者操作審計（auth.login, session.create 等） |

---

## Analytics 表（待遷移）

目前由 `analytics_db.py` 管理，支援 SQLite/PostgreSQL 雙 DB。待整合至 VPS PostgreSQL。

### 待處理事項

1. **P0+P1: DB 整合 + Async 改寫（一起做）**
   - 從獨立 `ANALYTICS_DATABASE_URL`（Neon.tech）遷移至 VPS PostgreSQL（同一個 `nlweb` database）
   - 同時將 `analytics_db.py` 從 sync `psycopg.connect()` 改為 async `AsyncConnectionPool`（照 `auth_db.py` pattern）
   - 改動範圍：`analytics_db.py`、`analytics_handler.py`、`ranking_analytics_handler.py`、baseHandler 呼叫端
   - 風險低：analytics 是 write-mostly（記 log），不影響搜尋主路徑。寫入失敗不阻斷搜尋
   - 時機：全量 indexing 完成、pg_dump → VPS 時一起做
2. **P2: Login 整合** — `queries.user_id` 從 anonymous hash 改為真實 user_id（NOT NULL）+ 加 `org_id`（NOT NULL）。B2B only，無未登入用戶，不需 anonymous fallback。auth middleware 保證每個 request 都有身份。P0 做 DB 整合時先加 `org_id` 欄位（nullable），P2 實作時改為 NOT NULL
3. **P3: Schema cleanup** — `ranking_scores.bm25_score` rename 為 `text_search_score`（對齊 XGBoost feature rename）。P0 時順手做，一行 ALTER TABLE + handler query 更新
4. **P4: 保留 SQLite 本地開發** — `analytics_db.py` 的 SQLite/PostgreSQL 雙 DB 支援保留。改 schema 時兩邊（`_get_sqlite_schema()` / `_get_postgres_schema()`）一起更新。SQLite 檔案已加入 `.gitignore`（`data/analytics/*.db`）

### queries

| 欄位 | 型別 | 說明 |
|------|------|------|
| query_id | VARCHAR PK | |
| timestamp | DOUBLE PRECISION | epoch |
| user_id | VARCHAR | 目前是 anonymous hash，待改為真實 user_id |
| session_id | VARCHAR | |
| query_text | TEXT | 原始查詢 |
| decontextualized_query | TEXT | 去脈絡化查詢 |
| site | VARCHAR | |
| mode | VARCHAR | search / deep_research |
| latency_total_ms | DOUBLE PRECISION | |
| latency_retrieval_ms | DOUBLE PRECISION | |
| latency_ranking_ms | DOUBLE PRECISION | |
| latency_generation_ms | DOUBLE PRECISION | |
| num_results_* | INTEGER | retrieved / ranked / returned |
| cost_usd | DOUBLE PRECISION | LLM API 成本 |
| error_occurred | INTEGER | |

### retrieved_documents

每次查詢檢索到的文件及其分數。

### ranking_scores

每次查詢的排序分數（LLM、text_search、MMR、XGBoost、final）。XGBoost shadow mode 資料收集用。

### user_interactions

前端使用者行為（click, dwell_time, scroll_depth）。XGBoost training signal。

### tier_6_enrichment

Tier 6 API（Stock/Weather/Wikipedia）呼叫記錄。

---

## User Uploads 表（規劃中）

依賴 Login 系統 JWT 認證。詳見 `docs/decisions.md` User Data 段落。

| 表 | 用途 |
|----|------|
| user_sources | 使用者上傳的資料源元資料 |
| user_documents | 已解析文檔元資料 |
| user_chunks | 文本分塊（embedding 1024D，同新聞搜尋） |

所有表含 `org_id` 欄位，用 RLS 隔離。

---

## 連線管理

| 用途 | 連線方式 | 環境變數 |
|------|----------|----------|
| Search (retrieval) | async psycopg pool | `POSTGRES_CONNECTION_STRING` |
| Auth | async psycopg `AsyncConnectionPool` | `POSTGRES_CONNECTION_STRING` → `DATABASE_URL` fallback |
| Analytics | async psycopg `AsyncConnectionPool` | `POSTGRES_CONNECTION_STRING` → `DATABASE_URL` fallback |

三個模組統一優先讀 `POSTGRES_CONNECTION_STRING`。VPS 只需設定這一個環境變數。

---

## Docker 設定

```yaml
# docker-compose.production.yml
postgres:
  image: custom (PG17 + pgvector + pg_bigm)
  POSTGRES_DB: nlweb
  max_connections: 50
  shared_buffers: 4GB
  work_mem: 128MB
  effective_cache_size: 12GB
```

初始化：`infra/init.sql`（Search 表 + indexes）+ Alembic migrations（Auth/Session/Audit 表）

---

## 檔案對應

| 檔案 | 角色 |
|------|------|
| `infra/init.sql` | Search 表 schema + indexes（Docker 初次啟動） |
| `code/python/alembic/versions/` | Auth/Session/Audit 表 migrations |
| `code/python/core/analytics_db.py` | Analytics 表 schema + DB 抽象層 |
| `code/python/retrieval_providers/postgres_client.py` | Search 查詢（hybrid search） |
| `code/python/auth/auth_db.py` | Auth 查詢（async pool） |
| `docker-compose.production.yml` | PostgreSQL container 設定 |

---

*Created: 2026-03-12*
*Supersedes: db-switching-spec.md（已歸檔至 docs/archive/）*
