---
name: 通用技術教訓
description: 跨模組的除錯哲學、Embedding/DB、開發環境、E2E 測試相關教訓。問題模組不明時優先閱讀。
type: feedback
---

## Embedding / Vector DB

### SentenceTransformer prompt_name="query" 必須在 API 端手動複製
**問題**：SentenceTransformer 的 `model.encode(text, prompt_name="query")` 會自動在 text 前加 instruction prefix（`"Instruct: Given a web search query, retrieve relevant passages that answer the query.\nQuery: {text}"`）。透過 OpenRouter API 呼叫同一模型時，API 不會自動加 prefix。結果：local INT8 vs API 的 embedding cosine similarity 只有 avg 0.80（FAIL）。加上 prefix 後提升到 avg 0.982（PASS）。
**解決方案**：API 呼叫時必須手動 prepend 完整 instruction prefix。prefix 內容可從 SentenceTransformer 的 `model.prompts` dict 或模型的 config.json 找到。**通則：embedding model 的 instruction-tuning prefix 是向量語意的一部分，不是可選裝飾。混用不同推論管道（local vs API）時必須確保 prompt template 一致。**
**信心**：高（8 queries benchmark 驗證）
**檔案**：`code/python/embedding_providers/qwen3_embedding.py`
**日期**：2026-03-05

### OpenRouter Qwen3-Embedding-4B 回傳 2560D — 需截斷至 1024D
**問題**：OpenRouter（DeepInfra backend）回傳 Qwen3-Embedding-4B 的完整 2560 維向量，而本地 INT8 用 `truncate_dim=1024` 截斷到 1024D。直接使用 2560D 向量會與 DB 中的 1024D 向量不相容。
**解決方案**：API 回傳後截斷到前 1024 維。Matryoshka embedding 模型的設計保證截斷後的子向量保留語意。截斷後 cosine similarity avg 0.982 驗證相容性。
**信心**：高
**檔案**：`code/python/embedding_providers/qwen3_embedding.py`
**日期**：2026-03-05

### IVFFlat probes 最佳化 — probes=50 是 sweet spot
**問題**：IVFFlat index 的 `probes` 參數影響 recall 和 latency。未經測試直接使用預設值（probes=1）會導致嚴重的 recall 問題。
**解決方案**：Benchmark 118K chunks, lists=1000：probes=20 → R@10=97.0%, avg 21ms；probes=50 → R@10=98.7%, avg 29ms；probes=100 → R@10=98.7%, avg 31ms。probes=50 是 sweet spot（從 20→50 recall 提升 1.7%，50→100 只提升 0%，但 latency 從 29→31ms）。在 `postgres_client.py` 每次查詢前 `SET ivfflat.probes = 50`。
**附註**：Benchmark 時發現 DB 同時有 IVFFlat 和 HNSW index，PostgreSQL 默默選了 HNSW（recall 只有 80%）。需 `EXPLAIN` 確認用了正確的 index。HNSW 和 IVFFlat 在 118K chunks 下大小相同（~930MB），HNSW 無優勢但重建需大量 shared memory。
**信心**：高（benchmark 數據驗證）
**檔案**：`code/python/retrieval_providers/postgres_client.py`, `infra/init.sql`
**日期**：2026-03-05

### psycopg3 無法序列化混合型別 list — OpenRouter embedding 包含 int
**問題**：OpenRouter API 回傳的 embedding vector 中，部分值是 `int`（如 `0`、`1`），其餘是 `float`。Python JSON parser 保留原始型別。psycopg3 將 list 傳給 `%s::vector` 時，發現 `float` 和 `int` 混合，拋出 `psycopg.DataError: cannot dump lists of mixed types; got: float, int`。整個 vector search 路徑失敗。
**解決方案**：在 `postgres_client.py` 的 `search()` 中，取得 embedding 後立即 `query_embedding = [float(v) for v in query_embedding]`。**通則：任何 embedding API 回傳的 vector 都應統一 cast 為 float，不要假設 JSON parse 後的型別一致。**
**信心**：高（smoke test 驗證，修復後 4/4 通過）
**檔案**：`code/python/retrieval_providers/postgres_client.py`
**日期**：2026-03-05

## 開發環境 / 工具

### 評估 skill/工具前必須讀完整內容 — description 不代表全貌
**問題**：CEO 問「我們的 code-reviewer 能從 adversarial-review 學什麼」。Zoe 只看了 system-reminder 的 skill description（一行摘要），就下結論「我們缺少嚴重度分級、結構化輸出」。實際讀完 superpowers:code-reviewer 的 4 個檔案後，發現它早已有 Critical/Important/Minor 分級、完整的 review checklist、結構化 output format。差點基於錯誤資訊 reinvent the wheel。
**解決方案**：**評估任何 skill/工具/模組的能力前，必須讀原始檔案內容。** Description 只是觸發條件摘要，不是功能全貌。Skill 檔案位置：`~/.claude/plugins/cache/claude-plugins-official/superpowers/` 或 `~/.claude/skills/`。
**信心**：高（本次直接踩坑）
**日期**：2026-03-05

