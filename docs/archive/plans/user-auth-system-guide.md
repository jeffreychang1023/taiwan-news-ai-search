# 使用者登入與對話管理系統開發指南

> 本文件為開發者提供指引，說明如何將目前的 localStorage / hardcode user_id 改為 Production 級別的實作。

---

## 一、現有模組概覽

### 1. OAuth 認證（已實作）

| 檔案 | 功能 |
|------|------|
| `webserver/routes/oauth.py` | OAuth 後端路由，支援 Google/Facebook/Microsoft/GitHub |
| `webserver/middleware/auth.py` | Auth middleware（已實作），JWT / Base64 / 測試 token 解析 |
| `config/config_oauth.yaml` | OAuth provider 配置 |
| `static/old scripts/oauth-login.js` | 前端 OAuth 登入邏輯（參考用） |
| `static/old scripts/identity-service.js` | Email-based 身份識別（hash-based participant ID） |

**API 端點：**
- `GET /api/oauth/config` - 取得 OAuth 配置（enabled providers）
- `POST /api/oauth/token` - 用 OAuth code 換取 token
- Token 格式：JWT，包含 `user_id`, `email`, `name`, `provider`

### 2. Auth Middleware 現況（`webserver/middleware/auth.py`）

Middleware 已實作，支援三種 token 格式：

| Token 格式 | 範例 | 用途 |
|---|---|---|
| JWT | 標準 `header.payload.signature` | Production OAuth |
| Base64 JSON | `btoa(JSON.stringify({user_id, email, ...}))` | 簡易前端登入 |
| `e2e_*` | `e2e_test_single_user` | E2E 測試 |

Fallback：token 解析失敗時，user_id 預設為 `'authenticated_user'`。

### 3. 三層身份識別架構

系統有三層 fallback 機制，由高到低：

```
Layer 1: OAuth 認證（JWT token）
    ↓ 沒有 token
Layer 2: Email 身份（identity-service.js, hash-based ID）
    ↓ 沒有 email
Layer 3: 匿名用戶（自動生成 anon_ + UUID）
```

**各層對應的程式碼：**

| 層級 | 後端檔案 | 前端檔案 | ID 格式 |
|---|---|---|---|
| OAuth | `middleware/auth.py` | `oauth-login.js` | Provider-specific 或 email |
| Email | — | `identity-service.js` | `user_` + hash(email) |
| 匿名 | `webserver/routes/chat.py` | `fp-chat-interface-ws.js` | `anon_{uuid}` → 顯示為 `Anonymous {last4}` |

**後端 Fallback chain（`baseHandler.py`）：**
```python
self.oauth_id = get_param(self.query_params, "oauth_id", str, "")
# logging 時: self.oauth_id or "anonymous"
```

### 4. User Data 模組（已實作）

| 檔案 | 功能 |
|------|------|
| `core/user_data_db.py` | 資料庫層（SQLite/PostgreSQL 雙支援）|
| `core/user_data_manager.py` | 用戶資料 CRUD 管理 |
| `core/user_data_processor.py` | 檔案處理（chunking, embedding）|
| `core/user_data_retriever.py` | 用戶私有資料檢索 |
| `webserver/routes/user_data.py` | API 路由 |
| `config/user_data.yaml` | 配置（檔案限制、Qdrant collection）|

**資料表：**
- `user_sources` - 用戶上傳的檔案 metadata
- `user_documents` - 文件 chunks

### 5. 對話歷史模組（已實作）

| 檔案 | 功能 |
|------|------|
| `core/conversation_history.py` | 對話儲存抽象層 |
| `storage_providers/qdrant_storage.py` | Qdrant 對話儲存 |
| `config/config_conv_store.yaml` | 對話儲存配置 |

**功能：**
- `store_conversation()` - 儲存對話
- `get_conversations()` - 取得用戶對話列表
- `get_conversation()` - 取得單一對話
- `delete_conversation()` - 刪除對話
- `migrate_from_localstorage()` - 從 localStorage 遷移

### 6. 其他使用 user_id 的模組

