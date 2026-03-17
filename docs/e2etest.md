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
> 
> ```
> ssh -p 2222 root@95.217.153.63
> docker exec -w /app/python nlweb-app python -m auth.bootstrap_cli --org "客戶公司名" --expires 72
> ```
> 
> 會印出 bootstrap URL。

| #   | 操作                                      | 預期結果                                                 | Pass? |
| --- | --------------------------------------- | ---------------------------------------------------- |:-----:|
| 0-1 | 開無效 token URL（`/setup?token=random123`） | 錯誤頁面「此連結無效或已過期」                                      | O     |
| 0-2 | 開有效 bootstrap URL                       | 組織設定頁面：讀豹 logo + 組織名稱（預填）+ 管理員名稱 + Email + 密碼 + 確認密碼 | O     |
| 0-3 | 填寫表單 → 點「建立組織」                          | 成功訊息 → **2 秒自動跳轉首頁**（E1）                             | O     |
| 0-4 | 再開同一個 bootstrap URL                     | 錯誤頁面（token 已使用）                                      | O     |
| 0-5 | 檢查 email 收件匣（含垃圾郵件）                      | **不應收到**驗證信（bootstrap admin 自動驗證）（E2）                 | O     |
| 0-6 | 用剛註冊的帳密登入                               | 成功，header 顯示名稱 + 組織按鈕（不需要先驗證 email）                 | O     |

---

## 1. Auth Guard（強制登入）

| #   | 操作                        | 預期結果                      | Pass? |
| --- | ------------------------- | ------------------------- |:-----:|
| 1-1 | 無痕視窗 → twdubao.com        | Login modal 自動彈出，主 UI 被隱藏 | O     |
| 1-2 | 點 modal 外面灰色遮罩            | Modal 不關閉（未登入不可關）         | O     |
| 1-3 | 點右上角 X                    | Modal 不關閉（未登入不可關）         | O     |
| 1-4 | 確認 modal 只有「登入」tab，沒有「註冊」 | Login modal 無註冊 tab       | O     |

---

## 2. Login / Logout

| #   | 操作                         | 預期結果                                  | Pass? |
| --- | -------------------------- | ------------------------------------- |:-----:|
| 2-1 | 輸入錯誤密碼 → 登入                | 紅字 "Invalid email or password"        | O     |
| 2-2 | 輸入正確密碼 → 登入                | Modal 消失，右上角："名稱 \| 組織 \| 變更密碼 \| 登出" | O     |
| 2-3 | F5 重新整理                    | 維持登入（cookie 持久，不重新顯示 login modal）     | O     |
| 2-4 | 關閉 tab → 重開 twdubao.com    | 維持登入                                  | O     |
| 2-5 | Hover「登出」按鈕                | 出現 dropdown：「登出」+「登出全部裝置」             | O     |
| 2-6 | 點「登出」                      | 回到 login modal，主 UI 被隱藏               | O     |
| 2-7 | 重新登入 → hover 登出 → 「登出全部裝置」 | 回到 login modal                        | O     |

---

## 3. 組織管理（需 admin 帳號）

> 先用 #0 或既有 admin 登入。#3-3 以後需要至少 2 個用戶（先用 #3-2 建帳號）。

| #   | 操作                          | 預期結果                                            | Pass? |
| --- | --------------------------- | ----------------------------------------------- |:-----:|
| 3-1 | 點「組織」                       | Modal：成員列表 + 建立帳號表單（員工姓名 + email + 角色 + 建立帳號按鈕） | O     |
| 3-2 | 輸入員工姓名 + 真實 email → 點「建立帳號」 | 成功：「帳號已建立，啟用信已寄出」+ email 信箱收到啟用信                | O     |
| 3-3 | 新成員出現在列表                    | 看到：角色下拉、停用按鈕、強制登出按鈕、刪除按鈕                        | O     |
| 3-4 | 改角色：下拉選「管理員」                | 角色即時更新                                          | O     |
| 3-5 | 停用帳號：點停用                    | 反饋「已停用」+ 成員旁顯示「已停用」badge + 按鈕變「啟用」  | O     |
| 3-6 | 強制登出：點強制登出                  | 成功提示                                            | O     |
| 3-7 | 刪除帳號：點刪除 → 確認               | 成員從列表消失                                         | O     |