### Git uncommitted changes 跟隨 branch switch — 導致改動出現在錯誤 branch
**問題**：Phase 2 infra migration 改動（postgres_client.py rewrite、config 切換等）是 uncommitted working tree changes。中途 `git checkout feature/login-system-merge` 做 login system 工作時，所有 uncommitted changes 跟著切過去。結果：(1) Phase 2 改動看起來「在 login branch 上」，但其實只是 uncommitted changes 隨身攜帶。(2) 如果不注意直接 commit，會把 infra 改動混進 login branch。(3) 上一個 session 用 `git status` 判斷「Phase 2 沒做」也受此影響 — 看到的 diff 是正確的（確實沒 commit），但 branch context 是錯的。
**解決方案**：(1) **大型改動完成後立即 commit 或 stash**，不要讓 uncommitted changes 跨 branch 漂移。(2) 切 branch 前 `git status` 確認沒有不相關的 uncommitted changes。(3) 判斷「某工作是否完成」時，除了 `git status`/`git diff`，也要確認在正確的 branch 上（`git branch --show-current`）。
**信心**：高（本次直接踩坑）
**日期**：2026-03-05

### Crawler Registry 數量 ≠ Indexed 資料量 — confidently wrong
**問題**：把 crawler registry 的 1,910,520 筆當作「Qdrant Cloud 裡有 190 萬筆已 indexed 資料」，在多個回覆中 confidently 引用這個數字。實際上 crawling 和 indexing 是完全分離的流程，registry 只記錄爬蟲抓到的文章，不代表這些文章已經過 indexing pipeline（chunking + embedding + upload）。CEO 從未跑過大規模 indexing，所以 Qdrant Cloud 的實際資料量未知。
**教訓**：(1) **不同 pipeline 階段的數字不可互換**：crawled ≠ indexed ≠ searchable。(2) **不在 memory/docs 裡的事實，不可以猜 — 要嘛問 CEO，要嘛去查**。猜得有信心比說「我不知道」更危險，因為會誤導決策。(3) 這是 lesson #5「過時 memory 會誤導」的變體：不是 memory 過時，而是從一開始就錯誤理解數字的含義。
**信心**：高（CEO 直接指正）
**日期**：2026-03-09

## E2E 測試

### E2E 測試必須模擬人類操作 — fetch() 直打 API 不算 E2E
**問題**：用 Chrome DevTools 的 `evaluate_script` + `fetch()` 直接呼叫 API endpoint 做「E2E 測試」，繞過了前端 UI（表單欄位、submit handler、JS fetch wrapper）。結果：API 層 14/14 PASS，但前端註冊表單**缺少 org_name 欄位**（B2B bootstrap 必需），人工測試立刻發現。fetch() 可以在 JSON body 自由組裝參數，不受限於表單有哪些 input — 這跟真實使用者體驗完全脫節。
**解決方案**：E2E 測試必須模擬人類使用者操作：(1) 用 DevTools `navigate_page` 開頁面 (2) 用 `take_snapshot` 看到什麼元素 (3) 用 `fill` / `click` 操作表單 (4) 用 `take_snapshot` / `take_screenshot` 驗證結果。**絕不用 evaluate_script + fetch() 繞過 UI。** 如果 UI 不存在（純 API），那才用 fetch()，但要明確標記為「API test」而非「E2E test」。
**信心**：高（本次直接踩坑）
**檔案**：N/A（測試方法論）
**日期**：2026-03-12

### 前端與後端 API 參數不同步 — 後端加了參數前端沒跟上
**問題**：B2B 改動在後端 `register_user()` 加了 `org_name` 參數，前端表單和 JS `authManager.register()` 都沒更新。後端 API test 全過（手動帶 org_name），前端完全不能用。
**解決方案**：修改後端 API 參數時，**必須同步檢查前端呼叫端**。搜尋 API endpoint 路徑（如 `/api/auth/register`）在前端的所有呼叫點，確認參數一致。
**信心**：高（本次直接踩坑）
**檔案**：`static/news-search-prototype.html`, `static/news-search.js`, `webserver/routes/auth.py`
**日期**：2026-03-12

## 架構 / 複雜度

### 背景 stream 繼續是假命題 — 簡單 cancel + retry 勝過複雜狀態管理
**問題**：搜尋中切 session 導致結果遺失。嘗試「背景 stream 繼續」方案：soft detach controller、session identity tracking、saveToBackgroundSession、backgroundSearches Map、activeBackgroundStreams Map、single-stream-per-mode 限制。6 層 moving parts，至少 3 種 bug（stale object reference、跨 session 資料污染、loading 狀態卡住）。CEO 測試 3 輪全部失敗。
**根因**：(1) `saveCurrentSession()` 做 `savedSessions[idx] = {...}` 替換整個 object，popup closure 捕舊 reference → stale data。(2) 三種 mode（search/DR/free convo）的 abort 機制不同（AbortController vs EventSource.close），統一追蹤太複雜。(3) 渲染條件順序錯誤（`sessionHistory.length > 0` 排在 `interruptedSearch` 前）。
**解決方案**：全部拆掉，改為最簡方案：cancel + retry button。切 session 時 `cancelAllActiveRequests()`，標記 `interruptedSearch` 在舊 session，切回顯示 retry 按鈕。**教訓：當一個方案需要 3 個 Map + session identity tracking + closure reference 管理，它就是 over-engineered。先用最簡方案。**
**信心**：高（3 輪 CEO 測試驗證：複雜方案全失敗，簡單方案成功）
**檔案**：`static/news-search.js`
**日期**：2026-03-13