| 檔案 | user_id 用法 |
|---|---|
| `core/baseHandler.py` | `oauth_id` param，fallback `"anonymous"`；自動生成 `session_id`、`conversation_id` |
| `core/query_logger.py` | 每次查詢記錄 `user_id` 到 analytics |
| `core/analytics_db.py` | DB schema 含 `user_id` 欄位 |
| `core/utils/message_senders.py` | `handler.oauth_id` → `user_id` param 層層解析 |
| `retrieval_providers/user_qdrant_provider.py` | 向量搜尋時以 `user_id` FieldCondition filter |
| `chat/participants.py` | `HumanParticipant(user_id, user_name)` |
| `chat/websocket.py` | WebSocket 連線管理以 `user_id` 為 key |
| `chat/schemas.py` | `ParticipantInfo` 以 `participant_id` 做 hash/eq |

---

## 二、目前需要改進的問題

### 前端 Hardcode

```javascript
// static/news-search.js:51
const TEMP_USER_ID = 'demo_user_001';  // ❌ 需要改為真實 user_id
```

**`TEMP_USER_ID` 的所有使用位置（共 7 處）：**

| 行號 | 用途 | 程式碼 |
|---|---|---|
| 51 | 定義 | `const TEMP_USER_ID = 'demo_user_001'` |
| 1861 | Deep Research URL param | `deepResearchUrl.searchParams.append('user_id', TEMP_USER_ID)` |
| 1862 | Deep Research console log | `console.log('...', TEMP_USER_ID)` |
| 3248 | Free Conversation request body | `requestBody.user_id = TEMP_USER_ID` |
| 5279 | 檔案上傳 form data | `formData.append('user_id', TEMP_USER_ID)` |
| 5300 | 上傳進度 SSE URL | `` `/api/user/upload/${sourceId}/progress?user_id=${TEMP_USER_ID}` `` |
| 5415 | 載入使用者檔案 | `` `/api/user/sources?user_id=${TEMP_USER_ID}` `` |
| 5832 | 刪除使用者檔案 | `` `/api/user/sources/${sourceId}?user_id=${TEMP_USER_ID}` `` |

### 後端問題

```python
# webserver/routes/user_data.py — user_id 從 query param 取得（不安全）
user_id = request.query.get('user_id')  # ❌ 應從 token 解析

# core/baseHandler.py — 不同的參數名稱
self.oauth_id = get_param(self.query_params, "oauth_id", str, "")
# logging: self.oauth_id or "anonymous"
```

注意：`user_data.py` 用 `user_id` param，`baseHandler.py` 用 `oauth_id` param，兩套命名並存。

### 完整的 localStorage 使用清單

**核心應用資料（`news-search.js`）：**

| Key | 內容 | 遷移優先級 |
|---|---|---|
| `taiwanNewsSavedSessions` | 所有搜尋歷史（對話、文章、研究報告、pinned） | **高**（資料量最大，無限增長） |
| `nlweb_source_folders` | 新聞來源資料夾組織 | 高 |
| `nlweb_file_folders` | 使用者檔案資料夾組織 | 高 |
| `nlweb_selected_files` | 已勾選的檔案 ID 清單 | 中 |

**身份認證（`oauth-login.js`, `identity-service.js`）：**

| Key | 內容 | 安全風險 |
|---|---|---|
| `authToken` | OAuth JWT token | **高**（應改用 HttpOnly cookie） |
| `userInfo` | 使用者名稱、email、provider JSON | 中（含 PII） |
| `nlweb_chat_identity` | Email + displayName JSON | 中（含 PII） |

**UI 偏好：**

| Key | 內容 | 遷移優先級 |
|---|---|---|
| `nlweb_chat_mode` | 搜尋模式偏好（list/summarize/generate） | 低（可保留 localStorage） |
| `nlweb-sidebar-collapsed` | 側欄展開/收起狀態 | 低（裝置級偏好） |

**舊版 / Legacy（`old scripts/`, `old htmls/`）：**

| Key | 內容 | 備註 |
|---|---|---|
| `anonymousUserId` | `anon_` + random string | `fp-chat-interface-ws.js` |
| `nlweb_conversations` | 已加入的對話 metadata | `join.html` |
| `nlweb_messages` | 對話訊息 | `join.html` |
| `currentConversationId` | 目前對話 ID | `join.html` |
| `nlweb_chat_state` | 完整 app state | `state-manager.js` |

### sessionStorage 使用清單

