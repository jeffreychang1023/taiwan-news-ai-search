# E2E 測試文件

> **程式碼改動在 E2E 測試通過前不算完成。**
>
> 完整 pipeline：`Unit Test → Smoke Test → Agent E2E (DevTools) → 修 bugs → 寫到本文件 → CEO 人工 E2E → Pass = 完成`
>
> Agent 測試結果記錄在本文件最後面。人工 checklist 在各段落。
> 詳細流程規則見 `memory/delegation-patterns.md`「E2E Gate」段落。

---

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
| 0-5 | 檢查 email 收件匣（含垃圾郵件）                     | **不應收到**驗證信（bootstrap admin 自動驗證）（E2）                | O     |
| 0-6 | 用剛註冊的帳密登入                               | 成功，header 顯示名稱 + 組織按鈕（不需要先驗證 email）                  | O     |

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
| 3-5 | 停用帳號：點停用                    | 反饋「已停用」+ 成員旁顯示「已停用」badge + 按鈕變「啟用」              | O     |
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

| #   | 操作                    | 預期結果                          | Pass? |
| --- | --------------------- | ----------------------------- |:-----:|
| 6-1 | Login modal → 「忘記密碼?」 | 切換到 email 輸入表單                | O     |
| 6-2 | 輸入 email → submit     | 成功提示「已寄送重設連結」                 | O     |
| 6-3 | 檢查 email 收件匣          | 收到密碼重設 email + 連結             | O     |
| 6-4 | 點 email 中的連結          | 開啟品牌化重設密碼頁面（讀豹 logo，非 405）    | O     |
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

| #    | 操作（瀏覽器）            | 預期結果                                                                                         | Pass? |
| ---- | ------------------ | -------------------------------------------------------------------------------------------- |:-----:|
| A11a | A2 搜尋完成後，看 Console | 有 `[Analytics] Using backend query_id: query_xxx` log（代表 `startQuery` 成功）                    |       |
| A11b | 左鍵點擊一筆結果的「閱讀全文」    | Console 出現 `[Analytics-SSE] Click tracked: <url> position: N` + `Event sent: result_clicked` |       |
| A11c | 中鍵（滾輪鍵）點擊另一筆結果     | 同 A11b，Console 出現 click tracked log                                                          |       |
| A11d | 右鍵點擊另一筆結果          | 同 A11b，Console 出現 click tracked log                                                          |       |

**後端驗證**（A11b-d 點擊後，SSH 進 VPS 查 click 記錄）：

| #    | 驗證項目          | SQL                                                                                                                                                                       | 預期                                                                 | Pass? |
| ---- | ------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------ |:-----:|
| A11e | click 事件有記錄   | `SELECT interaction_type, user_id, org_id, doc_url, result_position FROM user_interactions WHERE interaction_type = 'click' ORDER BY interaction_timestamp DESC LIMIT 3;` | 3 筆 click 記錄、user_id/org_id = 真實 UUID、doc_url 和 result_position 正確 |       |
| A11f | query_id 正確關聯 | `SELECT query_id FROM user_interactions WHERE interaction_type = 'click' ORDER BY interaction_timestamp DESC LIMIT 1;`                                                    | query_id 非 NULL，且與 A6 的 query_id 一致                                |       |

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

| #    | 操作                              | 預期結果                     | Pass? |
| ---- | ------------------------------- | ------------------------ |:-----:|
| E1-1 | SSH 進 VPS → 產生新 bootstrap token | 拿到 URL                   |       |
| E1-2 | 無痕視窗開 bootstrap URL             | 組織設定頁面                   |       |
| E1-3 | 填表單 → 點「建立組織」                   | 顯示「組織建立成功」訊息             |       |
| E1-4 | 等 2 秒                           | **自動跳轉到首頁**（login modal） |       |

---

## E2: Bootstrap 不寄驗證 email

| #    | 操作                          | 預期結果                            | Pass? |
| ---- | --------------------------- | ------------------------------- |:-----:|
| E2-1 | 完成 E1 後，檢查 email 收件匣（含垃圾郵件） | **不應收到**「Verify your email」的驗證信 |       |
| E2-2 | 直接用剛註冊的帳密登入                 | 登入成功（不需要先驗證 email）              |       |

---

## E6: 刪除帳號完整清除

> 需要先有一個可刪除的員工帳號。用 admin 在 org modal 建一個。