## API / Frontend

> CSS selector / opacity / hover 相關教訓已移至 `lessons-frontend.md`

> Auth / Login 相關教訓已移至 `lessons-auth.md`

### 文件更新必須包含 memory — 不只 docs/
**問題**：CEO 說「更新文件」時，只更新了 docs/ 目錄（status, specs, completed-work），沒有同步 memory/ 檔案（lessons-learned, project status）。導致 lessons 遺漏、下個 session 踩同樣坑。
**解決方案**：「更新文件」= docs/ + memory/lessons + memory/project，三個都要做。已整合 /update-docs 和 /learn 為單一 /learn skill。
**日期**：2026-03-17

> Analytics click event、fetch credentials、cookie secure flag、Windows asyncio 等 auth 相關教訓已移至 `lessons-auth.md`

## 文件維護 / 工具系統（2026-03-18）

### /learn 未執行 → 文件大規模腐化
**問題**：文件全面審查發現 14 個 spec/docs 出現大量過時描述：Qdrant 已 deprecated 但仍寫 Qdrant、CSS 變數是舊色、API client 路徑錯誤、algo/ 路徑不存在、測試宣稱 passing 但測試檔案已刪。根因：多個 session 只改了 code，沒有跑 /learn。/learn 雖然存在，但缺乏強制機制：(1) Zoe skill 沒有在 session 結束時提醒跑 /learn (2) /learn 本身缺乏 staleness verification 步驟。
**解決方案**：
1. Zoe skill 加入 session 結束前強制提醒：「你有沒有跑 /learn？」
2. /learn skill 加入分層 staleness verification：層級 1（待做段落驗證，每次強制）+ 層級 2（有改 code 時全文驗證）
3. `/learn specs` 新觸發方式：對所有 spec 做全文驗證（每月或大 milestone 後）
**通則**：**工具必須有機制確保被執行，紀律本身不夠可靠。** 強制提醒 + 分層驗證才能防止腐化累積。
**信心**：高（本次掃描發現 14+ 過時描述，修正後驗證）
**日期**：2026-03-18

### memory 目錄位置混淆 — 兩個 memory 共存
**問題**：本次 session 差點把舊 memory 檔案（`~/.claude/projects/C--users-user-nlweb/memory/`）的內容恢復到專案 memory（`C:/users/user/nlweb/memory/`）。兩個路徑都存在，路徑名稱也相近，很容易混淆。舊路徑是 Claude 工具系統的 global memory；新路徑是專案自管的 memory（在 git repo 裡）。
**解決方案**：專案的 memory 永遠在 `nlweb/memory/`（git repo 內）。CLI 工具的 global memory 在 `~/.claude/projects/.../memory/`（git 外，CLI 自動管理）。操作 memory 前先確認路徑是 `C:/users/user/nlweb/memory/`，不是 `~/.claude/...`。
**通則**：如果指令中提到 memory 路徑，必須顯示完整絕對路徑確認是哪個目錄。
**信心**：高（本次直接差點踩坑）
**日期**：2026-03-18

### status.md「最近完成」的正確粒度
**問題**：status.md 的「最近完成」累積到 13 項，包含「SQL SELECT 漏欄位修復」「cookie secure flag 修復」等個別 bugfix。這導致列表無限增長且難以看出整體進展。
**解決方案**：「最近完成」只記大功能層級（如「Auth 系統完成」「Analytics 系統清理完成」），不記個別 bugfix。個別 bugfix 記在 lessons-general.md。超過 10 項就整批移到 completed-work.md。
**通則**：Status 文件的受眾是「快速了解專案在哪」，不是「查歷史 bugfix」。粒度錯了讀者看不到重點。
**信心**：高（CEO 直接確認）
**日期**：2026-03-18

### Spec 文件的 pending 項目永不更新 — 需要主動驗證機制
**問題**：多個 spec 的「待做」「已知限制」段落記錄了計畫功能，但對應功能完成後沒有人回頭更新 spec。如 analytics-spec 的 6 個待做項、xgboost-spec 的 Phase A 任務全都已完成，spec 卻仍顯示「未完成」。原因：功能完成時只更新 code + completed-work.md，不更新 spec。
**解決方案**：/learn 的層級 1 驗證（每次強制）：對受影響 spec 的待做/限制段落逐項驗證，已完成的加刪除線 + 完成日期。這讓 spec 從「計畫文件」進化為「活文件」。
**通則**：**Spec 的待做清單是技術債，不是靜態記錄。每次 /learn 都必須清一遍。**
**信心**：高（本次掃描發現大量已完成但未標記的項目）
**日期**：2026-03-18