| Key | 內容 | 檔案 |
|---|---|---|
| `nlweb_session_id` | Analytics session（`sess_` + UUID 12 chars） | `news-search.js` |
| `pendingJoinConversation` | OAuth 重導向後待加入的 conversation_id | `chat-interface-unified.js`, `join.html` |
| `oauth_provider` | 登入中的 OAuth provider 名稱 | `oauth-login.js` |

---

## 三、建議實作步驟

### Phase 1：認證流程整合

#### 1.1 前端：整合 OAuth 登入

```javascript
// 參考 static/old scripts/oauth-login.js
class AuthManager {
    async login(provider) {
        // 開啟 OAuth 視窗
        const authUrl = `/api/oauth/${provider}/authorize`;
        window.open(authUrl, 'oauth', 'width=500,height=600');
    }

    async handleCallback(code, provider) {
        // 換取 token
        const response = await fetch('/api/oauth/token', {
            method: 'POST',
            body: JSON.stringify({ code, provider })
        });
        const { token, user } = await response.json();

        // 儲存到 localStorage（暫時）或 httpOnly cookie（推薦）
        localStorage.setItem('authToken', token);
        localStorage.setItem('userInfo', JSON.stringify(user));
    }

    getAuthHeaders() {
        const token = localStorage.getItem('authToken');
        return token ? { 'Authorization': `Bearer ${token}` } : {};
    }

    getUserId() {
        const userInfo = JSON.parse(localStorage.getItem('userInfo') || '{}');
        return userInfo.id || null;
    }
}
```

#### 1.2 後端：統一 user_id 解析

Auth middleware（`webserver/middleware/auth.py`）已存在，但需要調整：

```python
# 現況：middleware 已實作，但有以下問題需修正

# 1. 移除 e2e_* token 路徑（或限定為測試環境）
if auth_token.startswith('e2e_'):
    # ⚠️ 目前存在於 production code，上線前需移除或用環境變數控制

# 2. fallback 值 'authenticated_user' 語意不清
user_id = payload.get('user_id', 'authenticated_user')  # ⚠️ 改為明確的錯誤處理

# 3. 統一 user_id 與 oauth_id 命名
# baseHandler.py 用 "oauth_id"，user_data.py 用 "user_id"
# 應統一為 request['user_id']，由 middleware 注入
```

#### 1.3 修改現有 API 使用 request['user_id']

```python
# webserver/routes/user_data.py
async def list_sources_handler(request):
    # 舊：user_id = request.query.get('user_id')
    # 新：從 middleware 注入
    user_id = request.get('user_id')
    if not user_id:
        return web.json_response({'error': 'Unauthorized'}, status=401)
    ...
```

#### 1.4 替換 TEMP_USER_ID

```javascript
// 舊：const TEMP_USER_ID = 'demo_user_001';
// 新：從 AuthManager 取得
const userId = authManager.getUserId();
// 所有 7 處使用點都需替換（見 Section 二的表格）
```

---

### Phase 2：對話歷史遷移

#### 2.1 新增對話 API 端點

```python
# webserver/routes/conversations.py（新增）
from core.conversation_history import (
    store_conversation, get_conversations,
    get_conversation, delete_conversation
)

async def list_conversations_handler(request):
    """GET /api/conversations"""
    user_id = request.get('user_id')
    conversations = await get_conversations(user_id)
    return web.json_response(conversations)

async def get_conversation_handler(request):
    """GET /api/conversations/{id}"""
    user_id = request.get('user_id')
    conv_id = request.match_info['id']
    conversation = await get_conversation(conv_id, user_id)
    return web.json_response(conversation)

async def save_conversation_handler(request):
    """POST /api/conversations"""
    user_id = request.get('user_id')
    data = await request.json()
    result = await store_conversation(user_id, data)
    return web.json_response(result)

async def delete_conversation_handler(request):
    """DELETE /api/conversations/{id}"""
    user_id = request.get('user_id')
    conv_id = request.match_info['id']
    await delete_conversation(conv_id, user_id)
    return web.json_response({'success': True})
```

#### 2.2 前端：改用 API 儲存對話

