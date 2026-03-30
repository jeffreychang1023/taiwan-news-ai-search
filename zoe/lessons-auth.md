---
name: Auth / Login 技術教訓
description: httpOnly cookie、SQLite vs PostgreSQL 型別差異、B2B model、async auth 等 Login 系統相關教訓。Auth 模組除錯時閱讀。
type: feedback
---

## httpOnly Cookie Auth — Unit Test 全過但 Production 全壞

### SQLite vs PostgreSQL boolean 不相容 — 硬編碼 `success = 0`
**問題**：`_record_login_attempt` 的 lockout check 用 `success = 0`（integer literal），PostgreSQL 的 `success` column 是 boolean，不能跟 integer 比較。SQLite 不在乎型別所以 unit test 全過。
**解決方案**：改用 parameterized `success = ?` 傳 Python `False`，psycopg 自動轉換。**通則：永遠用 parameterized query，不要硬編碼 boolean/integer literal。**
**日期**：2026-03-16

### PostgreSQL UUID object 不能 JSON 序列化
**問題**：PostgreSQL 回傳 UUID 欄位時是 Python `uuid.UUID` object，`aiohttp.json_response` 無法序列化。SQLite 回傳 string 所以 unit test 全過。
**解決方案**：在 `auth_db.py` 的 `_pg_fetchone` / `_pg_fetchall` 加 `_serialize_row()` 統一轉換。**通則：DB abstraction layer 應該在最底層統一處理型別轉換，不要讓每個 caller 自己處理。**
**日期**：2026-03-16

### httpOnly cookie 模式下 JS 拿不到 access_token — 5 個連環 bug
**問題**：BP-1 把 access_token 從 response body 移到 httpOnly cookie，但前端 JS 多處假設 access_token 在 JS 可用：
1. `login()` 存 `data.access_token`（undefined）到 localStorage → 字串 `"undefined"`
2. `refreshToken()` 同上
3. `isLoggedIn()` 檢查 `!!this._accessToken` → 永遠 false
4. `authenticatedFetch` 只在 `_accessToken` 存在時嘗試 refresh → httpOnly 模式永不 refresh
5. 發送 `Authorization: Bearer undefined` header → 401
**解決方案**：(1) `isLoggedIn()` 只檢查 `_user` (2) 不存 undefined 到 localStorage (3) `authenticatedFetch` 永遠嘗試 refresh on 401 (4) `refreshToken` 只在有值時存 localStorage
**教訓**：**httpOnly cookie 是破壞性變更 — 改了 token 存放位置後，所有讀取 token 的地方都要更新。Unit test 用 SQLite + mock 完全測不到這類問題。Production E2E 是唯一能抓到的方式。**
**日期**：2026-03-16

### Auth guard race condition — async 不 await
**問題**：`checkAuthOnLoad()` 是 async function 但 `DOMContentLoaded` handler 沒有 await，導致後續 code 在 auth check 完成前就跑。
**解決方案**：`DOMContentLoaded` handler 改為 `async () =>` 並 `await checkAuthOnLoad()`。
**教訓**：**async function 如果不 await，它的 side effects（顯示/隱藏 modal）可能被後續 synchronous code 覆蓋。**
**日期**：2026-03-16

### Cloudflare CDN cache 讓部署看不到效果
**問題**：push + deploy 後前端 JS/HTML 被 Cloudflare cache，新版 code 沒生效。即使 `ignoreCache` reload 也不行（nginx 沒設 Cache-Control header）。
**解決方案**：(1) HTML 的 script src 加 cache buster `?v=20260316` (2) nginx 加 `Cache-Control: no-cache, must-revalidate` for `.html` 和 `.js` (3) 每次改前端都 bump cache buster + purge Cloudflare。
**教訓**：**有 CDN 的環境，靜態資源必須有 cache busting 策略。否則部署 = 沒部署。**
**日期**：2026-03-16

## B2B Login E2E（2026-03-17）

### SQL SELECT 漏欄位 → 前端功能壞掉但 unit test 全過
**問題**：`list_org_members` SQL 沒有 SELECT `u.is_active`，前端 `renderOrgMembers` 檢查 `m.is_active === false` 永遠拿不到值，「已停用」badge 和「啟用」按鈕不顯示。Unit test 沒測 response 欄位完整性。
**解決方案**：SQL 加 `u.is_active`。**通則：DB query 的 SELECT 欄位是前後端契約的一部分。改前端 render 邏輯時要同時確認後端有回傳對應欄位。**
**日期**：2026-03-17