### .indexing_done 跨系統遷移後未重建 — progress tracking 脫節 PG 實際狀態
**問題**：`.indexing_done` 是 Qdrant 時代的 resume 追蹤檔，記錄了 458/463 TSV 檔案為「已完成」。遷移至 PostgreSQL 後未重建，導致看起來「幾乎全部完成」但 PG 實際上只有 ~236K 文章（幾乎全是 chinatimes）。ltn/cna/udn/einfo/esg 等來源完全未 indexed 進 PG。
**解決方案**：(1) 建立 `pg_batch.py` 新 pipeline，使用獨立追蹤檔 `.pg_indexing_done`（不重用舊檔）(2) 啟動時 pre-fetch PG 已有 URLs 自動跳過已 indexed 文章 (3) 舊的 `.indexing_done` 和 `.checkpoint.json` 保留但不再使用。
**通則**：**系統遷移（DB/storage/infra）後，所有 progress tracking 機制都必須重建或驗證。** 追蹤檔是特定 storage backend 的副產品，跨遷移無效。數字要對 target DB 查詢確認，不信任本地 tracking 檔案。
**信心**：高（本次直接踩坑）
**檔案**：`indexing/pg_batch.py`, `run_indexing.sh`
**日期**：2026-03-18

### Pipeline 舊模組 vs 新模組共存 — pipeline.py 用 Qdrant，postgresql_uploader.py 用 PG，但未整合
**問題**：`pipeline.py` 的 CLI 入口使用 VaultStorage（SQLite）+ optional Qdrant。`postgresql_uploader.py` 有完整的 PG upload 能力但沒有 CLI 入口也沒被任何人 import。`run_indexing.sh` 呼叫 `python -m indexing.pipeline` 但 parse 不存在的 "PostgreSQL articles:" 輸出。結果：pipeline 看起來在跑，但資料只進了 SQLite Vault，不進 PG。
**解決方案**：建立 `pg_batch.py` 整合 IngestionEngine + QualityGate + ChunkingEngine + PostgreSQLUploader，提供 single-file 和 batch 兩種 CLI mode。`run_indexing.sh` 改呼叫 `python -m indexing.pg_batch batch`。
**通則**：**pipeline 模組修改後（特別是 storage backend 變更），必須端到端驗證 CLI 入口 → 實際 DB 寫入 → DB 查詢確認。** 中間任何斷裂都會造成「看起來在跑但沒效果」。
**信心**：高
**日期**：2026-03-18

### /learn 只寫入不整理 → 文件漸漸腐化（2026-03-20）
**問題**：文件整理時發現四個累積問題：(1) status.md 累積 6 個 `~~已完成~~` 刪除線項目（完成時只標記沒歸檔）。(2) decisions.md 的 superseded 條目留在 active 區（只標 tag 沒搬移）。(3) CLAUDE.md 和 delegation-patterns.md 重複寫了 Smoke Test / E2E Gate 規則（沒有指定 single source of truth）。(4) lessons-general.md 的 httpOnly auth 區長到 78 行 13 條（沒有按模組分拆門檻）。共同根因：/learn 只負責「寫入新內容」，沒有「整理既有內容」的步驟。
**解決方案**：/learn 新增歸檔步驟：
1. **完成即歸檔**：status.md 項目完成時同步移到 completed-work.md，不留刪除線
2. **superseded 即搬移**：decisions.md 決策被取代時移到「歷史決策」區
3. **Single source of truth**：規則只在一處寫完整版，其他地方一行指標
4. **lessons 分拆門檻**：同一主題超過 3 條就獨立成 `lessons-{module}.md`
**通則**：**文件系統需要「寫入」和「整理」兩個動作。只有寫入的系統會漸漸腐化。**
**信心**：高（本次直接踩坑 — 清理了 4 類問題）
**日期**：2026-03-20

## Skill 開發 / 優化（2026-03-19）

### Skill 優化的兩種方法論 — 漸進式 patch vs 第一性原則重寫
**問題**：優化現有 skill 時，習慣性「在舊文件上加東西」（加段落、修 wording），但舊結構本身可能就是問題根源。例如 /learn 的 staleness verification 散落各處，讀者找不到「這個步驟必須執行」的明確訊號。
**解決方案**：先判斷 skill 的問題來自「缺少內容」還是「結構不對」：(1) 缺內容 → patch 式加段落（快速有效） (2) 結構問題 → 第一性原則重寫（問：這個 skill 的唯一目標是什麼？每個段落有沒有服務這個目標？）。重寫時先列出 skill 的 invariants（不變的核心邏輯），再重新組織圍繞它們。
**通則**：**Gotchas 段落放在 skill 最前面（不是最後面）**，因為位置 = 優先級，讀者在「開始做事」前最需要看到陷阱清單。
**信心**：高（本次 14 個 skills 優化實驗）
**日期**：2026-03-19

### Progressive disclosure 的量化效果 — 373 行 → 65 行（-82%）
**問題**：newest-scan skill 是單一 373 行 markdown，每次調用都把所有 parser 細節、crawler 指令、例外情況全部載入 context。但大多數 scan 是「正常 newest scan」，不需要 parser 細節。
**解決方案**：把 skill 拆為主 `SKILL.md`（65 行，只有核心流程）+ `references/` 目錄（3 個專門參考檔：parser-details、crawler-commands、checkpoint-recovery）。主流程只在需要時 `Read` 對應 reference。結果：常見場景 token 消耗降 82%，罕見場景（需要 reference）才載入完整細節。
**通則**：**Skill 是資料夾，不是 markdown 檔案。** 把「每次都需要的」和「偶爾需要的」分到不同檔案，讓 AI 按需載入而非一次全包。最多 100 行的主 skill 是健康訊號；超過 200 行要考慮拆。
**信心**：高（-82% 是實際量化結果）
**日期**：2026-03-19