---

## 4. 員工啟用（需 admin 先建立帳號 #3-2）

| #   | 操作                 | 預期結果                                  | Pass? |
| --- | ------------------ | ------------------------------------- |:-----:|
| 4-1 | 員工收到啟用 email       | Email 內有「Activate Account」連結          | O     |
| 4-2 | 點連結 → 開啟啟用頁面       | 「Set Your Password」表單（密碼 + 確認）        | O     |
| 4-3 | 設定密碼 → submit      | 成功提示 "Account activated"              | O     |
| 4-4 | 用新帳號登入 twdubao.com | 成功，header 顯示員工名稱，**無**「組織」按鈕（非 admin） | O     |

---

## 5. 密碼管理

| #   | 操作                      | 預期結果                      | Pass? |
| --- | ----------------------- | ------------------------- |:-----:|
| 5-1 | 點「變更密碼」                 | Modal：目前密碼 + 新密碼 + 確認密碼   | O     |
| 5-2 | 輸入錯的目前密碼 → submit       | 紅字錯誤                      | O     |
| 5-3 | 輸入正確目前密碼 + 新密碼 → submit | 成功提示 → 自動登出 → login modal | O     |
| 5-4 | 用新密碼登入                  | 成功                        | O     |
| 5-5 | **改回原密碼**（重複 5-1~5-4）   | 避免下次測試密碼不對                | XD    |

---

## 6. 忘記密碼

| #   | 操作                    | 預期結果              | Pass? |
| --- | --------------------- | ----------------- |:-----:|
| 6-1 | Login modal → 「忘記密碼?」 | 切換到 email 輸入表單    | O     |
| 6-2 | 輸入 email → submit     | 成功提示「已寄送重設連結」     | O     |
| 6-3 | 檢查 email 收件匣          | 收到密碼重設 email + 連結 | O     |
| 6-4 | 點 email 中的連結          | 開啟品牌化重設密碼頁面（讀豹 logo，非 405） | O     |
| 6-5 | 設新密碼 → submit         | 成功「密碼已重設」→ 2 秒自動跳轉首頁 → 用新密碼登入 | O     |

---

## 注意事項

- **Email 是真的**：Resend 已上線，建帳號 / 忘記密碼 / 啟用都會寄真的 email。用真實 email 測試。
- **Cloudflare cache**：前端改動部署後，必須 Purge Cache 才能生效。
- **Admin controls 需要 2+ 用戶**：不能對自己停用/刪除/改角色/強制登出。
- **變更密碼後記得改回來**（#5-5）。
- **Bootstrap token 一次性**：用過就失效，每次測試需重新產生。
- **VPS 產生 token**：`ssh -p 2222 root@95.217.153.63` → `docker exec -w /app/python nlweb-app python -m auth.bootstrap_cli --org "公司名" --expires 72`

---

---

# Analytics 系統 E2E 測試 Checklist

> 人工測試用。Analytics 相關改動後跑一遍。需要 VPS 有 indexed data（全量 indexing 完成後）。
> 測試分兩部分：**前端操作**（瀏覽器）+ **後端驗證**（SSH 查 DB 確認資料正確寫入）。

**測試 URL**: https://twdubao.com
**Admin 帳號**: admin@twdubao.com / Twdubao2026!
**建議**: 用 Chrome DevTools Network tab 觀察 SSE 和 API 請求

**後端驗證用**（需要時才開）:

- VPS SSH: `ssh -p 2222 root@95.217.153.63`
- DB 查詢: `docker exec nlweb-postgres psql -U nlweb -d nlweb -c "<SQL>"`

---

## A. 搜尋 + Analytics 記錄

| #   | 操作（瀏覽器）                  | 預期結果               | Pass? |
| --- | ------------------------ | ------------------ |:-----:|
| A1  | 開 twdubao.com → 登入       | 登入成功，右上角顯示名稱       | O     |
| A2  | 搜尋框輸入「台灣 AI 產業最新趨勢」→ 按搜尋 | 出現搜尋進度條 → 顯示新聞結果列表 |       |
| A3  | 看結果列表                    | 每筆結果有標題、摘要、來源、日期   |       |
| A4  | 點擊第一筆結果的標題連結             | 開啟新聞原文頁面（新分頁）      |       |
| A5  | 回到搜尋頁，按讚/踩按鈕（如果有的話）      | 按鈕狀態切換             |       |

**後端驗證**（A2 完成後，SSH 進 VPS 查）：

| #   | 驗證項目                    | SQL                                                                                                                                                                        | 預期                                                                                                               | Pass? |
| --- | ----------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------- |:-----:|
| A6  | queries 表有記錄            | `SELECT query_id, query_text, user_id, org_id, query_length_chars, has_temporal_indicator, embedding_model FROM queries ORDER BY timestamp DESC LIMIT 1;`                  | user_id/org_id = 真實 UUID、query_length_chars > 0、has_temporal_indicator = 1（查詢含「最新」）、embedding_model = 'qwen3-4b' |       |
| A7  | retrieved_documents 有記錄 | `SELECT COUNT(*) FROM retrieved_documents WHERE query_id = '<A6 的 query_id>';`                                                                                             | COUNT > 0                                                                                                        |       |
| A8  | retrieval 細節正確          | `SELECT retrieval_algorithm, doc_length, has_author FROM retrieved_documents WHERE query_id = '<query_id>' LIMIT 3;`                                                       | retrieval_algorithm = 'postgres_hybrid'、doc_length > 0                                                           |       |
| A9  | ranking_scores 有記錄      | `SELECT ranking_position, llm_final_score, ranking_method FROM ranking_scores WHERE query_id = '<query_id>' AND ranking_method = 'llm' ORDER BY ranking_position LIMIT 3;` | ranking_position > 0、llm_final_score > 0                                                                         |       |
| A10 | Schema 乾淨（無舊欄位）         | `SELECT column_name FROM information_schema.columns WHERE table_name = 'ranking_scores' AND column_name LIKE 'llm_%';`                                                     | 只有 `llm_final_score` 和 `llm_snippet`                                                                             |       |

**前端驗證**（A4 點擊前後，DevTools Console 觀察）：

| #    | 操作（瀏覽器）                      | 預期結果                                                                                     | Pass? |
| ---- | ---------------------------- | ---------------------------------------------------------------------------------------- |:-----:|
| A11a | A2 搜尋完成後，看 Console           | 有 `[Analytics] Using backend query_id: query_xxx` log（代表 `startQuery` 成功）                |       |
| A11b | 左鍵點擊一筆結果的「閱讀全文」             | Console 出現 `[Analytics-SSE] Click tracked: <url> position: N` + `Event sent: result_clicked` |       |
| A11c | 中鍵（滾輪鍵）點擊另一筆結果              | 同 A11b，Console 出現 click tracked log                                                     |       |
| A11d | 右鍵點擊另一筆結果                   | 同 A11b，Console 出現 click tracked log                                                     |       |

**後端驗證**（A11b-d 點擊後，SSH 進 VPS 查 click 記錄）：

