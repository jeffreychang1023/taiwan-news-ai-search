# Login 系統 E2E 測試 Checklist

> 人工測試用。每次重大 login/auth 變更後跑一遍。

**測試 URL**: https://twdubao.com
**既有 Admin 帳號**: admin@twdubao.com / Twdubao2026!
**建議**: 用無痕視窗，避免 localStorage/cookie 殘留
**Cloudflare**: 如果頁面行為異常，到 Cloudflare dashboard → Purge Cache → Purge Everything

---

## 0. Bootstrap Onboarding（新客戶首次設定）

> 模擬我們發送 bootstrap URL 給新客戶 admin 的完整流程。
> 需要先在 VPS 產生 token：
> ```
> ssh -p 2222 root@95.217.153.63
> docker exec -w /app/python nlweb-app python -m auth.bootstrap_cli --org "客戶公司名" --expires 72
> ```
> 會印出 bootstrap URL。

| # | 操作 | 預期結果 | Pass? |
|---|------|---------|:-----:|
| 0-1 | 開無效 token URL（`/setup?token=random123`）| 錯誤頁面「此連結無效或已過期」| |
| 0-2 | 開有效 bootstrap URL | 組織設定頁面：讀豹 logo + 組織名稱（預填）+ 管理員名稱 + Email + 密碼 + 確認密碼 | |
| 0-3 | 填寫表單 → 點「建立組織」| 成功訊息，導向登入頁 | |
| 0-4 | 再開同一個 bootstrap URL | 錯誤頁面（token 已使用）| |
| 0-5 | 用剛註冊的帳密登入 | 成功，header 顯示名稱 + 組織按鈕 | |

---

## 1. Auth Guard（強制登入）

| # | 操作 | 預期結果 | Pass? |
|---|------|---------|:-----:|
| 1-1 | 無痕視窗 → twdubao.com | Login modal 自動彈出，主 UI 被隱藏 | |
| 1-2 | 點 modal 外面灰色遮罩 | Modal 不關閉（未登入不可關） | |
| 1-3 | 點右上角 X | Modal 不關閉（未登入不可關） | |
| 1-4 | 確認 modal 只有「登入」tab，沒有「註冊」| Login modal 無註冊 tab | |

---

## 2. Login / Logout

| # | 操作 | 預期結果 | Pass? |
|---|------|---------|:-----:|
| 2-1 | 輸入錯誤密碼 → 登入 | 紅字 "Invalid email or password" | |
| 2-2 | 輸入正確密碼 → 登入 | Modal 消失，右上角："名稱 \| 組織 \| 變更密碼 \| 登出" | |
| 2-3 | F5 重新整理 | 維持登入（cookie 持久，不重新顯示 login modal） | |
| 2-4 | 關閉 tab → 重開 twdubao.com | 維持登入 | |
| 2-5 | Hover「登出」按鈕 | 出現 dropdown：「登出」+「登出全部裝置」| |
| 2-6 | 點「登出」| 回到 login modal，主 UI 被隱藏 | |
| 2-7 | 重新登入 → hover 登出 → 「登出全部裝置」| 回到 login modal | |

---

## 3. 組織管理（需 admin 帳號）

> 先用 #0 或既有 admin 登入。#3-3 以後需要至少 2 個用戶（先用 #3-2 建帳號）。

| # | 操作 | 預期結果 | Pass? |
|---|------|---------|:-----:|
| 3-1 | 點「組織」| Modal：成員列表 + 建立帳號表單（員工姓名 + email + 角色 + 建立帳號按鈕）| |
| 3-2 | 輸入員工姓名 + 真實 email → 點「建立帳號」| 成功：「帳號已建立，啟用信已寄出」+ email 信箱收到啟用信 | |
| 3-3 | 新成員出現在列表 | 看到：角色下拉、停用按鈕、強制登出按鈕、刪除按鈕 | |
| 3-4 | 改角色：下拉選「管理員」| 角色即時更新 | |
| 3-5 | 停用帳號：點停用 | 狀態切換 | |
| 3-6 | 強制登出：點強制登出 | 成功提示 | |
| 3-7 | 刪除帳號：點刪除 → 確認 | 成員從列表消失 | |

---

## 4. 員工啟用（需 admin 先建立帳號 #3-2）

| # | 操作 | 預期結果 | Pass? |
|---|------|---------|:-----:|
| 4-1 | 員工收到啟用 email | Email 內有「Activate Account」連結 | |
| 4-2 | 點連結 → 開啟啟用頁面 | 「Set Your Password」表單（密碼 + 確認）| |
| 4-3 | 設定密碼 → submit | 成功提示 "Account activated" | |
| 4-4 | 用新帳號登入 twdubao.com | 成功，header 顯示員工名稱，**無**「組織」按鈕（非 admin）| |

---

## 5. 密碼管理

| # | 操作 | 預期結果 | Pass? |
|---|------|---------|:-----:|
| 5-1 | 點「變更密碼」| Modal：目前密碼 + 新密碼 + 確認密碼 | |
| 5-2 | 輸入錯的目前密碼 → submit | 紅字錯誤 | |
| 5-3 | 輸入正確目前密碼 + 新密碼 → submit | 成功提示 → 自動登出 → login modal | |
| 5-4 | 用新密碼登入 | 成功 | |
| 5-5 | **改回原密碼**（重複 5-1~5-4）| 避免下次測試密碼不對 | |

---

## 6. 忘記密碼

| # | 操作 | 預期結果 | Pass? |
|---|------|---------|:-----:|
| 6-1 | Login modal → 「忘記密碼?」| 切換到 email 輸入表單 | |
| 6-2 | 輸入 email → submit | 成功提示「已寄送重設連結」| |
| 6-3 | 檢查 email 收件匣 | 收到密碼重設 email + 連結 | |
| 6-4 | 點 email 中的連結 | 開啟重設密碼頁面 | |
| 6-5 | 設新密碼 → submit | 成功 → 用新密碼登入 | |

---

## 注意事項

- **Email 是真的**：Resend 已上線，建帳號 / 忘記密碼 / 啟用都會寄真的 email。用真實 email 測試。
- **Cloudflare cache**：前端改動部署後，必須 Purge Cache 才能生效。
- **Admin controls 需要 2+ 用戶**：不能對自己停用/刪除/改角色/強制登出。
- **變更密碼後記得改回來**（#5-5）。
- **Bootstrap token 一次性**：用過就失效，每次測試需重新產生。
- **VPS 產生 token**：`ssh -p 2222 root@95.217.153.63` → `docker exec -w /app/python nlweb-app python -m auth.bootstrap_cli --org "公司名" --expires 72`