| #    | 操作                                                                                                                                                       | 預期結果                       | Pass? |
| ---- | -------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------- |:-----:|
| E6-1 | Admin 登入 → 組織 → 建立帳號（員工姓名: "刪除測試", email: "delete-test@test.com"）                                                                                        | 成功                         |       |
| E6-2 | 記下新 user 的 ID：`docker exec nlweb-postgres psql -U nlweb -d nlweb -c "SELECT id FROM users WHERE email = 'delete-test@test.com';"`                        | 拿到 UUID                    |       |
| E6-3 | Org modal → 點該員工的「刪除」→ 確認                                                                                                                                | 員工從列表消失                    |       |
| E6-4 | 確認 user row 已刪除：`docker exec nlweb-postgres psql -U nlweb -d nlweb -c "SELECT COUNT(*) FROM users WHERE email = 'delete-test@test.com';"`                | **COUNT = 0**（hard delete） |       |
| E6-5 | 確認 login_attempts 已清除：`docker exec nlweb-postgres psql -U nlweb -d nlweb -c "SELECT COUNT(*) FROM login_attempts WHERE email = 'delete-test@test.com';"` | COUNT = 0                  |       |
| E6-6 | 確認 refresh_tokens 已清除：`docker exec nlweb-postgres psql -U nlweb -d nlweb -c "SELECT COUNT(*) FROM refresh_tokens WHERE user_id = '<E6-2 的 UUID>';"`      | COUNT = 0                  |       |

---

## E8: 忘記密碼 reset 頁面

> 需要一個有密碼的帳號。用既有 admin@twdubao.com 測。

| #    | 操作                                      | 預期結果                                  | Pass? |
| ---- | --------------------------------------- | ------------------------------------- |:-----:|
| E8-1 | 無痕開 twdubao.com → login modal → 「忘記密碼?」 | 切換到 email 輸入表單                        |       |
| E8-2 | 輸入 admin@twdubao.com → submit           | 綠字「已寄送重設連結」                           |       |
| E8-3 | 檢查 email 收件匣                            | 收到 reset password email，含連結           |       |
| E8-4 | 點 email 中的連結                            | 開啟**品牌化重設密碼頁面**（讀豹 logo + 深藍背景，非 405） |       |
| E8-5 | 輸入新密碼 + 確認密碼 → submit                   | 顯示「密碼已重設」→ 2 秒後自動跳轉首頁                 |       |
| E8-6 | 用新密碼登入                                  | 成功                                    |       |
| E8-7 | **改回原密碼**（重複忘記密碼流程或用「變更密碼」）             | 避免下次測試密碼不對                            |       |

---

---

# 搜尋品質 E2E 測試 Checklist

> 人工測試用。搜尋/排序/Reasoning 相關改動後跑一遍。
> **前提**：VPS 必須有 indexed data（全量 indexing 完成後）。本地測試需啟動 server + PG 有資料。

**測試 URL**: https://twdubao.com（或 `localhost:8080`）
**Admin 帳號**: admin@twdubao.com / Twdubao2026!
**建議**: 用 Chrome DevTools Console + Network tab 觀察

---

## S1. 零結果不 hallucinate（P0 修復驗證）

> 驗證 retrieval 0 結果時不會生成虛假回應。
> 需要一個保證搜不到結果的查詢。

| #    | 操作（瀏覽器）                             | 預期結果                                                      | Pass? |
| ---- | ------------------------------------- | ----------------------------------------------------------- |:-----:|
| S1-1 | 搜尋完全無關的 gibberish：「xyzzy12345 qwrtp」 | **不應顯示**「基於 N 則報導生成」的研究報告                                  |       |
| S1-2 | 觀察回應內容                               | 應顯示「找不到相關結果」或類似空結果提示，**不應有 hallucinated 內容**                |       |
| S1-3 | DevTools Console                       | 無 Writer/Analyst agent 錯誤 log（pipeline 應在 guard 階段就返回）      |       |

**Deep Research 版本**：

| #    | 操作（瀏覽器）                                     | 預期結果                                                             | Pass? |
| ---- | --------------------------------------------- | ------------------------------------------------------------------ |:-----:|
| S1-4 | 切換到 Deep Research 模式 → 搜「xyzzy12345 qwrtp」   | 應顯示無法找到相關資料的訊息，**不應有虛假研究報告**                                      |       |
| S1-5 | 觀察 SSE stream（DevTools Network → EventStream） | 應收到 `no_results` 或 error 類型 event，**不應收到 `final_result` + 假來源清單** |       |

---

## S2. 日期篩選有效（P1 修復驗證）

> 驗證時間相關查詢確實做日期篩選。
> 需要 PG 有不同日期的文章。

| #    | 操作（瀏覽器）                    | 預期結果                                              | Pass? |
| ---- | ---------------------------- | --------------------------------------------------- |:-----:|
| S2-1 | 搜「台灣 AI 最近三天」              | 結果列表中的文章日期都在最近 3 天內                                 |       |
| S2-2 | 搜「2025 年 12 月 台積電」         | 結果主要集中在 2025-12 月                                   |       |
| S2-3 | 搜不帶日期的通用查詢「半導體產業趨勢」        | 結果不限特定日期範圍（跟 S2-1/S2-2 對比，確認 filter 只在有時間意圖時啟動）   |       |