| #    | 驗證項目                     | SQL                                                                                                                                                    | 預期                                                             | Pass? |
| ---- | ------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------ | -------------------------------------------------------------- |:-----:|
| A11e | click 事件有記錄              | `SELECT interaction_type, user_id, org_id, doc_url, result_position FROM user_interactions WHERE interaction_type = 'click' ORDER BY interaction_timestamp DESC LIMIT 3;` | 3 筆 click 記錄、user_id/org_id = 真實 UUID、doc_url 和 result_position 正確 |       |
| A11f | query_id 正確關聯            | `SELECT query_id FROM user_interactions WHERE interaction_type = 'click' ORDER BY interaction_timestamp DESC LIMIT 1;`                                  | query_id 非 NULL，且與 A6 的 query_id 一致                            |       |

**後端驗證**（A5 按讚/踩後）：

| #   | 驗證項目         | SQL                                                                                             | 預期                                                 | Pass? |
| --- | ------------ | ----------------------------------------------------------------------------------------------- | -------------------------------------------------- |:-----:|
| A12 | feedback 有記錄 | `SELECT rating, user_id, org_id, query_id FROM user_feedback ORDER BY created_at DESC LIMIT 1;` | rating = 'positive' 或 'negative'、user_id/org_id 有值 |       |

---

## B. Analytics API（瀏覽器 DevTools 或 curl）

> 登入後在瀏覽器 URL 直接輸入以下網址，或用 DevTools Console 的 `fetch()`。

| #   | 操作                                                                   | 預期結果                                                                                                | Pass? |
| --- | -------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------- |:-----:|
| B1  | 瀏覽器開 `https://twdubao.com/api/analytics/stats?days=7`                | JSON：total_queries > 0、avg_latency_ms > 0                                                           |       |
| B2  | 瀏覽器開 `https://twdubao.com/api/analytics/queries?limit=3`             | JSON 陣列：最近 3 筆查詢，含 query_text、latency                                                               |       |
| B3  | 瀏覽器開 `https://twdubao.com/api/analytics/export_training_data?days=7` | 下載 CSV 檔。開啟確認：header 有 `bm25_score`（非 `text_search_score`）、`latency_total_ms`（非 `query_latency_ms`） |       |
| B4  | 瀏覽器開 `https://twdubao.com/api/ranking/pipeline/<A6 的 query_id>`      | JSON：含 ranking 細節、llm_final_score、ranking_method                                                    |       |

---

## C. B2B 欄位存在性（一次性確認）

> Schema 檢查，只需在 analytics 改動部署後做一次。

| #   | 驗證項目                       | SQL                                                                                                                                           | 預期    | Pass? |
| --- | -------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------- | ----- |:-----:|
| C1  | user_interactions 有 B2B 欄位 | `SELECT column_name FROM information_schema.columns WHERE table_name = 'user_interactions' AND column_name IN ('user_id', 'org_id');`         | 兩個都存在 |       |
| C2  | user_feedback 有 B2B 欄位     | `SELECT column_name FROM information_schema.columns WHERE table_name = 'user_feedback' AND column_name IN ('query_id', 'user_id', 'org_id');` | 三個都存在 |       |

---

## 注意事項

- **A7-A9 需要 indexed data**：VPS 沒有 indexed data 時 retrieval 回 0 結果，子表為空是正常的。等全量 indexing 完成後再驗證。
- **A11 需要真的點擊結果**：前端的 click event handler 觸發 POST /api/analytics/event。左/中/右鍵都會記錄。Console 必須先有 `[Analytics] Using backend query_id` log，click 才會送出（否則被 guard 擋掉）
- **A12 需要按讚/踩按鈕**：如果前端沒有這個 UI，此項跳過
- **B 系列可以用瀏覽器直接開**：登入狀態下 cookie 會自動帶，不需要 curl
- **本地測試**：啟動 local server（`cd code/python && python app-file.py`）用 SQLite 即可跑，不需 VPS

---
---

# E2E Round 2 補測（人工）

> 以下 4 項需要收 email 或查 DB，無法用 DevTools agent 測試。
> **前置**：先 purge Cloudflare cache。