### Gotchas 的撰寫標準 — 什麼值得放，什麼不值得
**問題**：為 skills 加 Gotchas 時，容易把所有「可能出問題的事」都列進去，結果 Gotchas 超長，讀者習慣性跳過。
**解決方案**：Gotchas 的正確標準是「這個錯誤 (1) 容易犯 (2) 難以發現 (3) 後果嚴重」三者同時成立。三個條件任一不滿足，移到「注意事項」或正文而非 Gotchas。Gotchas 清單最多 8 項；超過了就說明哪些條目不符合標準，需要降級。
**通則**：**短且高密度的 Gotchas > 長且包山包海的 Gotchas。** 讀者在快速瀏覽時只看前 5 項。
**信心**：中（推論自用戶行為研究，未直接量化驗證）
**日期**：2026-03-19

### 平行派工的邊界 — 小型 4 個、中型 5 個的實際效果
**問題**：Skills 優化時，14 個 skills 分成「小型（4 個平行）」和「中型（5 個平行）」批次處理，但批次大小的根據不明確。
**解決方案**：批次大小的考量：(1) **同檔案禁止平行**（已知原則），(2) 每個 subagent 的預期工作量，(3) 如果 subagent 需要互相參考（如 /zoe 需要參考 /learn 的結構），強依賴的必須序列化。14 個 skills 中，/learn 和 /zoe 是互依賴的（zoe 需要知道 learn 的結構才能寫「session 結束前提醒」邏輯），其餘無相依 → 分批平行。
**通則**：**平行派工前先畫依賴圖**，有邊的 → 序列化；無邊的 → 可平行。不要用「感覺應該 OK」決定平行策略。
**信心**：高（本次實際操作驗證）
**日期**：2026-03-19

### `.claude/commands/` 下的 .md 會被自動註冊為 slash commands
**問題**：把 eval.md 放在 `.claude/commands/` 下（如 `learn-eval.md`、`zoe-eval.md`），結果 Claude Code 自動把它們當作 slash commands 註冊：`/eval`、`/zoe-eval`。這不是預期行為 — eval 檔案是評分標準，不是指令。
**解決方案**：把 eval 檔案移到 `.claude/evals/` 目錄（不在 `commands/` 下）。`commands/` 目錄只放真正的 slash command 定義（/learn、/zoe 等），不放 helper 文件、eval 標準或參考資料。
**信心**：高（本次直接踩坑後驗證）
**日期**：2026-03-19

### Binary Eval 設計原則 — 避免表面症狀與模糊標準
**問題**：設計 /zoe-eval 時，初版包含「有沒有簽名」（表面症狀）和「有沒有跟 CEO 討論」（模糊）兩項 eval。實際測試時：(1) context rot 讓 AI 忘了簽名但核心行為正確 → 表面症狀 pass/fail 不代表 skill 品質。(2) 「有沒有討論」取決於任務性質 → 無法明確判斷 Y/N。
**解決方案**：Binary eval 的設計標準：每項必須可明確判斷 Y/N，且與 skill 的核心行為直接相關（不是副產品）。好的 eval 問「做了什麼」（派工 prompt 附了 spec 路徑嗎？），壞的 eval 問「有沒有這個特徵」（有簽名嗎？）。刪除「簽名檢查」，改為「技術判斷品質」和「subagent review」。
**通則**：**Eval 衡量的是核心行為，不是表面症狀。** 可觀察行為 > 間接指標。
**信心**：高（CEO 直接確認修訂方向）
**日期**：2026-03-19

## DB 遷移 / 介面契約（2026-03-19）

### Qdrant→PG 遷移留下三個 silent fail — 介面契約未完整實作
**問題**：從 Qdrant 遷移到 PostgreSQL 後，`postgres_client.py` 有三個介面未實作但 silent fail：(1) P0：RSN-11 guard 檢查 `formatted_context` 字串，但 `_get_current_time_header()` 永遠非空 → 0 結果時 Writer hallucinate。(2) P1：`search()` 完全不讀 `kwargs['filters']`（日期 filter）→ 所有時間搜尋無效。(3) P2：回傳結果不含 embedding 向量 → MMR 多元性永遠 skip。三個 bug 共同 pattern：Qdrant client 有的功能，PG client 沒實作，且全部 silent fail。
**解決方案**：(1) Guard 改為 `if not self.source_map`（語意檢查，不靠字串）。(2) `_build_filters()` 加 `kwargs_filters` 支援。(3) `search()` 加 `include_vectors` 回傳 5-tuple。**通則：DB/storage 遷移後，必須逐一驗證舊 client 的所有介面在新 client 中有等效實作。Silent fail 是遷移 bug 的最大殺手 — 功能看起來在跑但實際沒有。**
**信心**：高（三個 bug 同一 pattern，52 個測試驗證修復）
**檔案**：`reasoning/orchestrator.py`, `retrieval_providers/postgres_client.py`, `core/ranking.py`
**日期**：2026-03-19