```javascript
class ConversationManager {
    constructor(authManager) {
        this.auth = authManager;
    }

    async saveSession(sessionData) {
        const response = await fetch('/api/conversations', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                ...this.auth.getAuthHeaders()
            },
            body: JSON.stringify(sessionData)
        });
        return response.json();
    }

    async loadSessions() {
        const response = await fetch('/api/conversations', {
            headers: this.auth.getAuthHeaders()
        });
        return response.json();
    }

    async deleteSession(sessionId) {
        await fetch(`/api/conversations/${sessionId}`, {
            method: 'DELETE',
            headers: this.auth.getAuthHeaders()
        });
    }
}
```

#### 2.3 遷移現有 localStorage 資料

需遷移的 key 不只 `taiwanNewsSavedSessions`，還包括 `nlweb_source_folders`、`nlweb_file_folders`、`nlweb_selected_files`：

```javascript
async function migrateLocalStorageToServer() {
    if (!authManager.getUserId()) return;

    // 1. 遷移搜尋歷史
    const localSessions = JSON.parse(
        localStorage.getItem('taiwanNewsSavedSessions') || '[]'
    );
    if (localSessions.length > 0) {
        await fetch('/api/conversations/migrate', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                ...authManager.getAuthHeaders()
            },
            body: JSON.stringify({ conversations: localSessions })
        });
        localStorage.removeItem('taiwanNewsSavedSessions');
    }

    // 2. 遷移資料夾組織
    const sourceFolders = JSON.parse(
        localStorage.getItem('nlweb_source_folders') || '[]'
    );
    const fileFolders = JSON.parse(
        localStorage.getItem('nlweb_file_folders') || '[]'
    );
    if (sourceFolders.length > 0 || fileFolders.length > 0) {
        await fetch('/api/user/preferences', {
            method: 'PATCH',
            headers: {
                'Content-Type': 'application/json',
                ...authManager.getAuthHeaders()
            },
            body: JSON.stringify({ sourceFolders, fileFolders })
        });
        localStorage.removeItem('nlweb_source_folders');
        localStorage.removeItem('nlweb_file_folders');
    }
}
```

---

### Phase 3：用戶偏好設定

#### 3.1 擴展 user_data 資料表

```sql
-- 新增 user_preferences 表
CREATE TABLE user_preferences (
    user_id TEXT PRIMARY KEY,
    default_search_mode TEXT DEFAULT 'search',
    include_private_sources BOOLEAN DEFAULT false,
    source_folders JSON,        -- 新聞來源資料夾組織
    file_folders JSON,          -- 使用者檔案資料夾組織
    selected_files JSON,        -- 已勾選的檔案清單
    font_size TEXT DEFAULT 'normal',
    theme TEXT DEFAULT 'light',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### 3.2 API 端點

```python
# webserver/routes/user_preferences.py
async def get_preferences(request):
    """GET /api/user/preferences"""
    user_id = request.get('user_id')
    prefs = await db.get_user_preferences(user_id)
    return web.json_response(prefs)

async def update_preferences(request):
    """PATCH /api/user/preferences"""
    user_id = request.get('user_id')
    updates = await request.json()
    await db.update_user_preferences(user_id, updates)
    return web.json_response({'success': True})
```

---

## 四、安全性考量

### 4.1 Token 安全

```python
# 推薦：使用 httpOnly cookie 而非 localStorage
response = web.json_response({'user': user_info})
response.set_cookie(
    'auth_token',
    token,
    httponly=True,      # JavaScript 無法存取
    secure=True,        # 只在 HTTPS 傳輸
    samesite='Strict',  # 防止 CSRF
    max_age=86400 * 7   # 7 天過期
)
```

### 4.2 測試 Token 路徑

`middleware/auth.py` 中的 `e2e_*` token 解析邏輯目前存在於 production code。上線前需要：
- 用環境變數（如 `ALLOW_TEST_TOKENS=true`）控制是否啟用
- 或在 production build 中完全移除

### 4.3 WebSocket Token 傳遞

目前 WebSocket 連線透過 URL query param 傳 token（`websocket-service.js`），token 會出現在 server log 和瀏覽器歷史紀錄中。改善方案：
- 改用 cookie（WebSocket handshake 會自動帶 cookie）
- 或在 WebSocket 連線建立後，第一個 message 傳送 token

### 4.4 API 權限檢查

```python
# 確保用戶只能存取自己的資料
async def get_conversation_handler(request):
    user_id = request.get('user_id')
    conv_id = request.match_info['id']

    conversation = await get_conversation(conv_id)
    if conversation['user_id'] != user_id:
        return web.json_response({'error': 'Forbidden'}, status=403)
    ...
