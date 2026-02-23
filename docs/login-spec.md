# Login System Specification & Implementation Tracker

> **Source**: 整合自 `docs/使用者登入系統與對話管理參考計畫0209.md` 原始規劃，加上實際實作紀錄。
> **Last Updated**: 2026-02-12

---

## Table of Contents

- [Context](#context)
- [Implementation Status Summary](#implementation-status-summary)
- [Part 0: Pre-cleanup](#part-0pre-cleanup)
- [Part 1: Auth System](#part-1auth-system)
- [Part 2: Session Management](#part-2session-management)
- [Part 3: Security Hardening](#part-3security-hardening)
- [Part 4: Data Migration](#part-4data-migration)
- [Part 5+: Research Collaboration](#part-5research-collaboration)
- [Sprint Schedule](#sprint-schedule)
- [File Inventory](#file-inventory)
- [Environment Variables](#environment-variables)
- [Dependencies](#dependencies)
- [Verification Checklist](#verification-checklist)

---

## Context

目前系統以單機開發為主，user ID 全靠 `TEMP_USER_ID = 'demo_user_001'` hardcode（前端 7 處），搜尋歷史存 localStorage（`taiwanNewsSavedSessions` + `taiwanNewsFolders`），API 端點以 query param 傳 `user_id`（不安全）。現有 OAuth（GitHub/Google）登入已不需要，將移除。轉為 B2B 線上服務需要：

1. 組織制的 Email/Password 登入系統（取代 OAuth）
2. Server-side 對話/偏好管理，取代 localStorage
3. Email 服務（Resend）支援驗證、邀請、密碼重設
4. 移除 WebSocket chat 功能（B2B 場景不需要，僅保留 SSE 搜尋串流）

### DB 選擇：Neon PostgreSQL（擴展現有）

| 選項 | 優點 | 缺點 | 結論 |
|------|------|------|------|
| **Neon PostgreSQL** | 已在用（analytics）、psycopg 已裝、RLS 支援多租戶、零新基建 | 需自建 auth 邏輯 | **採用** |
| Supabase | 內建 Auth + RLS | 額外服務、供應商鎖定 | 過度 |
| AWS RDS / GCP Cloud SQL | 企業級 | 早期階段太貴 | 太早 |
| MongoDB Atlas | 彈性 schema | 關聯型 org/user 資料不適合 | 不合 |

**理由**：已有 `ANALYTICS_DATABASE_URL` 連 Neon，`analytics_db.py` 有 SQLite/PostgreSQL 雙支援 pattern 可複用。同一個 DB 加新 table 即可。

---

## Implementation Status Summary

| Sprint | Phase | 狀態 | 說明 |
|--------|-------|------|------|
| Sprint 0 | Phase 0A — 移除 OAuth | :white_check_mark: **完成** | oauth.py、config_oauth.yaml 已刪除，config.py 已清理 |
| Sprint 0 | Phase 0B — 移除 WebSocket Chat | :white_check_mark: **完成** | chat/ 目錄（9 檔）、routes/chat.py 已刪除 |
| Sprint 1 | Phase 1A — DB Schema | :yellow_circle: **部分完成** | auth_db.py 用 auto-create，尚未導入 Alembic |
| Sprint 1 | Phase 1B — Auth Service | :white_check_mark: **完成** | auth_service.py 所有核心方法已實作 |
| Sprint 1 | Phase 1B — Email Service | :white_check_mark: **完成** | email_service.py（Resend + dev console） |
| Sprint 1 | Phase 1C — Auth API Routes | :white_check_mark: **完成** | routes/auth.py 所有端點已註冊 |
| Sprint 2 | Phase 1D — Auth Middleware | :white_check_mark: **完成** | 完整重寫，JWT 驗證 + org_id/role |
| Sprint 2 | Phase 1E — 修復 user_id 模式 | :yellow_circle: **部分完成** | user_data.py 已改用 request['user']['id']，baseHandler.py 仍用 query param |
| Sprint 2 | Phase 1F — 前端 Login UI | :red_circle: **未開始** | AuthManager + TEMP_USER_ID 替換 |
| Sprint 3 | Phase 2A — Session Schema | :red_circle: **未開始** | search_sessions + org_folders + user_preferences |
| Sprint 3 | Phase 2B — Session API | :red_circle: **未開始** | routes/sessions.py |
| Sprint 3 | Phase 2C — Session Service | :red_circle: **未開始** | session_service.py |
| Sprint 3 | Phase 2D — 前端遷移 | :red_circle: **未開始** | localStorage -> API |
| Sprint 4 | Phase 2E — 組織隔離 | :red_circle: **未開始** | org_id filter everywhere |
| Sprint 4 | Phase 3A — Rate Limiting | :red_circle: **未開始** | |
| Sprint 5 | Phase 3B — Audit Logs | :red_circle: **未開始** | audit_service.py |
| Sprint 5 | Phase 3C — CORS | :red_circle: **未開始** | |
| Sprint 5 | Phase 4A — Data Migration | :red_circle: **未開始** | migrate_to_b2b.py |
| Sprint 5 | Phase 5A — Session Export | :red_circle: **未開始** | CSV/RIS/citations |
| Sprint 5 | Phase 5B — Session Sharing | :red_circle: **未開始** | visibility + shared_with |

---

## Part 0：Pre-cleanup

### Phase 0A — 移除 OAuth :white_check_mark: DONE

**已刪除檔案：**

| 檔案 | 說明 |
|------|------|
| `code/python/webserver/routes/oauth.py` | OAuth 路由（GitHub/Google callback、token exchange） |
| `config/config_oauth.yaml` | OAuth provider 設定 |

**已修改檔案：**

| 檔案 | 修改 |
|------|------|
| `webserver/routes/__init__.py` | 移除 `setup_oauth_routes` import 和呼叫 |
| `webserver/middleware/auth.py` | PUBLIC_ENDPOINTS 移除 OAuth 端點，改為新 auth 端點 |
| `core/config.py` | 移除 `config_oauth.yaml` 路徑、`load_oauth_config()` 呼叫和方法 |

**實作筆記**：middleware 的 JWT 驗證已從 `CONFIG.oauth_session_secret` 改為 `JWT_SECRET` 環境變數。

### Phase 0B — 移除 WebSocket Chat :white_check_mark: DONE

**已刪除：**

| 檔案/目錄 | 說明 |
|-----------|------|
| `code/python/chat/`（整個目錄，9 個檔案） | WebSocket chat 基礎設施 |
| `code/python/webserver/routes/chat.py` | WebSocket route handlers |

**已修改：**

| 檔案 | 修改 |
|------|------|
| `webserver/routes/__init__.py` | 移除 `setup_chat_routes` import 和呼叫 |
| `webserver/aiohttp_server.py` | 移除 `_initialize_chat_system()` 方法、呼叫點、shutdown 清理 |
| `webserver/middleware/auth.py` | 移除 WebSocket path 特殊處理 |

**保留（不動）**：`webserver/routes/conversation.py` — SSE 對話歷史 API（`/conversation`、`/userConversations`、`/api/conversation/delete`）

---

## Part 1：Auth System

### Phase 1A — DB Schema :yellow_circle: Partially Done

**已實作**（`auth/auth_db.py`，auto-create 模式）：

```
auth/auth_db.py    # AuthDB singleton，SQLite/PostgreSQL 雙支援
                   # 複用 analytics_db.py 的 pattern
                   # 啟動時自動建表（_init_database）
```

**已建立的表：**

| Table | SQLite Type | PostgreSQL Type | 說明 |
|-------|-------------|-----------------|------|
| `organizations` | TEXT PK | UUID PK | 組織（id, name, slug, plan, max_members, settings） |
| `users` | TEXT PK | UUID PK | 使用者（id, email, password_hash, name, email_verified, verification/reset tokens） |
| `org_memberships` | TEXT PK | UUID PK | 組織成員（user_id, org_id, role, status） |
| `invitations` | TEXT PK | UUID PK | 邀請（org_id, email, token, expires_at） |
| `refresh_tokens` | TEXT PK | UUID PK | Refresh Token（token_hash, expires_at, revoked_at） |
| `login_attempts` | TEXT PK | UUID PK | 登入嘗試紀錄（email, ip_address, success, attempted_at） |

**已建立的 Index：**
- `idx_users_email`, `idx_users_verification_token`, `idx_users_reset_token`
- `idx_org_memberships_user`, `idx_org_memberships_org`
- `idx_invitations_token`, `idx_invitations_email`
- `idx_refresh_tokens_hash`, `idx_refresh_tokens_user`
- `idx_login_attempts_email`, `idx_login_attempts_time`

**尚未實作：**
- [ ] Alembic migration 設定（目前用 auto-create，未來 schema 變更需版本控制）
- [ ] `audit_logs` 表（Phase 3B）
- [ ] organizations 缺少 `storage_quota_gb`、`monthly_search_limit` 欄位（Phase 2E 需要）
- [ ] organizations 時間欄位用 `REAL`（epoch），規劃中是 `TIMESTAMPTZ`

**規劃中的 Alembic 設定（TODO）：**
```
code/python/
├── alembic/
│   ├── versions/        # migration 檔案
│   ├── env.py           # 環境設定（雙 DB 支援）
│   └── script.py.mako   # template
├── alembic.ini          # Alembic 設定檔
```

### Phase 1B — Auth Service :white_check_mark: DONE

**檔案**：`auth/auth_service.py`

| 方法 | 狀態 | 說明 |
|------|------|------|
| `register_user(email, password, name)` | :white_check_mark: | bcrypt hash -> 建立 user -> 發送驗證 email |
| `verify_email(token)` | :white_check_mark: | 驗證 token -> email_verified=true |
| `login(email, password, ip)` | :white_check_mark: | bcrypt 驗證 -> brute force check -> JWT + refresh token |
| `refresh_token(token)` | :white_check_mark: | SHA256 hash 比對 -> 產生新 access token |
| `logout(refresh_token)` | :white_check_mark: | 撤銷 refresh token（set revoked_at） |
| `forgot_password(email)` | :white_check_mark: | 產生 reset token -> email（不洩漏 email 是否存在） |
| `reset_password(token, new_pw)` | :white_check_mark: | 驗證 token -> 更新密碼 -> 撤銷所有 refresh token |
| `create_organization(name, admin_user_id)` | :white_check_mark: | 建立 org + admin membership |
| `invite_member(org_id, email, role, invited_by)` | :white_check_mark: | 驗證 admin -> 檢查人數上限 -> 建立邀請 -> email |
| `accept_invitation(token, user_id)` | :white_check_mark: | 驗證 token + email match -> 建立 membership |
| `list_user_orgs(user_id)` | :white_check_mark: | 列出使用者加入的組織 |
| `list_org_members(org_id, requester)` | :white_check_mark: | 驗證是成員 -> 列出成員 |
| `remove_member(org_id, target, requester)` | :white_check_mark: | 驗證 admin -> 不可移除自己 -> set status='removed' |
| `get_user_by_id(user_id)` | :white_check_mark: | 取得使用者（不含 password_hash） |

**Token 策略（已實作）：**
- Access token：15 分鐘，JWT payload 含 `{user_id, email, name, org_id, role, iat, exp}`
- Refresh token：7 天，secrets.token_urlsafe(64)，DB 存 SHA256 hash
- 密碼驗證：bcrypt hash
- Brute force：15 分鐘內失敗 5 次鎖定

### Phase 1B — Email Service :white_check_mark: DONE

**檔案**：`auth/email_service.py`

| 方法 | 狀態 | 說明 |
|------|------|------|
| `send_verification_email(email, token, name)` | :white_check_mark: | 註冊後驗證 email |
| `send_password_reset_email(email, token, name)` | :white_check_mark: | 密碼重設連結（1 小時有效） |
| `send_invitation_email(email, org_name, inviter_name, token)` | :white_check_mark: | 組織邀請連結（7 天有效） |

**模式**：
- Production：`RESEND_API_KEY` 設定時透過 Resend API 發送
- Development：無 API key 時 logger.info 印出 URL 到 console

### Phase 1C — Auth API Routes :white_check_mark: DONE

**檔案**：`webserver/routes/auth.py`

**Auth 路由：**

| Method | Endpoint | 狀態 | 說明 |
|--------|----------|------|------|
| POST | `/api/auth/register` | :white_check_mark: | 註冊 |
| GET | `/api/auth/verify-email?token=xxx` | :white_check_mark: | 驗證 email |
| POST | `/api/auth/login` | :white_check_mark: | 登入（回傳 access_token + HttpOnly refresh cookie） |
| POST | `/api/auth/refresh` | :white_check_mark: | 刷新 token（cookie 或 body） |
| POST | `/api/auth/logout` | :white_check_mark: | 登出（撤銷 refresh token + 清 cookie） |
| GET | `/api/auth/me` | :white_check_mark: | 取得目前使用者資訊 |
| POST | `/api/auth/forgot-password` | :white_check_mark: | 請求密碼重設 |
| POST | `/api/auth/reset-password` | :white_check_mark: | 重設密碼 |

**組織路由：**

| Method | Endpoint | 狀態 | 說明 |
|--------|----------|------|------|
| POST | `/api/org` | :white_check_mark: | 建立組織 |
| GET | `/api/org` | :white_check_mark: | 列出使用者的組織 |
| POST | `/api/org/{id}/invite` | :white_check_mark: | 邀請成員 |
| GET | `/api/org/{id}/members` | :white_check_mark: | 列出成員 |
| DELETE | `/api/org/{id}/members/{user_id}` | :white_check_mark: | 移除成員 |
| POST | `/api/org/accept-invite` | :white_check_mark: | 接受邀請 |

**實作細節**：
- Login handler 在 response 設定 `Set-Cookie: refresh_token`（HttpOnly, Secure, SameSite=Lax, path=/api/auth）
- Refresh handler 同時支援 cookie 和 request body（非瀏覽器客戶端）
- `_get_client_ip()` 支援 X-Forwarded-For header
- 所有 handler 使用 lazy-init `_get_service()` 避免 import-time DB 連線

### Phase 1D — Auth Middleware :white_check_mark: DONE

**檔案**：`webserver/middleware/auth.py`（完整重寫）

**已完成的修改：**

| 項目 | 狀態 |
|------|------|
| PUBLIC_ENDPOINTS 移除 OAuth 端點 | :white_check_mark: |
| PUBLIC_ENDPOINTS 加入 auth 端點（register/login/verify/forgot/reset/refresh） | :white_check_mark: |
| WebSocket path 特殊處理移除 | :white_check_mark: |
| Test token (`e2e_*`, `test_token_*`) 移除 | :white_check_mark: |
| JWT 解碼失敗 -> 401（非靜默放行） | :white_check_mark: |
| JWT_SECRET 未設定 -> 500 error（非靜默放行） | :white_check_mark: |
| `request['user']` 含 org_id, role, authenticated | :white_check_mark: |
| Dev mode bypass（`mode == 'development'` 時 no-token 可進入） | :white_check_mark: |
| Token 來源：Bearer header > cookie > query param (GET only) | :white_check_mark: |

**`/ask` 端點的認證策略**：目前 `/ask` 仍在 PUBLIC_ENDPOINTS 中（line 23 註解 "Allow public access for now"），尚未實施 auth。

規劃方案：使用方案 A — `fetch()` + `ReadableStream`（前端 `performSearch()` 已用此模式，非原生 `EventSource`），搭配 `Authorization: Bearer` header。

### Phase 1E — 修復 user_id 模式 :yellow_circle: Partially Done

**`user_data.py`（5 個端點）**：:white_check_mark: 已從 `request['user']['id']` 取值

| 行號（現） | 原始 | 改為 | 狀態 |
|------------|------|------|------|
| ~38-39 | upload multipart user_id | `request.get('user', {}).get('id')` | :white_check_mark: |
| ~128-129 | progress query param | `request.get('user', {}).get('id')` | :white_check_mark: |
| ~245-246 | list query param | `request.get('user', {}).get('id')` | :white_check_mark: (待確認) |
| ~286-287 | delete query param | `request.get('user', {}).get('id')` | :white_check_mark: (待確認) |
| ~344-345 | get_status query param | `request.get('user', {}).get('id')` | :white_check_mark: (待確認) |

**`baseHandler.py`**：:red_circle: 尚未修改
- Line 102：仍為 `self.user_id = get_param(self.query_params, "user_id", str, None)`
- 需改為從 HTTP request 的 `request['user']` 注入

**`storage_providers/qdrant_storage.py`**：:red_circle: 尚未修改
- `get_conversation_by_id()` 需加入 user_id filter

### Phase 1F — 前端 Login UI :red_circle: Not Started

**需修改檔案：**
- `static/news-search-prototype.html` — Header 加入 Login/Register modal
- `static/news-search.js` — AuthManager class + 替換 TEMP_USER_ID
- `static/news-search.css` — Login modal 樣式

**AuthManager class 設計：**

| 方法 | 說明 |
|------|------|
| `login(email, password)` | POST `/api/auth/login`，存 access token 到 JS 變數 |
| `register(email, password, name)` | POST `/api/auth/register` |
| `refreshToken()` | POST `/api/auth/refresh`（HttpOnly cookie 自動帶） |
| `logout()` | POST `/api/auth/logout`，清除 token |
| `getAccessToken()` | 回傳 token，過期自動 refresh |
| `getCurrentUser()` | 回傳快取的 user info |
| `isAuthenticated()` | 檢查是否有有效 token |
| `authenticatedFetch(url, options)` | 統一 API 請求 wrapper + 401 自動 refresh |

**Request Queue 攔截機制**：

```javascript
// 當 access token 過期時，多個同時 401 的請求統一處理：
// 1. 第一個 401 觸發 refreshToken()
// 2. isRefreshing = true，後續 401 加入等待佇列
// 3. refresh 成功 -> 用新 token 重發所有排隊請求
// 4. refresh 失敗 -> reject 所有 -> 跳轉登入頁
```

**TEMP_USER_ID 替換位置（7 處）：**

| 行號 | 用途 | 改為 |
|------|------|------|
| 51 | `const TEMP_USER_ID = 'demo_user_001'` 定義 | 刪除 |
| 1563 | Deep Research URL user_id | `authManager.getCurrentUser().id` |
| 1564 | Deep Research console log | `authManager.getCurrentUser().id` |
| 2540 | requestBody.user_id | `authManager.getCurrentUser().id` |
| 4041 | upload formData user_id | `authManager.getCurrentUser().id` |
| 4062 | upload progress SSE URL | `authManager.getCurrentUser().id` |
| 4104 | list user sources URL | `authManager.getCurrentUser().id` |

**SSE 斷線重連機制**：
- 偵測 ReadableStream 中斷（network error / stream closed）
- 401 -> 先 refreshToken()，成功後自動重啟搜尋
- 網路波動 -> 帶 session_id + conversation_id 重新發送
- 最大重試 3 次，exponential backoff（1s -> 2s -> 4s）

---

## Part 2：Session Management（對話管理/歸戶系統）

### Phase 2A — Session Schema :red_circle: Not Started

```sql
-- 搜尋 Session（取代 localStorage taiwanNewsSavedSessions）
CREATE TABLE search_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    org_id UUID NOT NULL REFERENCES organizations(id),
    title VARCHAR(500),
    conversation_history JSONB DEFAULT '[]',
    session_history JSONB DEFAULT '[]',
    chat_history JSONB DEFAULT '[]',
    accumulated_articles JSONB DEFAULT '[]',
    pinned_messages JSONB DEFAULT '[]',
    pinned_news_cards JSONB DEFAULT '[]',
    research_report JSONB DEFAULT '{}',
    user_feedback VARCHAR(20),              -- 'thumbs_up', 'thumbs_down', NULL
    admin_note TEXT,
    visibility VARCHAR(20) DEFAULT 'private',  -- 'private', 'team', 'org'（Phase 5+）
    shared_with UUID[] DEFAULT '{}',           -- Phase 5+
    team_comments JSONB DEFAULT '[]',          -- Phase 5+
    is_archived BOOLEAN DEFAULT FALSE,
    deleted_at TIMESTAMPTZ,                    -- 軟刪除
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 組織共享資料夾
CREATE TABLE org_folders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    created_by UUID NOT NULL REFERENCES users(id),
    session_ids UUID[] DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 使用者偏好
CREATE TABLE user_preferences (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    org_id UUID NOT NULL REFERENCES organizations(id),
    preference_key VARCHAR(100) NOT NULL,
    preference_value JSONB NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, org_id, preference_key)
);
```

**軟刪除機制**：
- DELETE 實際上 `SET deleted_at = NOW()`
- 所有查詢 `WHERE deleted_at IS NULL`
- Admin 30 天內可恢復（`POST /api/sessions/{id}/restore`）
- 排程清理 30 天後的記錄 + Qdrant orphan vectors

**`accumulated_articles` JSONB 結構**：
```json
{
  "url": "https://...",
  "title": "...",
  "source": "Reuters",
  "published_date": "2026-02-08",
  "summary": "...",
  "retrieved_at": "2026-02-09T14:30:00Z",
  "status": "unread",        // unread | read | analyzed | excluded
  "importance": null,         // null | 1-5
  "tags": [],
  "researcher_note": null
}
```

### Phase 2B — Session API :red_circle: Not Started

**新檔案**：`webserver/routes/sessions.py`

| Method | Endpoint | 說明 |
|--------|----------|------|
| GET | `/api/sessions` | 列出 session（分頁，org 範圍） |
| POST | `/api/sessions` | 建立/儲存 session |
| GET | `/api/sessions/{id}` | 取得單一 session |
| PUT | `/api/sessions/{id}` | 更新 session（partial JSONB update） |
| DELETE | `/api/sessions/{id}` | 軟刪除 session |
| POST | `/api/sessions/migrate` | 從 localStorage 批次遷移 |
| PATCH | `/api/sessions/{id}/feedback` | 使用者回饋 |
| PATCH | `/api/sessions/{id}/note` | 管理員備註（admin only） |
| POST | `/api/sessions/{id}/restore` | 恢復軟刪除（admin, 30 天內） |
| PATCH | `/api/sessions/{id}/articles/{url}/annotate` | 文章標註 |
| GET | `/api/sessions/{id}/export` | 匯出（json/csv/citations/ris） |
| PATCH | `/api/sessions/{id}/visibility` | 分享範圍（Phase 5+） |
| GET | `/api/sessions/shared` | 共享給我的 Sessions（Phase 5+） |

**偏好端點：**

| Method | Endpoint | 說明 |
|--------|----------|------|
| GET | `/api/preferences` | 取得所有偏好 |
| PUT | `/api/preferences/{key}` | 設定偏好 |

### Phase 2C — Session Service :red_circle: Not Started

**新檔案**：`core/session_service.py`

核心方法：`list_sessions`, `create_session`, `get_session`, `update_session`, `append_message`, `delete_session`, `restore_session`, `append_articles`, `update_article_annotation`, `migrate_sessions`, `export_session`, `generate_citations`, `get_preferences`, `set_preference`

**JSONB Append 模式**（效能優化）：
```sql
UPDATE search_sessions
SET conversation_history = conversation_history || $1::jsonb,
    updated_at = NOW()
WHERE id = $2 AND user_id = $3;
```

### Phase 2D — 前端遷移 :red_circle: Not Started

**新增 SessionManager class**：

| 方法 | 取代的 localStorage 操作 |
|------|--------------------------|
| `loadSessions()` | `localStorage.getItem('taiwanNewsSavedSessions')` |
| `saveSession(session)` | `localStorage.setItem('taiwanNewsSavedSessions', ...)` |
| `deleteSession(id)` | 從 savedSessions 移除 |
| `migrateFromLocal()` | 首次登入遷移 |
| `loadFolders()` | `localStorage.getItem('taiwanNewsFolders')` |
| `saveFolders(folders)` | `localStorage.setItem('taiwanNewsFolders', ...)` |

**遷移流程**：登入 -> 偵測 localStorage -> POST /api/sessions/migrate -> 清除 localStorage -> 設 flag

**Auto-save**：debounce 2-3 秒，Optimistic UI

### Phase 2E — 組織級資料隔離 :red_circle: Not Started

- 所有查詢加 `WHERE org_id = $n`
- JWT 含 org_id，middleware 注入
- Admin 可查 `visibility = 'org'/'team'` 的 Session
- Admin 可恢復軟刪除
- 不允許 admin 查 `visibility = 'private'`

**需加 org_id 的現有模組**：
- `core/user_data_manager.py` — user_sources
- `retrieval_providers/user_qdrant_provider.py` — Qdrant filter
- `core/query_logger.py` — analytics

**資源配額**：
- `organizations.storage_quota_gb` — upload 前檢查
- `organizations.monthly_search_limit` — 搜尋前檢查
- 80% 時 log warning

---

## Part 3：Security Hardening

### Phase 3A — Rate Limiting :red_circle: Not Started

**Login 防護（已實作於 auth_service.py 的 brute force check）**：
- :white_check_mark: 同一 email 15 分鐘內失敗 5 次 -> 鎖定（已在 auth_service._check_brute_force）

**API Rate Limiting（未實作）**：
- [ ] 全局：每個 user 100 requests/min
- [ ] `/api/auth/register`：每個 IP 5 requests/hour
- [ ] `/api/auth/forgot-password`：每個 email 3 requests/hour
- [ ] 建議使用 `aiohttp-ratelimiter` 或自建 middleware

### Phase 3B — Audit Logs :red_circle: Not Started

**新表**：`audit_logs`（見 Phase 1A 規劃中的 SQL）

**新檔案**：`core/audit_service.py`

| 方法 | 說明 |
|------|------|
| `log_action(user_id, org_id, action, target_type, target_id, details, request)` | 寫入稽核紀錄 |
| `get_audit_logs(org_id, filters, limit, offset)` | 查詢組織紀錄（admin only） |
| `get_my_research_trail(user_id, org_id, date_range)` | 個人搜尋軌跡 |

**需記錄的行為**：`member.invite`, `member.remove`, `session.delete`, `session.report_update`, `session.export`, `session.share`, `search.query`, `search.deep_research`, `file.upload`, `file.delete`, `org.settings.update`, `auth.login`, `auth.login_failed`, `auth.password_reset`

**整合**：fire-and-forget 模式（`asyncio.create_task`）

### Phase 3C — CORS :red_circle: Not Started

- Production：`ALLOWED_ORIGINS` 環境變數
- Development：允許 `localhost:*`
- `credentials: true` 支援 HttpOnly cookie

---

## Part 4：Data Migration

### Phase 4A — 現有資料遷移 :red_circle: Not Started

| 資料位置 | 遷移策略 |
|----------|----------|
| Qdrant `nlweb_conversations` | 舊 user_id 映射到新 users 表 |
| Qdrant `nlweb_user_data` | 同上 + 加入 org_id payload |
| SQLite/PostgreSQL `user_sources` + `user_documents` | ALTER TABLE 加 org_id |
| analytics tables | 加 org_id（歷史資料標 `legacy_org`） |

**遷移腳本**：`scripts/migrate_to_b2b.py`（idempotent）

---

## Part 5+：Research Collaboration

### Phase 5A — Session Export :red_circle: Not Started

格式：JSON / CSV / RIS / APA+Chicago citations

### Phase 5B — Session Sharing :red_circle: Not Started

基礎版：visibility 設為 team/org，側欄「共享給我」分頁

### Phase 6+ 功能備忘

| 功能 | 觸發條件 |
|------|----------|
| 跨 Session 全文檢索 | 100+ Sessions |
| 配額告警 Email | 有付費方案 |
| 研究主管統計看板 | 3+ 組織使用者 |
| 網頁快照（Snapshot） | 新聞連結失效 |
| BibTeX 匯出 | 學術用戶需求 |
| 團隊評論 | Phase 5B 成熟後 |
| 精細分享權限 | Phase 5B 成熟後 |

---

## Sprint Schedule

| Sprint | 週數 | 內容 | 狀態 |
|--------|------|------|------|
| **Sprint 0** | Week 1 | Phase 0A-0B：移除 OAuth + WebSocket Chat | :white_check_mark: 完成 |
| **Sprint 1** | Week 2-3 | Phase 1A-1C：DB schema + auth service + email + API routes | :white_check_mark: 完成（Alembic 除外） |
| **Sprint 2** | Week 4 | Phase 1D-1F：middleware + 前端 Login UI + TEMP_USER_ID 替換 | :yellow_circle: middleware 完成，前端未開始 |
| **Sprint 3** | Week 5-6 | Phase 2A-2D：session schema + API + service + 前端遷移 | :red_circle: 未開始 |
| **Sprint 4** | Week 7 | Phase 2E + 3A-3C：組織隔離 + 安全性 + CORS | :red_circle: 未開始 |
| **Sprint 5** | Week 8 | Phase 3B + 4A + 5A-5B：Audit + 遷移 + 匯出 + 分享 | :red_circle: 未開始 |
| **Phase 6+** | 未排期 | 組織知識庫 + 跨 Session 搜尋 + 進階協作 | :red_circle: 未排期 |

---

## File Inventory

### 已建立的新檔案

| 檔案 | Sprint | 狀態 |
|------|--------|------|
| `code/python/auth/__init__.py` | Sprint 1 | :white_check_mark: |
| `code/python/auth/auth_db.py` | Sprint 1 | :white_check_mark: |
| `code/python/auth/auth_service.py` | Sprint 1 | :white_check_mark: |
| `code/python/auth/email_service.py` | Sprint 1 | :white_check_mark: |
| `code/python/webserver/routes/auth.py` | Sprint 1 | :white_check_mark: |

### 待建立的新檔案

| 檔案 | Sprint | 說明 |
|------|--------|------|
| `code/python/alembic/` + `alembic.ini` | Sprint 1 (延後) | DB migration |
| `code/python/webserver/routes/sessions.py` | Sprint 3 | Session API |
| `code/python/core/session_service.py` | Sprint 3 | Session 業務邏輯 |
| `code/python/core/audit_service.py` | Sprint 5 | 稽核日誌 |
| `scripts/migrate_to_b2b.py` | Sprint 5 | 資料遷移 |

### 已刪除的檔案

| 檔案 | Sprint |
|------|--------|
| `code/python/chat/`（9 個檔案） | Sprint 0 |
| `code/python/webserver/routes/chat.py` | Sprint 0 |
| `code/python/webserver/routes/oauth.py` | Sprint 0 |
| `config/config_oauth.yaml` | Sprint 0 |

### 已修改的檔案

| 檔案 | Sprint | 修改內容 |
|------|--------|----------|
| `webserver/routes/__init__.py` | Sprint 0+1 | 移除 oauth/chat，加入 auth |
| `webserver/middleware/auth.py` | Sprint 0+2 | 完整重寫 |
| `webserver/aiohttp_server.py` | Sprint 0 | 移除 chat 初始化 |
| `core/config.py` | Sprint 0 | 移除 OAuth config |
| `webserver/routes/user_data.py` | Sprint 2 | user_id 改從 request['user'] 取 |

### 待修改的檔案

| 檔案 | Sprint | 修改內容 |
|------|--------|----------|
| `core/baseHandler.py` | Sprint 2 | user_id 從 auth context 注入（目前仍用 query param） |
| `storage_providers/qdrant_storage.py` | Sprint 2 | get_conversation_by_id 加 user_id filter |
| `static/news-search-prototype.html` | Sprint 2 | Login/Register modal |
| `static/news-search.js` | Sprint 2+3 | AuthManager + SessionManager + TEMP_USER_ID 替換 |
| `static/news-search.css` | Sprint 2 | Login modal 樣式 |
| `core/user_data_manager.py` | Sprint 4 | org_id filter |
| `retrieval_providers/user_qdrant_provider.py` | Sprint 4 | org_id filter |
| `core/query_logger.py` | Sprint 4 | org_id 記錄 |

---

## Environment Variables

| 變數 | 說明 | 範例 | 狀態 |
|------|------|------|------|
| `JWT_SECRET` | JWT 簽名密鑰 | 隨機 256-bit string | :white_check_mark: 已使用 |
| `RESEND_API_KEY` | Resend API key | `re_xxxxx` | :white_check_mark: 已使用（可選） |
| `RESEND_FROM_EMAIL` | 發信地址 | `noreply@yourdomain.com` | :white_check_mark: 已使用 |
| `BASE_URL` | 系統 base URL | `http://localhost:8000` | :white_check_mark: 已使用 |
| `ANALYTICS_DATABASE_URL` | 共用 DB URL | PostgreSQL connection string | :white_check_mark: 已使用 |
| `NLWEB_DEV_AUTH_BYPASS` | 開發模式跳過認證 | `true` | :red_circle: 未使用（目前用 mode=development） |
| `ALLOWED_ORIGINS` | CORS 允許的 origin | `https://app.yourdomain.com` | :red_circle: Phase 3C |

---

## Dependencies

| 套件 | 用途 | 狀態 |
|------|------|------|
| `bcrypt` | 密碼 hash | :white_check_mark: 已安裝使用 |
| `PyJWT` | JWT token | :white_check_mark: 已安裝使用 |
| `resend` | Email 發送 | :white_check_mark: 已安裝（可選） |
| `alembic` | DB migration | :red_circle: 未安裝 |

---

## Verification Checklist

### Sprint 0 :white_check_mark:

- [x] `oauth.py`、`config_oauth.yaml`、`chat/`、`routes/chat.py` 已刪除
- [x] `config.py` 無 OAuth 相關屬性
- [x] `routes/__init__.py` 無 oauth/chat imports
- [x] `aiohttp_server.py` 無 chat 初始化

### Sprint 1 :white_check_mark:

- [x] `auth_db.py` 啟動時自動建表
- [x] POST `/api/auth/register` -> success + 驗證 email（dev 印出 URL）
- [x] GET `/api/auth/verify-email?token=xxx` -> email_verified=true
- [x] POST `/api/auth/login` -> access_token + refresh cookie
- [x] POST `/api/org` -> 建立組織

### Sprint 2（進行中）

- [x] Middleware 重寫完成
- [x] user_data.py 端點改用 request['user']['id']
- [ ] baseHandler.py user_id 從 auth context 取
- [ ] qdrant_storage.py 加 user_id filter
- [ ] 前端 AuthManager class
- [ ] 替換 7 處 TEMP_USER_ID
- [ ] Login/Register modal UI
- [ ] SSE 斷線重連 + token refresh

### Sprint 3

- [ ] search_sessions 表建立（Alembic migration）
- [ ] Session CRUD API + JSONB append
- [ ] SessionManager 前端 class
- [ ] localStorage 完全移除
- [ ] 文章標註功能（status/tags/importance）
- [ ] CSV/JSON export

### Sprint 4

- [ ] org_id filter 加入所有查詢
- [ ] API rate limiting middleware
- [ ] CORS 設定
- [ ] 配額檢查（storage + search limit）

### Sprint 5

- [ ] audit_logs 表 + audit_service.py
- [ ] 資料遷移腳本
- [ ] RIS export + citation generation
- [ ] Session 分享（visibility）
- [ ] 組織管理 UI + 邀請流程