### B2B 純 org-bound model — 沒有個人用戶、跨 org 不歸戶
**問題**：原始 login 系統有 `invite_member`（邀請已有帳號加入 org），假設 user 可以跨 org。B2B 場景不適用：user 永遠屬於 org，換公司 = 新帳號，不帶走資料。
**解決方案**：(1) 移除前端 invite flow，改用 `admin_create_user` (2) 刪除帳號時 hard delete + 保留但斷開 session（user_id = NULL）(3) Bootstrap 走 token-based 獨立頁面，不走 login modal 的「註冊」tab。**通則：B2B SaaS 的 user model 跟 C2C 完全不同，不要沿用 self-service registration 的假設。**
**日期**：2026-03-17

### fetch() 不帶 credentials — httpOnly cookie 不會自動送出
**問題**：`handlePostStreamingRequest` 和 `analytics-tracker-sse.js` 的 fetch 呼叫都沒有 `credentials: 'same-origin'`，導致 httpOnly cookie（access_token）不會被送出。Analytics event POST 到後端被 auth middleware 回 401，但 catch block 只用 `console.warn` 記錄 — 開發時極易忽略。
**解決方案**：所有需要帶 auth cookie 的 fetch 加 `credentials: 'same-origin'`。同時把 analytics event endpoints 加到 `PUBLIC_ENDPOINTS`（analytics 不應因 token 過期而丟失）。**通則：httpOnly cookie 模式下，每個 fetch 呼叫都必須明確設 `credentials: 'same-origin'`，這不是 browser 預設行為。**
**日期**：2026-03-17

### cookie secure flag 在 reverse proxy 後面永遠 False
**問題**：`Set-Cookie` 的 `secure=request.secure` 在 nginx reverse proxy 後面永遠是 `False`（nginx 終止 SSL，後端收到的是 HTTP）。Cookie 沒有 Secure flag → 瀏覽器在 HTTPS 頁面不穩定地送出 cookie。
**解決方案**：硬編碼 `secure=True`。Production 永遠是 HTTPS。本地開發用 `NLWEB_DEV_AUTH_BYPASS=true` 繞過 auth。
**日期**：2026-03-17

### Windows asyncio ProactorEventLoop 與 psycopg 不相容
**問題**：Windows 預設 `ProactorEventLoop`，psycopg（async mode）不支援，導致所有 DB 操作失敗：`Psycopg cannot use the 'ProactorEventLoop' to run in async mode`。Server 能啟動但 auth/analytics 全部壞掉。
**解決方案**：在 `app-file.py` 的 `__main__` block 加 `asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())`。必須在 `asyncio.run()` 之前設定。
**日期**：2026-03-17

## Analytics / Auth 交叉問題（2026-03-17）

### Analytics click event 靜默丟棄 — GET/POST SSE 雙路徑不同步
**問題**：前端搜尋走 POST SSE 路徑（`handlePostStreamingRequest`），收到 `begin-nlweb-response` 時只設了 `currentAnalyticsQueryId`，但漏呼叫 `analyticsTracker.startQuery()`。GET SSE 路徑（舊 EventSource code）兩個都有做。`trackClick()` 內部有 `if (!this.currentQueryId) return;` guard — `this.currentQueryId` 永遠是 null → 所有 click 被靜默丟棄。
**解決方案**：POST SSE handler 的 `begin-nlweb-response` case 加 `analyticsTracker.startQuery()` 呼叫。**通則：當系統有多條 code path 到達同一個功能（GET SSE vs POST SSE），修改其中一條時必須搜尋所有 path 確認同步。**
**日期**：2026-03-17

### fetch() 不帶 credentials — httpOnly cookie 不會自動送出
**問題**：`handlePostStreamingRequest` 和 `analytics-tracker-sse.js` 的 fetch 呼叫都沒有 `credentials: 'same-origin'`，導致 httpOnly cookie（access_token）不會被送出。
**解決方案**：所有需要帶 auth cookie 的 fetch 加 `credentials: 'same-origin'`。**通則：httpOnly cookie 模式下，每個 fetch 呼叫都必須明確設 `credentials: 'same-origin'`，這不是 browser 預設行為。**
**日期**：2026-03-17

### cookie secure flag 在 reverse proxy 後面永遠 False
**問題**：`Set-Cookie` 的 `secure=request.secure` 在 nginx reverse proxy 後面永遠是 `False`（nginx 終止 SSL，後端收到的是 HTTP）。
**解決方案**：硬編碼 `secure=True`。Production 永遠是 HTTPS。本地開發用 `NLWEB_DEV_AUTH_BYPASS=true` 繞過 auth。
**日期**：2026-03-17

### Windows asyncio ProactorEventLoop 與 psycopg 不相容
**問題**：Windows 預設 `ProactorEventLoop`，psycopg（async mode）不支援，導致所有 DB 操作失敗。
**解決方案**：在 `app-file.py` 的 `__main__` block 加 `asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())`。必須在 `asyncio.run()` 之前設定。
**日期**：2026-03-17

*最後更新：2026-03-20*
