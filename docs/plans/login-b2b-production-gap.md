# Login 系統 — B2B Production Ready 差距分析

> Scratchpad for discussion. 2026-03-16

---

## 表格 1：已有功能現況

| 功能 | 後端 API | 前端 UI | Email |
|------|:--------:|:-------:|:-----:|
| Bootstrap（首位 admin 註冊）| ✅ | ✅ login modal | ⚠️ print to terminal |
| Login / Logout | ✅ | ✅ | — |
| httpOnly cookie + refresh rotation | ✅ | ✅ | — |
| `GET /api/auth/me`（當前用戶資訊）| ✅ | — | — |
| Admin 建立員工帳號 | ✅ `/api/admin/create-user` | ⚠️ Org modal 有 invite UI，需釐清 vs create-user | ⚠️ print to terminal |
| 員工啟用帳號（設密碼）| ✅ | ⚠️ 獨立白底頁面，無品牌 | — |
| 忘記密碼 / 重設 | ✅ | ✅ forgot tab + form | ⚠️ print to terminal |
| Org member 管理（invite/list/remove）| ✅ API 齊全 | ✅ org modal | — |
| Brute force / rate limit / lockout | ✅ | — | ⚠️ print to terminal |
| Audit log | ✅ 後端寫入 | ❌ 無查詢 UI | — |
| 強制登入才能使用 | ❌ 搜尋在 PUBLIC | ❌ 前端不 check auth | — |
| 已登入改密碼 | ❌ | ❌ | — |
| Admin 停用/啟用帳號 | ❌ 無 API | ❌ | — |
| Admin 改角色 | ❌ 無 API | ❌ | — |
| Admin 刪除帳號 | ❌ 無 API | ❌ | — |
| 登出全部裝置 | ❌ 無 revoke-all API | ❌ | — |

---

## 表格 2：🔴 必須有才能賣

| # | 項目 | 說明 | 後端 | 前端 | 誰做 |
|---|------|------|:----:|:----:|:----:|
| 1 | **強制登入** | 移除搜尋 PUBLIC_ENDPOINTS + 前端 auth guard | ❌ | ❌ | |
| 2 | **Email 服務上線** | Resend API key + DNS（SPF/DKIM/DMARC）| ❌ 設定 | — | |
| 3 | **已登入改密碼** | `POST /api/auth/change-password` + 前端入口 | ❌ | ❌ | |
| 4 | **登出全部裝置** | revoke all tokens。Admin 對成員 + User 對自己（hover 登出）| ❌ | ❌ | |
| 5 | **Admin 停用/啟用帳號** | set is_active + 前端 org modal | ❌ | ❌ | |
| 6 | **Admin 刪除帳號** | 從 org 移除 + 清理 data + 前端 org modal | ❌ | ❌ | |
| 7 | **Admin 改角色** | member ↔ admin + 前端 org modal | ❌ | ❌ | |
| 8 | **Multi-org 資料隔離** | session CRUD 加 WHERE org_id + 搜尋歷史隔離 | ❌ | — | |

---

## 表格 3：🟡 上線後優先補

| # | 項目 | 說明 |
|---|------|------|
| 9 | **Activation 頁面品牌化** | 目前白底無樣式獨立頁面。加 logo + 品牌色即可 |
| 10 | **Email 文案優化** | 目前是簡單幾行文字 + 連結，功能上夠用。品牌化可後補 |

---

## 表格 4：🟢 可以後面加

| # | 項目 |
|---|------|
| 11 | Audit log 查詢 UI（admin 看操作紀錄）|
| 12 | 使用量 dashboard（客戶看查詢數）|
| 13 | SSO / SAML |
| 14 | 自訂 domain（white-label）|
| 15 | 計費整合（Stripe）|
| 16 | API key 管理 |

---

## 討論紀錄

**R1**：Admin 建員工有 UI、忘記密碼有 UI、Email 全 placeholder、不需登入 = 錯誤
**R2**：User profile 不需要、刪除只給 admin、登出全部裝置 admin+user 都要
**R3**：Activation 頁面 = 獨立白底頁無品牌（非 pop-up）。Email = 簡單文字+連結（非 HTML 模板）。Audit log / 使用量 dashboard / Role 權限強化 → 降級到 🟢。Role 確認：admin 只多 org 管理（增減 user + 強制登出），搜尋不分權限。
**決策**：Email 用 Resend + Cloudflare Email Routing（已記錄 decisions.md #42）