**後端驗證**（S2-1 完成後，SSH 查 analytics）：

| #    | 驗證項目                   | SQL                                                                                                              | 預期                                              | Pass? |
| ---- | ---------------------- | ---------------------------------------------------------------------------------------------------------------- | ----------------------------------------------- |:-----:|
| S2-4 | 時間意圖被正確偵測              | `SELECT has_temporal_indicator FROM queries ORDER BY timestamp DESC LIMIT 1;`                                     | has_temporal_indicator = true（S2-1）或 1           |       |
| S2-5 | retrieved_documents 日期正確 | `SELECT doc_url, doc_date FROM retrieved_documents WHERE query_id = '<S2-1 的 query_id>' ORDER BY doc_date DESC;` | doc_date 都在最近 3 天內                              |       |

---

## S3. MMR 多元性（P2 修復驗證）

> 驗證搜尋結果不全來自同一來源。
> 需要 PG 有多個來源的 indexed data。

| #    | 操作（瀏覽器）                  | 預期結果                                                | Pass? |
| ---- | -------------------------- | ----------------------------------------------------- |:-----:|
| S3-1 | 搜廣泛主題「台灣經濟」              | 結果列表中有 **2 個以上不同來源**（如 CNA + LTN + UDN）             |       |
| S3-2 | 觀察結果卡片的來源標籤              | 不應全部是同一家媒體                                           |       |
| S3-3 | 搜另一個廣泛主題「能源政策」           | 同上，至少 2 個不同來源                                        |       |

**後端驗證**（S3-1 完成後）：

| #    | 驗證項目               | SQL                                                                                                                                         | 預期                                              | Pass? |
| ---- | ------------------ | ------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------- |:-----:|
| S3-4 | MMR 有執行            | `SELECT ranking_method FROM ranking_scores WHERE query_id = '<query_id>' AND ranking_method = 'mmr' LIMIT 1;`                                | 有記錄（代表 MMR 有跑，不是 skip）                          |       |
| S3-5 | 來源多元               | `SELECT DISTINCT source FROM retrieved_documents WHERE query_id = '<query_id>';`                                                             | 2 個以上不同 source                                  |       |
| S3-6 | MMR diversity score | `SELECT ranking_position, mmr_diversity_score FROM ranking_scores WHERE query_id = '<query_id>' AND ranking_method = 'mmr' ORDER BY ranking_position;` | mmr_diversity_score 有值（非 NULL）                  |       |

---

## S4. 繁體中文回應（P3 修復驗證）

> 驗證所有搜尋回應都是繁體中文。

| #    | 操作（瀏覽器）                 | 預期結果                                             | Pass? |
| ---- | ----------------------- | -------------------------------------------------- |:-----:|
| S4-1 | 搜「semiconductor trends」 | 結果的摘要/描述是**繁體中文**，不是英文                             |       |
| S4-2 | 搜「ESG carbon neutral」   | 結果摘要是繁中（即使查詢是英文）                                  |       |
| S4-3 | 搜「台積電」                  | 結果摘要是繁中（確認中文查詢也正常）                                |       |
| S4-4 | 切 Deep Research → 搜任意主題  | 研究報告全文是繁體中文，**無英文段落混入**                            |       |

---

## S5. Verification Status 提示（RSN-4 驗證）

> 驗證 CoV 未驗證時前端顯示 warning banner。
> **注意**：CoV 只在 Deep Research 模式觸發。不一定每次都 fail，需要一個容易觸發 unverified 的查詢。

| #    | 操作（瀏覽器）                                | 預期結果                                                               | Pass? |
| ---- | ---------------------------------------- | -------------------------------------------------------------------- |:-----:|
| S5-1 | Deep Research → 搜一個有爭議性的主題（如「核電爭議」）    | 等研究報告完成                                                             |       |
| S5-2 | 觀察報告上方                                  | 如果 CoV 判定 unverified → 應出現**黃色 warning banner**「本報告未經完整事實驗證」         |       |
| S5-3 | 如果 CoV pass（verified）                   | 不應出現 warning banner（這是正常情況）                                          |       |
| S5-4 | DevTools Network → 找 SSE `final_result` event | 檢查 JSON 中有 `verification_status` 欄位（"verified" 或 "unverified"）       |       |

**強制測試法**（如果自然觸發困難）：

| #    | 操作                                                                               | 預期結果                          | Pass? |
| ---- | -------------------------------------------------------------------------------- | ----------------------------- |:-----:|
| S5-5 | 臨時改 `config/config_reasoning.yaml` 的 `enable_cov: true` + 搜一個資料少的冷門主題 | CoV 更容易 fail → banner 更可能出現    |       |
| S5-6 | 測完後改回原 config                                                                    | 確認 config 恢復                   |       |

---

