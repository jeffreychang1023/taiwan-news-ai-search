# Phase 2: Infrastructure Migration — Implementation Design

> Date: 2026-03-05 | Status: Approved by CEO | Prerequisite: Phase 1 S1-S4 all PASS

---

## Goal

Replace Qdrant + Python BM25 + OpenAI embedding with PostgreSQL hybrid search (pgvector + pg_bigm) + Qwen3-4B local embedding. Union merge strategy (no score weighting at retrieval).

---

## Key Discovery: postgres_client.py Already Exists

`retrieval_providers/postgres_client.py` (823 lines) already implements:
- `RetrievalClientBase` interface (same as qdrant.py)
- psycopg3 AsyncConnectionPool with retry logic
- Vector search via pgvector
- upload_documents, delete_documents_by_site, search_by_url

**BUT** it uses old schema (single flat `documents` table with id/url/name/schema_json/site/embedding). Needs adaptation to new `articles + chunks` schema and hybrid search.

---

## Architecture Change

### Before (current)
```
Query → OpenAI Embedding API → Qdrant Vector Search (top-500)
                                       ↓
                              Python BM25 re-rank same 500
                                       ↓
                              LLM → XGBoost → MMR
```

### After (target)
```
Query → Qwen3-4B Local Embedding → PostgreSQL Vector Search (top-N)
                                             ↓
                                   PostgreSQL Text Search (top-N)  [independent path]
                                             ↓
                                     Union merge (deduplicate)
                                             ↓
                                     LLM → XGBoost → MMR
```

---

## Track 1: Search Path

### 1a. Adapt postgres_client.py for new schema

**Current schema** (old, in postgres_client.py):
```sql
-- Single table: documents(id, url, name, schema_json, site, embedding)
```

**New schema** (from infra/init.sql):
```sql
-- articles(id, url, title, author, source, date_published, content, metadata, created_at)
-- chunks(id, article_id FK, chunk_index, chunk_text, embedding vector(1024), tsv text)
```

**Changes needed**:
- search(): Vector search on chunks table, JOIN articles for metadata
- search(): Add text search on chunks.tsv + articles.title using pg_bigm LIKE
- search(): Union merge both result sets (Decision: 聯集法)
- search(): Support author filter via `articles.author LIKE`
- search(): Support date filter via `articles.date_published`
- search(): Set `ivfflat.probes = 20` per session
- upload_documents(): Adapt to articles+chunks schema
- Result format: Must match existing [url, schema_json, name, site] format for downstream compatibility
- delete_documents_by_site(): Change to `DELETE FROM articles WHERE source = %s` (CASCADE deletes chunks)

### 1b. Add Qwen3-4B local embedding provider

**In `embedding_providers/qwen3_embedding.py`**:
- Load Qwen3-Embedding-4B INT8 via sentence-transformers (same as S3 pipeline)
- Singleton pattern (load model once, reuse)
- For query-time: `model.encode(text, prompt_name="query")` — single short text, fast even on CPU
- Dimension: 1024

**In `core/embedding.py`**:
- Add `qwen3` provider branch in `get_embedding()` and `batch_get_embeddings()`

**In `config/config_embedding.yaml`**:
- Add qwen3 provider config

### 1c. Remove BM25 and clean up references

- Delete `core/bm25.py`
- Remove `from core.bm25 import BM25Scorer` from qdrant.py (file being replaced anyway)
- Update `core/xgboost_ranker.py` and `training/feature_engineering.py`:
  - `bm25_score` feature → rename to `text_search_score` (from pg_bigm similarity)
  - Keep feature index stable for XGBoost compatibility (shadow mode, never trained)

---

## Track 2: Data Path

### 2a. Adapt indexing/pipeline.py

**Current flow**: TSV → Ingestion → QualityGate → Chunking → QdrantUploader + VaultStorage(SQLite)

**New flow**: TSV → Ingestion → QualityGate → Chunking → PostgreSQLUploader

**Changes**:
- Replace `QdrantUploader` import with new PostgreSQL uploader
- Replace `VaultStorage` (SQLite) — articles now stored in PostgreSQL
- Embedding: Use Qwen3-4B local instead of OpenAI API
- Write articles to `articles` table, chunks to `chunks` table
- Reuse proven logic from `infra/s3_data_pipeline.py` (already validated with 40K articles)

### 2b. Analytics (minimal change)

- `core/analytics_db.py` already supports both SQLite and PostgreSQL
- For unified DB: just point ANALYTICS_DATABASE_URL to the same PostgreSQL instance
- Phase 2 plan item: add `system_version` field to queries table (defer to after migration)

---

## Files Changed Summary

| File | Action | Track |
|------|--------|-------|
| `retrieval_providers/postgres_client.py` | Heavy edit (new schema + hybrid search) | T1 |
| `embedding_providers/qwen3_embedding.py` | New file | T1 |
| `core/embedding.py` | Add qwen3 provider | T1 |
| `config/config_embedding.yaml` | Add qwen3 config | T1 |
| `config/config_retrieval.yaml` | Switch endpoint to postgres | T1 |
| `core/bm25.py` | Delete | T1 |
| `core/xgboost_ranker.py` | Rename bm25_score → text_search_score | T1 |
| `training/feature_engineering.py` | Rename bm25_score → text_search_score | T1 |
| `indexing/pipeline.py` | Replace Qdrant+SQLite with PostgreSQL | T2 |
| `indexing/qdrant_uploader.py` | Replace with postgresql_uploader.py | T2 |
| `indexing/dual_storage.py` | Remove SQLite vault (articles in PG) | T2 |

**Not changed**: LLM reasoning, XGBoost model, MMR, Frontend, Crawler parsers, Chat

---

## Verification

After both tracks complete:
1. Start server with PostgreSQL backend
2. Run S4 test queries through the full pipeline (not just raw SQL)
3. Verify: author search works, hybrid results appear, LLM ranking runs
4. Check XGBoost shadow mode still logs features correctly

---

## Decisions Applied

- **Union merge** (not weighted score) — Decision 2026-03-05
- **IVFFlat** (not HNSW) — Decision 2026-03-04
- **Qwen3-4B INT8** — Decision 2026-03-04
- **pg_bigm** (not zhparser) — Decision 2026-03-04
