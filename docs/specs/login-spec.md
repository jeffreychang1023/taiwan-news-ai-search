# Login System Specification

> **Owner**: NLWeb Team (接手自外部 dev)
> **Last Updated**: 2026-03-05
> **Source repo**: `c0925028920-cpu/taiwan-news-ai-search-RG`

---

## Table of Contents

- [Context](#context)
- [Architecture Decisions](#architecture-decisions)
- [Implementation Status](#implementation-status)
- [Part 1: Auth System](#part-1-auth-system)
- [Part 2: Session Management](#part-2-session-management)
- [Part 3: Security Hardening](#part-3-security-hardening)
- [Part 4: Data Migration](#part-4-data-migration)
- [Part 5+: Research Collaboration](#part-5-research-collaboration)
- [Infra Adaptation](#infra-adaptation)
- [Known Gaps](#known-gaps)
- [File Inventory](#file-inventory)
- [Environment Variables](#environment-variables)
- [Dependencies](#dependencies)
- [Cost Analysis](#cost-analysis)

---

## Context

系統轉型為 B2B 線上服務，需要：

1. 組織制 Email/Password 登入（取代已刪除的 OAuth）
2. Server-side 對話/偏好管理（取代 localStorage）
3. Email 服務（Resend）支援驗證、邀請、密碼重設
4. WebSocket chat 已移除（B2B 不需要，僅保留 SSE 搜尋串流）

### 前置清理（已完成）

- OAuth 系統（`oauth.py`、`config_oauth.yaml`）已刪除
- WebSocket chat（`chat/` 目錄 9 檔、`routes/chat.py`）已刪除
- 保留 `routes/conversation.py`（SSE 對話歷史 API）

---

## Architecture Decisions

### DB: PostgreSQL（統一）

原 spec 選用 Neon PostgreSQL（擴展 analytics DB）。Infra migration 後改為自建 PostgreSQL on Hetzner VPS。Auth tables 與 articles/chunks tables 共存於同一 DB。

### Token Strategy

| 類型 | 策略 | 時效 |
|------|------|------|
| Access Token | JWT (HS256), payload: `{user_id, email, name, org_id, role}` | 15 分鐘 |
| Refresh Token | `secrets.token_urlsafe(64)`, DB 存 SHA256 hash | 7 天 |
| Password | bcrypt hash | - |
| Brute Force | 同一 email 15 分鐘內失敗 5 次鎖定 | 15 分鐘 |

### Multi-tenancy

組織制：每個 user 屬於 1+ 個 organization，JWT 含 `org_id` + `role`。資料隔離靠 `WHERE org_id = $n`。

---

## Implementation Status

> 以下狀態基於 2026-03-05 對 RG repo 程式碼的審計結果。
> 標記規則：已驗證 = 程式碼存在且邏輯正確；未驗證 = spec 宣稱完成但程式碼不符或不存在。

| Phase | 內容 | 狀態 | 備註 |
|-------|------|------|------|
| 0A | 移除 OAuth | **已驗證** | 檔案確認刪除 |
| 0B | 移除 WebSocket Chat | **已驗證** | 檔案確認刪除 |
| 1A | DB Schema | **已驗證** | auth_db.py auto-create, 12 tables |
| 1B | Auth Service | **已驗證** | 14 public methods, bcrypt+JWT |
| 1B | Email Service | **已驗證** | 4 send methods (含 lockout) |
| 1C | Auth API Routes | **已驗證** | 8 auth + 6 org endpoints |
| 1D | Auth Middleware | **已驗證** | JWT 驗證 + dev bypass |
| 1E | user_id 模式修復 | **部分** | user_data.py OK; **baseHandler.py 未改**（仍用 query param） |
| 1F | 前端 Login UI | **已驗證** | AuthManager + modal + TEMP_USER_ID 移除 |
| 2A | Session Schema | **已驗證** | Alembic migration 存在 |
| 2B | Session API | **已驗證** | routes/sessions.py, 15 endpoints |
| 2C | Session Service | **已驗證** | JSONB append + 200KB 監控 |
| 2D | 前端遷移 | **已驗證** | SessionManager, localStorage 移除 |
| 2E | 組織隔離 | **部分** | user_qdrant_provider OK; **user_data_manager org_id filter 只有寫入沒有查詢** |
| 3A | Rate Limiting | **已驗證（值不同）** | 實際值比 spec 寬鬆 5-17 倍（見下方） |
| 3B | Audit Logs | **已驗證** | audit_service.py + routes/audit.py |
| 3C | CORS | **已驗證** | cors.py, ALLOWED_ORIGINS |
| 4A | Data Migration | **已驗證** | migrate_to_b2b.py 存在 |
| 5B | Session Sharing | **已驗證** | visibility + shared_with |
| Tests | 69 tests (31+14+24) | **不存在** | 3 個 test 檔案全部 404 |

---

## Part 1: Auth System

### 1A — DB Schema

**檔案**: `auth/auth_db.py` — AuthDB singleton, SQLite/PostgreSQL 雙支援, 啟動時 auto-create。

**Tables（12 張，跨所有 Sprint）**:

| Table | 說明 | Sprint |
|-------|------|--------|
| `organizations` | 組織 (id, name, slug, plan, max_members, settings) | 1 |
| `users` | 使用者 (id, email, password_hash, name, email_verified, tokens) | 1 |
| `org_memberships` | 組織成員 (user_id, org_id, role, status) | 1 |
| `invitations` | 邀請 (org_id, email, token, expires_at) | 1 |
| `refresh_tokens` | Refresh Token (token_hash, expires_at, revoked_at) | 1 |
| `login_attempts` | 登入嘗試 (email, ip_address, success, attempted_at) | 1 |
| `search_sessions` | 搜尋 Session (user_id, org_id, history, articles) | 3 |
| `org_folders` | 組織資料夾 | 3 |
| `org_folder_sessions` | Junction: folder-session | 3 |
| `session_shares` | Junction: session-share | 3 |
| `user_preferences` | 使用者偏好 (key-value JSONB) | 3 |
| `audit_logs` | 稽核日誌 | 5 |

**Alembic Migrations**:
- `9df501ad9a13` — baseline: 6 auth tables
- `c1c6deac2013` — session tables (5 tables)
- `a3f8c2e51d07` — audit_logs
- `b5e9d3f71a42` — infra tables (articles + chunks, 適配新 infra)

### 1B — Auth Service

**檔案**: `auth/auth_service.py` — 14 public methods

| 方法 | 已驗證 | 說明 |
|------|--------|------|
| `register_user(email, password, name)` | Yes | bcrypt hash + 驗證 email |
| `verify_email(token)` | Yes | email_verified = true |
| `login(email, password, ip)` | Yes | brute force check + JWT + refresh |
| `refresh_token(token)` | Yes | SHA256 比對 + 新 access token |
| `logout(refresh_token)` | Yes | 撤銷 refresh token |
| `forgot_password(email)` | Yes | 不洩漏 email 是否存在 |
| `reset_password(token, new_pw)` | Yes | 更新密碼 + 撤銷所有 refresh |
| `create_organization(name, admin_user_id)` | Yes | 建 org + admin membership |
| `invite_member(org_id, email, role, invited_by)` | Yes | 驗證 admin + 人數上限 |
| `accept_invitation(token, user_id)` | Yes | token + email match |
| `list_user_orgs(user_id)` | Yes | |
| `list_org_members(org_id, requester)` | Yes | 驗證是成員 |
| `remove_member(org_id, target, requester)` | Yes | admin only, 不可移除自己 |
| `get_user_by_id(user_id)` | Yes | 不含 password_hash |

### 1B — Email Service

**檔案**: `auth/email_service.py` — Resend (production) / console log (dev)

| 方法 | 說明 |
|------|------|
| `send_verification_email(email, token, name)` | 註冊驗證 |
| `send_password_reset_email(email, token, name)` | 密碼重設（1 小時） |
| `send_invitation_email(email, org_name, inviter_name, token)` | 組織邀請（7 天） |
| `send_lockout_notification(email, name)` | 帳號鎖定通知 |

### 1C — Auth API Routes

**檔案**: `webserver/routes/auth.py`

**Auth**:

| Method | Endpoint | 說明 |
|--------|----------|------|
| POST | `/api/auth/register` | 註冊 |
| GET | `/api/auth/verify-email?token=xxx` | 驗證 email |
| POST | `/api/auth/login` | 登入 (access_token + HttpOnly refresh cookie) |
| POST | `/api/auth/refresh` | 刷新 (cookie or body) |
| POST | `/api/auth/logout` | 登出 |
| GET | `/api/auth/me` | 目前使用者 |
| POST | `/api/auth/forgot-password` | 忘記密碼 |
| POST | `/api/auth/reset-password` | 重設密碼 |

**Organization**:

| Method | Endpoint | 說明 |
|--------|----------|------|
| POST | `/api/org` | 建立組織 |
| GET | `/api/org` | 列出組織 |
| POST | `/api/org/{id}/invite` | 邀請 |
| GET | `/api/org/{id}/members` | 列出成員 |
| DELETE | `/api/org/{id}/members/{user_id}` | 移除成員 |
| POST | `/api/org/accept-invite` | 接受邀請 |

**Cookie 設定**: `Set-Cookie: refresh_token` (HttpOnly, Secure=request.secure, SameSite=Lax, path=/api/auth)

### 1D — Auth Middleware

**檔案**: `webserver/middleware/auth.py` — 完整重寫

- Token 來源優先順序: Bearer header > cookie > query param (GET only)
- JWT 解碼失敗 -> 401（非靜默放行）
- JWT_SECRET 未設定 -> 500
- `request['user']` 含 user_id, org_id, role, authenticated
- Dev bypass: `NLWEB_DEV_AUTH_BYPASS=true` 時 no-token 可進入 (authenticated=False)
- `/ask` 目前仍在 PUBLIC_ENDPOINTS（尚未實施 auth）

### 1E — user_id 修復

| 檔案 | 狀態 | 說明 |
|------|------|------|
| `webserver/routes/user_data.py` | Done | 從 `request['user']['id']` 取值 |
| `core/baseHandler.py` | Done | auth middleware soft-auth + api.py 注入至 query_params |
| `storage_providers/qdrant_storage.py` | Done (將作廢) | user_id filter — Qdrant 在 infra migration 後移除 |

### 1F — 前端 Login UI

**已完成**:
- AuthManager class (login, register, refreshToken, logout, authenticatedFetch)
- Request Queue 機制 (多個 401 同時觸發時只 refresh 一次)
- Login/Register modal
- TEMP_USER_ID 全部移除
- SSE 斷線重連 + token refresh

---

## Part 2: Session Management

### 2A — Schema

`search_sessions` 表（見 1A 的完整 table list）。Junction tables 取代原設計的 UUID[]。

### 2B-2C — Session API + Service

**API**: `webserver/routes/sessions.py` — 15 endpoints (CRUD + migrate + feedback + export + sharing)
**Service**: `core/session_service.py` — JSONB append pattern, 200KB size 監控

### 2D — 前端遷移

SessionManager class 取代 localStorage。首次登入觸發 `POST /api/sessions/migrate`。

### 2E — 組織隔離

| 模組 | 狀態 | 說明 |
|------|------|------|
| JWT org_id 注入 | Done | middleware 層 |
| user_qdrant_provider.py | Done (將作廢) | Qdrant 移除後需重寫 |
| user_data_manager.py | Done | create/list/delete 全部支援 org_id |
| query_logger.py | Done | queries schema + log_query_start 已加 org_id |

---

## Part 3: Security Hardening

### 3A — Rate Limiting

**檔案**: `webserver/middleware/rate_limit.py`

| Endpoint | 目前實際值 | 說明 |
|----------|-----------|------|
| `/api/auth/register` | 5/hr | ✅ 已調緊（原 50/hr） |
| `/api/auth/forgot-password` | 3/hr | ✅ 已調緊（原 50/hr） |
| `/api/auth/login` | 10/min | ✅ 已調緊（原 60/min） |

Rate limit 已於 2026-03-05 infra adaptation 時調整至 production 值。

### 3B — Audit Logs

**已完成**: `core/audit_service.py` + `webserver/routes/audit.py`
- Alembic migration `a3f8c2e51d07`
- fire-and-forget (`asyncio.create_task`)

### 3C — CORS

**已完成**: `webserver/middleware/cors.py`
- `ALLOWED_ORIGINS` env var
- Dev mode 允許 localhost
- 已修復 wildcard + credentials bug

---

## Part 4: Data Migration

**檔案**: `scripts/migrate_to_b2b.py` (idempotent)

原設計遷移 Qdrant conversations + user_data + analytics。Infra migration 後 Qdrant 移除，遷移範圍需重新評估。

---

## Part 5+: Research Collaboration

| 功能 | 狀態 |
|------|------|
| Session Export (JSON/CSV) | 已在 session_service.py |
| RIS export + citation | TODO |
| Session Sharing (visibility) | Done |
| 組織管理 UI + 邀請流程 | Done |

---

## Infra Adaptation

> Login system 實作於 infra migration 前。以下列出需要適配的項目。

### 高衝突：Qdrant 移除

Infra migration 將 Qdrant 替換為 PostgreSQL pgvector。以下 login 修改**全部作廢**，需重寫：

| 檔案 | Login 做了什麼 | 需要改成什麼 |
|------|---------------|-------------|
| `storage_providers/qdrant_storage.py` | 加 user_id filter | 在新的 PostgreSQL retriever 中實作 user_id filter |
| `retrieval_providers/user_qdrant_provider.py` | 加 org_id filter | 在新的 PostgreSQL retriever 中實作 org_id filter |

### 中衝突：DB 統一

| 項目 | Login 假設 | 新 Infra 實際 | 適配 | 狀態 |
|------|-----------|--------------|------|------|
| DB 連線 | `ANALYTICS_DATABASE_URL` (Neon) | `DATABASE_URL` (自建 PostgreSQL) | env var 改為 `DATABASE_URL`，保留 fallback | ✅ Done |
| Connection pool | 每次 query 新連線 | `psycopg_pool.AsyncConnectionPool` | auth_db.py 改用 pool (min=1, max=5) | ✅ Done |
| Schema 管理 | Alembic (auth + session + audit) | init.sql (articles + chunks) | 新增 Alembic migration `b5e9d3f71a42` 統一管理 | ✅ Done |
| Table 共存 | 12 張 auth/session 表 | articles + chunks 表 | 確認無 naming conflict | ✅ OK |

### 低衝突：部署環境

| 項目 | Login 假設 | 新 Infra | 適配 |
|------|-----------|---------|------|
| SSL | Render 自帶 HTTPS | Hetzner VPS | 自建 Let's Encrypt |
| Cookie Secure | `Secure=request.secure` | 需確保 HTTPS | 部署時處理 |
| CORS origin | Render domain | Hetzner domain | 改 `ALLOWED_ORIGINS` |
| BASE_URL | Render URL | 新 domain | 改 env var |
| Middleware | aiohttp middleware | 不變 | 直接合併 |
| 前端 | aiohttp static files | 不變 | 直接合併 |

---

## Known Gaps

> 程式碼審計發現的問題。合併前需逐一處理。

### Must Fix

| # | 問題 | 嚴重度 | 說明 |
|---|------|--------|------|
| 1 | **Tests 不存在** | High | Spec 宣稱 69 tests，repo 裡 0 個 test 檔案。需重寫 |
| 2 | ~~baseHandler.py 未改~~ | ~~High~~ | auth middleware soft-auth + api.py 注入 user_id/org_id（2026-03-05） |
| 3 | ~~Rate limit 過寬~~ | ~~Medium~~ | ✅ 已調緊至 production 值（2026-03-05） |
| 4 | ~~org_id 查詢 filter 缺失~~ | ~~Medium~~ | list/delete 已加 org_id filter（2026-03-05） |
| 5 | ~~query_logger org_id~~ | ~~Medium~~ | queries schema + log_query_start 已加 org_id（2026-03-05） |

### Completed (Code Review 2026-03-05)

| # | 修復項目 | 類型 |
|---|----------|------|
| M1 | rate_limit_middleware 未註冊 → 加入 middleware __init__ | MUST FIX |
| M2 | /api/org/accept-invite 不應為 public endpoint → 移除 | MUST FIX |
| M3 | email HTML template injection → html.escape | MUST FIX |
| M4 | _pg_execute autocommit=True 破壞 transaction → 改 conn.commit() | MUST FIX |
| S5 | Boolean `= 1` 在 PG 不相容 → 全面參數化 `= ?` + True/False | SHOULD FIX |
| S6 | JWT_SECRET 長度檢查 → startup warning if < 32 chars | SHOULD FIX |
| S7 | _adapt_query_pg JSONB `?` 衝突 → 加 TODO 註解 | SHOULD FIX |
| S8 | CSV formula injection → _csv_safe() sanitizer | SHOULD FIX |
| S9 | parseInt 無 try/except → sessions.py + audit.py 加 400 回傳 | SHOULD FIX |
| S10 | PG JSONB append 無 size check → append_message/articles 加檢查 | SHOULD FIX |

### Deferred (Code Review 2026-03-05)

> 以下為 code review 發現但目前不急、或需要較大重構才能解決的項目。

| # | 問題 | 理由 | 優先度 |
|---|------|------|--------|
| D1 | 雙 DB pool（auth_db + analytics_db）連線浪費 | 需統一 DB layer 重構，Infra Migration 時一起處理 | Low |
| D2 | 雙 schema 管理（Alembic + initialize() 手動 DDL） | 目前運作正常，統一需要設計遷移策略 | Low |
| D3 | localStorage 存 JWT token（XSS 風險） | 需前端重構為 httpOnly cookie，影響整個前端 auth flow | Medium |
| D4 | org_id 寫入 JWT，revoke 有延遲 | JWT 天生限制，需 token blacklist 機制，複雜度高 | Low |
| D5 | login_attempts 表無 cleanup 機制 | 資料增長慢，可在 Infra Migration 時加 pg_cron | Low |
| D6 | _windows dict 記憶體洩漏（rate_limit） | 需改用 TTL cache 或 Redis，Production 再處理 | Low |
| D7 | email_service 每次 import time 讀 env var | 功能正確，hot reload 情境才有問題 | Very Low |

### Will Be Invalidated by Infra Migration

| # | 問題 | 說明 |
|---|------|------|
| 6 | qdrant_storage.py 修改 | Qdrant 移除後作廢 |
| 7 | user_qdrant_provider.py 修改 | 同上 |
| 8 | migrate_to_b2b.py 範圍 | Qdrant conversation 遷移不再適用 |

---

## File Inventory

### 新增的檔案（從 RG repo 合併）

| 檔案 | 已驗證 |
|------|--------|
| `auth/__init__.py` | Yes |
| `auth/auth_db.py` | Yes |
| `auth/auth_service.py` | Yes |
| `auth/email_service.py` | Yes |
| `webserver/routes/auth.py` | Yes |
| `webserver/routes/sessions.py` | Yes |
| `webserver/routes/audit.py` | Yes |
| `webserver/middleware/rate_limit.py` | Yes (已調緊) |
| `webserver/middleware/cors.py` | Yes |
| `core/session_service.py` | Yes |
| `core/audit_service.py` | Yes |
| `alembic/` + `alembic.ini` | Yes |
| `scripts/migrate_to_b2b.py` | Yes |

### 已修改的檔案（需 merge 進主 repo）

| 檔案 | 已驗證 | 注意事項 |
|------|--------|---------|
| `webserver/routes/__init__.py` | Yes | 加入 auth/sessions/audit routes |
| `webserver/middleware/auth.py` | Yes | 完整重寫 |
| `webserver/aiohttp_server.py` | Yes | 移除 chat 初始化 |
| `core/config.py` | Yes | 移除 OAuth config |
| `webserver/routes/user_data.py` | Yes | user_id 從 request['user'] |
| `static/news-search-prototype.html` | Yes | Login modal + org modal |
| `static/news-search.js` | Yes | AuthManager + SessionManager |
| `static/news-search.css` | Yes | Modal styles |

### 需要但不存在的檔案

| 檔案 | 說明 |
|------|------|
| `tests/test_auth_service.py` | 需重寫 |
| `tests/test_auth_middleware.py` | 需重寫 |
| `tests/test_session_service.py` | 需重寫 |

### 刪除的檔案（已確認）

| 檔案 |
|------|
| `chat/` (9 files) |
| `webserver/routes/chat.py` |
| `webserver/routes/oauth.py` |
| `config/config_oauth.yaml` |

---

## Environment Variables

| 變數 | 說明 | 狀態 | Infra 適配 |
|------|------|------|-----------|
| `DATABASE_URL` | 統一 DB URL | 新增 | 取代 ANALYTICS_DATABASE_URL |
| `JWT_SECRET` | JWT 簽名密鑰 | 已使用 | 不變 |
| `RESEND_API_KEY` | Resend API key | 已使用（可選） | 不變 |
| `RESEND_FROM_EMAIL` | 發信地址 | 已使用 | 不變 |
| `BASE_URL` | 系統 base URL | 已使用 | 改為新 domain |
| `NLWEB_DEV_AUTH_BYPASS` | 開發模式跳過認證 | 已使用 | 不變 |
| `ALLOWED_ORIGINS` | CORS 允許 origin | 已使用 | 改為新 domain |

---

## Dependencies

| 套件 | 用途 | 狀態 |
|------|------|------|
| `bcrypt` | 密碼 hash | 已使用 |
| `PyJWT` | JWT token | 已使用 |
| `resend` | Email 發送 | 已使用（可選） |
| `alembic` | DB migration | 已使用 |
| `psycopg` | Async PostgreSQL | 已使用 |

---

## Cost Analysis

| 階段 | 月費 | 說明 |
|------|------|------|
| 開發期 | $0 | Free Tier + dev console email |
| Early B2B (<50 users) | ~$1/月 | 只有 domain 成本（DB 已含在 Hetzner VPS） |
| Growth (50-500 users) | ~$20/月 | Resend Pro $20（DB 已含在 VPS） |
| Scale (500+ users) | ~$100+/月 | Resend Business + 可能需升級 VPS |

注：原 spec 包含 Neon PostgreSQL 費用。Infra migration 後 DB 已含在 Hetzner VPS 月費中，不另計。