### Guard 條件應檢查語意實體，不是衍生字串
**問題**：RSN-11 guard 用 `if not self.formatted_context` 判斷「有沒有資料」，但 `formatted_context` 除了來源資料還包含 time header。time header 永遠非空 → guard 永遠不觸發 → 0 結果時 reasoning pipeline 繼續跑。
**解決方案**：改為 `if not self.source_map`。`source_map` 是真正的來源字典，只有實際 retrieval 結果才會填入。**通則：guard/branch 條件應該檢查 business logic 的核心實體（source_map），不是衍生表示（formatted_context string）。衍生表示會被其他邏輯（如 header prepend）汙染。**
**信心**：高
**檔案**：`reasoning/orchestrator.py`
**日期**：2026-03-19

### 動態 __dict__ 屬性不會自動 propagate — 需要顯式傳遞
**問題**：RSN-4 的 Critic agent 把 `verification_status` 塞進 `result.__dict__`，但 orchestrator 不知道要讀它，SSE 不知道要送它，前端不知道要收它。用 `__dict__` 塞動態屬性雖然方便，但下游 code 除非明確寫 `getattr(result, 'verification_status', None)`，否則完全看不到。
**解決方案**：在 orchestrator 的 `_format_result` 中顯式讀取並傳入 SSE payload。**通則：pipeline 中的資料傳遞要走顯式路徑（schema 欄位、函式參數），不要靠動態 __dict__。如果必須用 __dict__，下游必須有對應的 getattr 邏輯。**
**信心**：高
**檔案**：`reasoning/orchestrator.py`, `webserver/routes/api.py`
**日期**：2026-03-19

### Prompt 語言指示散佈 7 處 — 改一處漏六處
**問題**：`prompts.xml` 有 7 個位置寫「用跟文章相同語言回應」（RankingPrompt ×2、RankingPromptForGenerate ×3、SummarizeResultsPrompt ×2）。之前修了 SummarizeResultsPrompt 的主文但漏了 returnStruc，其餘 6 處完全沒動。
**解決方案**：用 indexer 搜 "same language" 找到全部 7 處，統一改為「必須用繁體中文」。**通則：config/prompt 檔案的修改必須用全文搜尋確認所有相同 pattern 的位置，不要只改「看到的那一個」。**
**信心**：高（7 個測試覆蓋全部位置）
**檔案**：`config/prompts.xml`
**日期**：2026-03-19

### Regex pattern 定義了但 handler 沒寫 — 同一個 silent fail pattern 的第四次
**問題**：`time_range_extractor.py` L111 定義了 `'yyyy_mm': r'\d{4}年\d{1,2}月'` regex，匹配「2025年12月」沒問題。但 `_try_regex_parsing` 的 if/elif chain 沒有 `yyyy_mm` 的 handler。Regex match 了 → 進入 try block → 沒有 elif 匹配 → 靜默 fall through → 日期篩選無效。這是本次 session 的第四個 silent fail（前三個是 P0/P1/P2 的 Qdrant→PG 介面缺失）。
**解決方案**：(1) 加 `yyyy_mm` handler（用 `calendar.monthrange()` 計算正確月末）。(2) 在 for loop 尾部加 `else` 分支：regex match 了但無 handler → `logger.warning("pattern matched but has no handler - this is a bug")`。**通則：定義功能接口（regex、API route、config key）時，必須同時寫 handler。如果做不到，至少要有 fall-through warning 讓問題浮現。**
**信心**：高（E2E 驗證 + 8 tests）
**檔案**：`core/query_analysis/time_range_extractor.py`
**日期**：2026-03-19

## E2E 測試流程（2026-03-19）

### 背景 server 啟動必須先殺舊 process — port 累積導致不穩定
**問題**：每次用 `run_in_background` 啟動 server 都沒有先 kill 舊的。結果 4 個 Python process 同時 LISTEN 在 port 8000，互相搶連線，server 行為不穩定（有時正常、有時 hang、有時立刻停止）。E2E agent 跑測試時 server 隨機掛掉。
**解決方案**：啟動 server 前必須先 `netstat -ano | grep ":8000.*LISTENING"` + kill 所有舊 PID。**通則：背景 process 管理需要 kill-before-start 紀律。`run_in_background` 不等於「fire and forget」。**
**信心**：高（修正後 server 穩定）
**日期**：2026-03-19

### E2E agent 測試發現 unit test 測不到的問題 — 重複文章 + 前端 JS crash
**問題**：52 個 unit test 全過、smoke 17/17 PASSED，但 agent E2E 發現：(1) 同一篇文章以不同 URL 變體出現 2-3 次（indexing dedup 問題）。(2) `combinedData.content.filter is not a function`（前端 JS 把 string 當 array）。(3) 日期篩選後端正確回 7 篇但前端顯示 0 篇。這三個問題都是 unit test 的盲區 — 只有跑完整 E2E 才能抓到。
**解決方案**：建立 E2E Gate 規則（寫入 delegation-patterns.md）：程式碼改動在 Agent E2E + CEO 人工 E2E 通過前不算完成。**通則：Unit test 驗證模組內部邏輯正確，E2E 驗證端到端行為正確。兩者不可互相替代。**
**信心**：高（本次直接驗證）
**日期**：2026-03-19