**VPS SSH**: `ssh -p 2222 root@95.217.153.63`
**DB 查詢**: `docker exec nlweb-postgres psql -U nlweb -d nlweb -c "<SQL>"`
**產生 bootstrap token**: `docker exec -w /app/python nlweb-app python -m auth.bootstrap_cli --org "測試公司" --expires 24`

---

## E1: Setup 成功後自動 redirect

| # | 操作 | 預期結果 | Pass? |
|---|------|---------|:-----:|
| E1-1 | SSH 進 VPS → 產生新 bootstrap token | 拿到 URL |  |
| E1-2 | 無痕視窗開 bootstrap URL | 組織設定頁面 |  |
| E1-3 | 填表單 → 點「建立組織」| 顯示「組織建立成功」訊息 |  |
| E1-4 | 等 2 秒 | **自動跳轉到首頁**（login modal）|  |

---

## E2: Bootstrap 不寄驗證 email

| # | 操作 | 預期結果 | Pass? |
|---|------|---------|:-----:|
| E2-1 | 完成 E1 後，檢查 email 收件匣（含垃圾郵件）| **不應收到**「Verify your email」的驗證信 |  |
| E2-2 | 直接用剛註冊的帳密登入 | 登入成功（不需要先驗證 email）|  |

---

## E6: 刪除帳號完整清除

> 需要先有一個可刪除的員工帳號。用 admin 在 org modal 建一個。

| # | 操作 | 預期結果 | Pass? |
|---|------|---------|:-----:|
| E6-1 | Admin 登入 → 組織 → 建立帳號（員工姓名: "刪除測試", email: "delete-test@test.com"）| 成功 |  |
| E6-2 | 記下新 user 的 ID：`docker exec nlweb-postgres psql -U nlweb -d nlweb -c "SELECT id FROM users WHERE email = 'delete-test@test.com';"` | 拿到 UUID |  |
| E6-3 | Org modal → 點該員工的「刪除」→ 確認 | 員工從列表消失 |  |
| E6-4 | 確認 user row 已刪除：`docker exec nlweb-postgres psql -U nlweb -d nlweb -c "SELECT COUNT(*) FROM users WHERE email = 'delete-test@test.com';"` | **COUNT = 0**（hard delete）|  |
| E6-5 | 確認 login_attempts 已清除：`docker exec nlweb-postgres psql -U nlweb -d nlweb -c "SELECT COUNT(*) FROM login_attempts WHERE email = 'delete-test@test.com';"` | COUNT = 0 |  |
| E6-6 | 確認 refresh_tokens 已清除：`docker exec nlweb-postgres psql -U nlweb -d nlweb -c "SELECT COUNT(*) FROM refresh_tokens WHERE user_id = '<E6-2 的 UUID>';"` | COUNT = 0 |  |

---

## E8: 忘記密碼 reset 頁面

> 需要一個有密碼的帳號。用既有 admin@twdubao.com 測。

| # | 操作 | 預期結果 | Pass? |
|---|------|---------|:-----:|
| E8-1 | 無痕開 twdubao.com → login modal → 「忘記密碼?」| 切換到 email 輸入表單 |  |
| E8-2 | 輸入 admin@twdubao.com → submit | 綠字「已寄送重設連結」|  |
| E8-3 | 檢查 email 收件匣 | 收到 reset password email，含連結 |  |
| E8-4 | 點 email 中的連結 | 開啟**品牌化重設密碼頁面**（讀豹 logo + 深藍背景，非 405）|  |
| E8-5 | 輸入新密碼 + 確認密碼 → submit | 顯示「密碼已重設」→ 2 秒後自動跳轉首頁 |  |
| E8-6 | 用新密碼登入 | 成功 |  |
| E8-7 | **改回原密碼**（重複忘記密碼流程或用「變更密碼」）| 避免下次測試密碼不對 |  |