```

### 4.5 Rate Limiting

```python
# 防止暴力攻擊
from aiohttp_ratelimiter import RateLimiter

@RateLimiter(calls=10, period=60)  # 每分鐘最多 10 次
async def login_handler(request):
    ...
```

### 4.6 localStorage 安全風險

| Key | 風險 | 說明 |
|---|---|---|
| `authToken` | **高** | XSS 可竊取，應改 HttpOnly cookie |
| `userInfo` | 中 | 含 PII（email、名稱），XSS 可讀取 |
| `nlweb_chat_identity` | 中 | 含 email，XSS 可讀取 |
| `taiwanNewsSavedSessions` | 低 | 無限增長可能超出 localStorage 5MB 限制 |

---

## 五、現有模組重用總結

| 需求 | 重用模組 | 需要修改 |
|------|----------|----------|
| 用戶認證 | `webserver/middleware/auth.py`（已存在） | 移除測試 token 路徑、統一 user_id 命名 |
| OAuth 路由 | `webserver/routes/oauth.py` | 改用 HttpOnly cookie 發 token |
| 用戶資料儲存 | `core/user_data_db.py` | 擴展 user_preferences 表 |
| 檔案上傳 | `core/user_data_manager.py` | 已完整，改用 token user_id |
| 對話歷史 | `core/conversation_history.py` | 新增 API 路由 |
| 對話儲存 | `storage_providers/qdrant_storage.py` | 已完整 |
| Query 追蹤 | `core/query_logger.py` | 確保 user_id 從 middleware 取得 |
| 向量隔離 | `retrieval_providers/user_qdrant_provider.py` | 確保所有 retrieval path 都有 user_id filter |
| Chat 參與者 | `chat/participants.py`, `chat/websocket.py` | 確保 user_id 來自認證而非前端傳入 |

---

## 六、user_id 命名統一計畫

目前系統中 user_id 有多種命名，需統一：

| 目前名稱 | 位置 | 統一為 |
|---|---|---|
| `oauth_id` | `baseHandler.py` query param | `user_id`（從 middleware 注入） |
| `user_id` | `user_data.py` query param | `user_id`（從 middleware 注入） |
| `TEMP_USER_ID` | `news-search.js` hardcode | `authManager.getUserId()` |
| `participant_id` | `chat/schemas.py` | 保留（Chat domain 內部用語） |
| `"anonymous"` | 多處 fallback | 統一的匿名 session 管理 |
| `"authenticated_user"` | `middleware/auth.py` default | 改為明確錯誤處理 |

---

## 七、測試建議

```bash
# 1. 測試 OAuth 流程
curl -X POST http://localhost:8080/api/oauth/token \
  -d '{"code": "xxx", "provider": "google"}'

# 2. 測試認證後的 API
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8080/api/conversations

# 3. 測試對話儲存
curl -X POST -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"messages": [...], "title": "Test"}' \
  http://localhost:8080/api/conversations
```

---

## 八、參考檔案

### 核心認證
- Auth middleware：`code/python/webserver/middleware/auth.py`
- OAuth 路由：`code/python/webserver/routes/oauth.py`
- OAuth 前端：`static/old scripts/oauth-login.js`
- Email 身份：`static/old scripts/identity-service.js`
- 認證測試：`tests/security/test_auth.py`

### User ID 使用
- 請求處理：`code/python/core/baseHandler.py`
- SSE 串流：`code/python/core/utils/message_senders.py`
- Query 記錄：`code/python/core/query_logger.py`
- Analytics：`code/python/core/analytics_db.py`

### 資料隔離
- User Data：`code/python/core/user_data_*.py`
- Qdrant 過濾：`code/python/retrieval_providers/user_qdrant_provider.py`
- 對話歷史：`code/python/core/conversation_history.py`

### Chat 系統
- 參與者：`code/python/chat/participants.py`
- WebSocket：`code/python/chat/websocket.py`
- Schema：`code/python/chat/schemas.py`

### 前端儲存
- 主應用：`static/news-search.js`（localStorage 主要使用者）
- 清理工具：`static/old scripts/clearLocalStore.js`

---

*更新：2026-02-09*