## 推論紀律（2026-03-19）

> 詳細規則已寫入 `zoe.md` Gotchas「Confidently wrong」段落。以下為核心教訓摘要。

### 假說不是結論 — 推測必須可驗偽，且驗偽後才能確定
**通則**：推測標為假說 → 列驗偽計畫 → 驗偽後才升級為結論。高信心 ≠ 高正確性。
**日期**：2026-03-19

### 環境變數缺失 → 整個測試 session 測錯 backend
**問題**：本地 server 啟動時沒設 `POSTGRES_CONNECTION_STRING`，系統 fallback 到 Qdrant Cloud。Agent E2E 跑了三輪測試（包括 cosine threshold、URL dedup 等），結果全部是在測 Qdrant 而不是 PG — 所有「改善」和「PASS」都是假的。直到 CEO 人工測試發現 server log 有 `qdrant_client ERROR`（dimension mismatch 1536 vs 1024）才揭露。
**解決方案**：(1) 本地 E2E 測試前必須確認 `POSTGRES_CONNECTION_STRING` 環境變數已設。(2) Server 啟動後第一件事：查 log 確認走哪個 retrieval provider（看到 `qdrant` 還是 `postgres`）。(3) 在 `docs/e2etest.md` 注意事項加環境變數 checklist。
**通則**：**E2E 測試的前提是環境正確。** 如果環境錯了，所有測試結果都是假的。啟動測試前先驗證環境，再跑測試。
**信心**：高（本次直接踩坑，3 輪 agent E2E 白跑）
**日期**：2026-03-19

## Zoe 工作模式（2026-03-19）

### 啟動時自作主張截斷必讀文件 → 批判品質不合格
**問題**：Zoe 啟動時自己決定用 `limit` 截斷必讀文件（status.md limit:50、lessons-general.md limit:60、decisions.md limit:80），漏掉了 LLM 模型策略（第 173 行）和 Rate Limiter 決策（第 159 行）。**沒有任何指令叫 Zoe 截斷這些文件**——Zoe skill 的啟動流程寫的是「全部平行讀取」，是 Zoe 自己為了省 token 偷懶。結果批判 guardrail spec 時：(1) 不知道系統用什麼 LLM model。(2) 不知道 rate limiter 已有 active decision（DR 1/session + 3/IP）。(3) 把自己的無知怪給「memory 沒寫」，CEO 指出 decisions.md 就有寫。
**解決方案**：啟動流程的必讀文件**必須完整讀取**，不可自作主張用 `limit` 截斷。沒有任何指令授權截斷。Zoe skill 已修正：decisions.md 從「掃最近 10 筆即可」改為「全部讀完」。如果文件太長，分段讀完再做任何判斷。
**通則**：**不完整的 context 產出不可靠的判斷。** 自作主張省 token 是最差的節省方式——省下的讀取時間，會在錯誤判斷上加倍浪費。
**信心**：高（CEO 直接指正，本次 session 踩坑）
**日期**：2026-03-19

### 批判 spec 前必須交叉比對 decisions.md
**問題**：guardrail spec 的 P1-1 寫 `/ask` 30/min per IP，但 decisions.md 第 159-162 行已有 active decision：DR 1/session + 3/IP，一般查詢 5/session。兩組數字完全不同維度且未互相引用。因為沒讀完 decisions.md，批判時只說「沒數據」，沒指出「跟既有決策矛盾」——後者才是真正的問題。
**解決方案**：審查任何 spec 前，先確認 decisions.md 中是否有同主題的 active decision。如果有，spec 應該引用或明確說明偏離理由。批判的重點從「你沒有數據」變成「你跟既有決策不一致」。
**通則**：**decisions.md 是 single source of truth。Spec 不應該無視既有決策另起爐灶。**
**信心**：高
**日期**：2026-03-19

### PII 過濾用 exact format validation + checksum，不用 loose regex
**問題**：guardrail spec P2-3 用 `[A-Z][12]\d{8}` 匹配台灣身分證，false positive 高（公司統編、產品型號、門牌號都可能命中）。CEO 建議用 exact format match 避免。
**解決方案**：台灣身分證有 weighted checksum（字母→兩位數，第一位×1 + 第二位×9 + 後續×8,7,6,5,4,3,2,1，mod 10 == 0）。信用卡有 Luhn algorithm。手機號碼有 `09` prefix + 固定 10 碼。加上 checksum/format validation 後，random 字串通過的機率大幅降低，幾乎消除 false positive，運算成本不變（純 CPU，不需 LLM）。
**通則**：**有 checksum 的格式就用 checksum 驗證，不要只靠 regex pattern 匹配。** Regex 只是第一層篩，validation 才是確認。
**信心**：高（CEO 提議，數學上正確）
**日期**：2026-03-19

## B2B SaaS 架構（2026-03-19）

