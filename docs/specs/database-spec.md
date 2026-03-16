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

## Analytics 表

由 `analytics_db.py` + `query_logger.py` 管理。Async 改寫完成（2026-03-16）。

**完整規格**：見 `docs/specs/analytics-spec.md`（schema、API、資料流的 source of truth）。

以下為摘要。7 張表：

| 表 | 說明 | 每次搜尋寫入 |
|----|------|-------------|
| `queries` | 主查詢記錄（25 欄位，含 org_id, v2 ML 欄位） | 1 INSERT + 1 UPDATE |
| `retrieved_documents` | Retrieval 文件及分數（21 欄位） | N（每 doc 一列） |
| `ranking_scores` | Ranking 分數，多 method（17 欄位） | N x M（llm/xgboost/mmr） |
| `user_interactions` | 前端行為：click, dwell, scroll（12 欄位） | 非同步，使用者操作時 |
| `tier_6_enrichment` | Tier 6 API 呼叫記錄（10 欄位） | 選擇性 |
| `feature_vectors` | XGBoost 預計算特徵（32 欄位） | Phase B 實作 |
| `user_feedback` | 讚/踩評價（7 欄位） | 選擇性 |

### 待處理

1. ~~P0+P1: Async 改寫~~ — ✅ 完成（2026-03-16）
2. **P2: user_id/org_id NOT NULL** — blocker 已解除（搜尋已強制登入），待實作 ALTER TABLE
3. ~~P3: Schema cleanup~~ — ✅ 完成（ranking_scores 本就無 bm25_score 欄位，無需 rename）
4. ~~P4: SQLite 本地開發保留~~ — ✅ 完成

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
