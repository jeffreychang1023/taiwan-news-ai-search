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
| 0-3 | 填寫表單 → 點「建立組織」                          | 成功訊息，導向登入頁                                           | O     |
| 0-4 | 再開同一個 bootstrap URL                     | 錯誤頁面（token 已使用）                                      | O     |
| 0-5 | 用剛註冊的帳密登入                               | 成功，header 顯示名稱 + 組織按鈕                                | O     |

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
| 3-5 | 停用帳號：點停用                    | 狀態切換                                            | X     |
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
| 6-4 | 點 email 中的連結          | 開啟重設密碼頁面          | X     |
| 6-5 | 設新密碼 → submit         | 成功 → 用新密碼登入       |       |

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

**測試 URL**: https://twdubao.com
**Admin 帳號**: admin@twdubao.com / Twdubao2026!
**VPS SSH**: `ssh -p 2222 root@95.217.153.63`
**DB 查詢**: `docker exec nlweb-postgres psql -U nlweb -d nlweb -c "<SQL>"`

---

## 前置：登入取得 auth cookie

```bash
curl -s -X POST https://twdubao.com/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@twdubao.com","password":"Twdubao2026!"}' \
  -c cookies.txt
```

---

## 搜尋 + Analytics 寫入

| # | 操作 | 預期結果 | Pass? |
|---|------|---------|:-----:|
| A1 | `curl -s "https://twdubao.com/ask?query=台灣AI產業趨勢&site=cna&mode=search" -b cookies.txt --max-time 60` | SSE streaming 回應，有 `begin-nlweb-response` | |
| A2 | 查 `queries` 表：`SELECT query_id, query_text, user_id, org_id, query_length_chars, query_length_words, has_temporal_indicator, embedding_model, latency_total_ms FROM queries ORDER BY timestamp DESC LIMIT 1;` | user_id/org_id 為真實 UUID（非 anonymous）、query_length_chars > 0、embedding_model = 'qwen3-4b'、latency_total_ms > 0 | |
| A3 | 查 `retrieved_documents` 表：`SELECT COUNT(*), MIN(retrieval_position), MAX(retrieval_position) FROM retrieved_documents WHERE query_id = '<A2 的 query_id>';` | COUNT > 0（有文件被 retrieve） | |
| A4 | 查 `retrieved_documents` 細節：`SELECT doc_url, retrieval_algorithm, doc_length, has_author, vector_similarity_score, bm25_score FROM retrieved_documents WHERE query_id = '<query_id>' LIMIT 3;` | retrieval_algorithm = 'postgres_hybrid'、doc_length > 0 | |
| A5 | 查 `ranking_scores` 表：`SELECT doc_url, ranking_position, llm_final_score, ranking_method FROM ranking_scores WHERE query_id = '<query_id>' AND ranking_method = 'llm' ORDER BY ranking_position LIMIT 5;` | ranking_position > 0（非全 0）、llm_final_score > 0、ranking_method = 'llm' | |
| A6 | 確認 ranking_scores 無 LLM 子分數欄位：`SELECT column_name FROM information_schema.columns WHERE table_name = 'ranking_scores' AND column_name LIKE 'llm_%';` | 只有 `llm_final_score` 和 `llm_snippet`，無 `llm_relevance_score` 等 5 個舊欄位 | |

## Analytics REST API

| # | 操作 | 預期結果 | Pass? |
|---|------|---------|:-----:|
| A7 | `curl -s "https://twdubao.com/api/analytics/stats?days=1" -b cookies.txt \| python -m json.tool` | total_queries > 0、avg_latency_ms > 0 | |
| A8 | `curl -s "https://twdubao.com/api/analytics/queries?limit=3" -b cookies.txt \| python -m json.tool` | 回傳最近查詢列表，含 query_text、latency | |
| A9 | `curl -s "https://twdubao.com/api/analytics/export_training_data?days=1" -b cookies.txt \| head -2` | CSV 格式。Header 含 `bm25_score`（非 `text_search_score`）、`latency_total_ms`（非 `query_latency_ms`） | |

## B2B 欄位驗證

| # | 操作 | 預期結果 | Pass? |
|---|------|---------|:-----:|
| A10 | 查 `user_interactions` schema：`SELECT column_name FROM information_schema.columns WHERE table_name = 'user_interactions' AND column_name IN ('user_id', 'org_id');` | 兩個欄位都存在 | |
| A11 | 查 `user_feedback` schema：`SELECT column_name FROM information_schema.columns WHERE table_name = 'user_feedback' AND column_name IN ('query_id', 'user_id', 'org_id');` | 三個欄位都存在 | |
| A12 | 在前端點擊搜尋結果（觸發 click event）→ 查 `user_interactions`：`SELECT query_id, user_id, org_id, interaction_type FROM user_interactions ORDER BY interaction_timestamp DESC LIMIT 1;` | user_id/org_id 為真實 UUID、interaction_type = 'click' | |

## Ranking Pipeline API

| # | 操作 | 預期結果 | Pass? |
|---|------|---------|:-----:|
| A13 | `curl -s "https://twdubao.com/api/ranking/pipeline/<A2 的 query_id>" -b cookies.txt \| python -m json.tool` | 回傳 pipeline 細節（含 llm_final_score、ranking_method） | |

---

## 注意事項

- **A3-A5 需要 indexed data**：VPS 沒有 indexed data 時 retrieval 回 0 結果，子表為空是正常的
- **A12 需要前端操作**：用瀏覽器登入後點擊搜尋結果，curl 無法觸發 click event
- **本地測試**：不需要 VPS，啟動 local server（`python app-file.py`）用 SQLite 即可跑全部測試