### B2B 環境的 IP rate limit 必須 bypass 已認證用戶
**問題**：Guardrail spec 設 DR 3 併發/IP，但 B2B 企業客戶共享辦公室 NAT IP。4 個記者同時用 DR → 第 4 個被 429。IP 限制在 B2B 場景 = 合法阻斷服務。Gemini review 指出此問題。
**解決方案**：IP 限制只套用在**未認證請求**（防爬蟲/DDoS）。已認證用戶（有 user_id）完全走 user_id/session 級限制，不受 IP 限制。判斷位置：auth middleware 解析 user_id 後，有 user_id → skip IP check。
**通則**：**B2B SaaS 的 rate limit key 永遠是 user_id 或 tenant_id，不是 IP。** IP 只用於匿名流量。
**信心**：高（Gemini 指出 + 邏輯正確）
**日期**：2026-03-19

### SSE 完整 message vs token-level streaming — output filter 的時空限制
**問題**：PII filter 用 regex + checksum 比對（如身分證 10 碼）。若 SSE 改為逐 token streaming，`A123` 已送出、`456789` 才到，regex 來不及攔。Gemini review 指出此問題。
**解決方案**：目前架構用完整 message（階段完成才送），PII filter 無此問題。但在 spec 加 constraint：PII filter 只適用完整 message。若未來改 token-level streaming，需加 token buffer（hold ≥10 字元等 checksum 完成）。
**通則**：**任何基於 pattern matching 的 output filter 都有最小 window 需求。** Streaming 架構設計時必須確認 filter 的 window 需求是否被滿足。
**信心**：高（Gemini 指出 + 工程原理正確）
**日期**：2026-03-19

### Global spending cap 可被武器化為 DoS — per-user budget 才是正解
**問題**：Provider-level spending cap $50/day 是全域的。一個壞帳號刷爆 → 全平台斷流。等於幫攻擊者完成 DoS。Gemini review 指出此問題。
**解決方案**：per-user 併發限制大幅稀釋風險（1 DR 併發 → 刷 $50 需串行 5.5 小時 → alert $30 在 3.3 小時觸發）。但長期需 per-user daily token budget（application layer 追蹤每用戶 LLM 消耗），provider cap 上調至 $150 作為防程式碼 bug 的底線。
**通則**：**全域資源限制（spending cap、connection pool）不應是防用戶的工具，而是防系統 bug 的安全網。** 防用戶用 per-user quota。
**信心**：高
**日期**：2026-03-19

> 前端 / CSS / JS / 瀏覽器相關教訓已移至 `lessons-frontend.md`

## 開發環境 / Server 管理（2026-03-20）

> .news-excerpt CSS display:none 教訓已移至 `lessons-frontend.md`

### PowerShell `set` 不是設環境變數 — 用 `$env:VAR="value"`
**問題**：在 PowerShell 用 `set POSTGRES_CONNECTION_STRING=...` 啟動 server，Python 讀不到 env var，fallback 到 Qdrant。`set` 在 PowerShell 是 `Set-Variable`（程式變數），不是環境變數。CMD 的 `set` 才是環境變數。
**解決方案**：PowerShell 設環境變數用 `$env:POSTGRES_CONNECTION_STRING="..."`。CMD 用 `set POSTGRES_CONNECTION_STRING=...`。
**信心**：高
**日期**：2026-03-20

### load_dotenv() 預設找 cwd 的 .env — project root 的 .env 不會自動載入
**問題**：`app-file.py` 從 `code/python/` 啟動，`load_dotenv()` 預設找 cwd，`.env` 在兩層上面的 `nlweb/.env`。Server 啟動後所有 env var 都是空的。
**解決方案**：用 `pathlib.Path(__file__).resolve().parent.parent.parent / '.env'` 指定絕對路徑。三個入口點（app-file.py, app-aiohttp.py, config.py）都要改。
**信心**：高
**日期**：2026-03-20

### Qdrant 和 PostgreSQL 同時 enabled — server 走了 Qdrant
**問題**：`config_retrieval.yaml` 的 `qdrant_url` 和 `postgres` 兩個 endpoint 都是 `enabled: true`。Server routing 選了 Qdrant，但 Qdrant 的向量維度是 1536（舊 OpenAI），現在 embedding model 是 1024（Qwen3-4B），導致 dimension mismatch → 所有搜尋失敗。
**解決方案**：`qdrant_url: enabled: false`。**通則：DB 遷移後，舊 provider 的 config 必須關閉，不能留 enabled。** 本次花了大量時間 debug「[Errno 22] Invalid argument」，根因其實只是 config 沒關。
**信心**：高（浪費 30+ 分鐘 debug 才找到）
**日期**：2026-03-20

### Claude Code 不應該啟動 server — 殭屍 process 管理不可靠
**問題**：從 Claude Code 的 Bash tool 用 `&` 或 `run_in_background` 啟動 server，產生多個殭屍 process 搶 port 8000。`taskkill //PID ... //F` 有時殺不掉，stderr 被吞（看不到 traceback），process 清理不乾淨。整個 session 累積了 3+ 個殭屍 server。
**解決方案**：(1) Server 由 CEO 從自己的 terminal（PowerShell/CMD）啟動，不從 Claude Code 啟動。(2) 殺 Python process 用 `Get-Process python* | Stop-Process -Force`（PowerShell），而非 `taskkill`。(3) 每次啟動前先確認 port 8000 只有一個 process。
**信心**：高（本次 session 踩坑多次）
**日期**：2026-03-20

*最後更新：2026-03-20*