## 注意事項

- **S1-S5 全部需要 indexed data**：VPS 全量 indexing 完成前，只能用本地 server + 本地 PG 測試。
- **S2 日期測試有時效性**：「最近三天」的結果取決於 indexed data 的日期範圍。如果最新資料是一個月前的，測試結果會不符預期。建議先確認 `SELECT MAX(date_published) FROM articles;`。
- **S3 MMR 需要多來源**：如果 PG 只有 chinatimes 的資料（目前狀態），MMR 無法展示跨來源多元性。需要等多來源 indexing 完成。
- **S5 CoV 不一定觸發 fail**：verification_status 的 warning banner 只在 CoV 判定 unverified/partially_verified 時出現。大多數正常查詢會 pass。可用 SSE `final_result` 的 JSON 確認欄位是否存在（S5-4）來驗證管線通了。
- **本地測試**：`cd code/python && python app-file.py` → `localhost:8000`。需要 PG 有 indexed data。
- **啟動前必殺舊 process**：`netstat -ano | grep ":8000.*LISTENING"` 確認無殘留。多個 server 搶同一 port 會導致不穩定。

---

---

# Agent E2E 測試記錄

> Agent 用 Chrome DevTools MCP 跑的自動化測試結果。每次 E2E 測試 session 追加在此。

---

## 2026-03-19 — 搜尋品質修復 E2E（本地 localhost:8000）

**環境**：本地 PG（325K articles, 1.1M chunks, 5 來源），localhost:8000
**測試項目**：S1-S4（S5 Deep Research 跳過 — port 衝突已修，待重測）

### 結果總表

| 場景 | 結果 | 問題摘要 |
|------|------|---------|
| S1 零結果 hallucinate | **FAIL** | 亂碼查詢仍回 10 篇 + AI 摘要（vector search 永遠回 top-k，非 P0 regression） |
| S2 日期篩選 | **FAIL** | 後端找到 7 篇但前端顯示 0 篇 + 「找不到」矛盾訊息 |
| S3 MMR 多元性 | **FAIL** | 全 chinatimes（資料不均）+ 嚴重重複文章 |
| S4 繁體中文 | **PASS** | 英文查詢 → 繁中摘要，正確 |

### 跨場景共通問題

**重複文章（Critical）**：每個測試都出現。同一篇文章以不同 URL 變體出現 2-3 次：
- S1：「台灣人最愛用的爛密碼」x2、「面試官問 3,4,5」x2
- S3：「童子賢：電力求穩」x3、「核管法擇期再審」x2
- S4：幾乎每篇都 x2

**S2 前端 bug**：`combinedData.content.filter is not a function`（已修 Array.isArray check，但仍顯示 0 篇文章 — 可能有更深層問題）

### 待修項目

| # | 問題 | 類型 | 嚴重度 |
|---|------|------|--------|
| 1 | 重複文章（indexing dedup） | Indexing bug | High |
| 2 | S2 前端文章不顯示 | Frontend bug | Medium |
| 3 | S1 gibberish 仍回結果 | 缺 relevance threshold | Medium（新 issue） |
| 4 | S5 Deep Research 待重測 | 未測 | — |

---

## 2026-03-19 — 修復後第二輪 E2E（F1-F4 修復驗證）

**環境**：同上（localhost:8000）
**修復內容**：F1 cosine threshold + F2 URL dedup + F3 title+source dedup（sendAnswers 層） + F4 frontend Array.isArray

### 結果總表

| 場景 | 第一輪 | 第二輪 | 改善 |
|------|--------|--------|------|
| S1 零結果 | 10 篇 + AI 摘要 | 2 篇 + AI 摘要 | **80% reduction**，threshold 有效但 gibberish embedding similarity 仍 >=0.40 |
| S2 日期篩選 | JS crash + 0 篇 | 無 JS crash + 0 篇 | **F4 前端修復成功**，後端 answer.items=[] 是另一個問題 |
| S3 重複文章 | 10 篇（5 unique x2-3） | **5 篇無重複** | **PASS — dedup 完全生效** |
| S4 繁中 | PASS | PASS | 維持 |

### 仍有的問題

| # | 問題 | 根因 | 優先級 |
|---|------|------|--------|
| 1 | S1 gibberish 仍回 2 篇 | Embedding model 對 gibberish 產出 cosine >=0.40 的向量。threshold 從 0.40 調高可解，但 CEO 指示「最少 40%，之後再調」 | Low（可調 config） |
| 2 | S2 後端 answer.items=[] | 後端找到 7 篇但 `answer` SSE event 回空 items。可能是 summarize mode 的 response 結構問題 | Medium（待查） |
| 3 | S5 Deep Research | 未重測（之前 hang 可能是 port 衝突） | Medium（待測） |
| 4 | S5 Deep Research 待重測 | 未測 | — |
