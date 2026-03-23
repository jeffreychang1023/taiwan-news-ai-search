# 專案狀態

> 合併自 CONTEXT.md + NEXT_STEPS.md。單一狀態檔案。

**最後更新**：2026-03-23

---

## 目前重點

**全量 Indexing（上線 blocker）+ VPS 部署驗證**

### 最近完成

- **Infra Migration**（2026-03）：PostgreSQL hybrid search（pgvector + pg_bigm）+ Hetzner VPS 部署（twdubao.com + HTTPS + Cloudflare）+ CI/CD（GitHub Actions → SSH deploy → LINE 通知）
- **Login 系統 B2B**（2026-03）：Email/Password + JWT + Session + Audit + B2B bootstrap token onboarding + 強制登入 + 117 tests pass + E2E 兩輪驗證通過
- **Analytics 系統重整**（2026-03）：schema 統一（`schema_definitions.py`）+ async migration + 29 bugs 修復 + B2B 欄位對齊 + click event 修復 + VPS 驗證通過
- **UI Redesign Phase 1-5**（2026-03-20）：藍灰工具風 → 金炭品牌化（讀豹主題），CSS 變數 + 主視覺 + icon + 全站顏色統一 + Phase 5: Auth 頁面/Email 模板/Reasoning Chain/Pinned Banner/Citation/進度條品牌化 + 「AI」→「讀豹」全站替換
- **GCP Daily Cron**（2026-03-11）：每天 05:00 台灣時間自動 newest scan，第一輪 backfill 完成
- **搜尋品質修復 + DB 清理 + E2E Gate**（2026-03-19）：虛假回應 guard、PG 日期 filter、MMR 向量、繁中 prompt、verification_status SSE、cosine threshold 0.50、DB dedup（325K→163K）、title dedup、source-info 修正 — 81+ 新測試、CEO 人工 E2E 通過（S1/S3/S5 PASS、S4 已由 Prompt 全面繁中改造解決）
- **Guardrail Phase 1**（2026-03-20）：併發限制 + QuerySanitizer + Prompt 防洩漏 + Chunk 隔離 + Spending Cap + Event Logging — 3 新模組、Agent E2E + CEO E2E 通過
- **Prompt 全面繁中改造**（2026-03-23）：config/prompts.xml 所有 prompt 改造為繁體中文（含 5 個 inline prompts）、18 個 dead code prompt 歸檔至 legacy/、Reasoning agents 精簡冗詞

**詳細歷史**：見 `docs/archive/completed-work.md`

---

## 進行中

### 全量 Indexing（上線 blocker）
- **來源**: `data/crawler/articles/`（475 TSV 檔案，~2M+ 篇）
- **桌機進度**: 224,179 articles / 769,413 chunks（33/475 TSV 完成，chinatimes 33/51、其餘 6 source 未開始）
- **VPS 測試資料**: 500 articles / 1,841 chunks（chinatimes 258 + udn 213 + cna 29）— 可做基本 E2E 測試
- **GPU 溫度保護**: 78°C 暫停 / 70°C 恢復 / 每 50 texts 檢查（2026-03-22 從 83/75/100 調低）
- **腳本**: `run_indexing.sh`（從 `code/python/` 目錄執行），skill: `/run-indexing`
- **完成後**: 全量 pg_dump → scp → VPS pg_restore → 上線

### Guardrail Phase 2（待排）
- **Phase 1 已完成**（2026-03-20）：P1-1~P1-6 全部實作 + CEO E2E 通過
- **Phase 2 待排**：Prompt Injection 偵測、Relevance Detection 啟用、PII 過濾
- **Spec**：`docs/specs/guardrail-spec.md`

### GCP Crawler
- **Daily Cron**: 每天 05:00 台灣時間自動 newest scan（6 sources）
- **Registry**: ~2,370,000 筆（桌機 master，已同步至 GCP）

---

## 待處理

### Analytics E2E 測試（待 indexed data）
- queries 表驗證通過（user_id, org_id, query_length, embedding_model 皆正確）
- 子表驗證待做：VPS 無 indexed data → retrieval 0 結果 → retrieved_documents / ranking_scores 空
- 待全量 indexing 完成後自然驗證，或本地用 SQLite 跑 E2E

### SEC-6 後續
- Phase 2：Extracted Knowledge（LLM 結構化輸出，Phase 1 驗證有效後）

### UI Redesign 殘餘（LOW 優先級）
- Org Modal 管理按鈕、index.html spinner、Analytics/Indexing Dashboard
- Loading spinner 讀豹動畫（CEO 構想中）、citation「讀豹背景知識」字色調整

### 前端 UX 修復（待排）
- 空結果 session 可點擊但顯示「此搜尋無結果」（目前點不進去）
- 「搜尋失敗」文字太 vague，應改為更具體的訊息

### 日期搜尋 UX 改善（待排）
- 指定時間範圍無直接結果時，應告知使用者「指定時間範圍內無結果，但有其他文章提到相關內容」（目前直接顯示跨日期結果，沒有說明）
- 不是 bug — 2024 年底文章提到 2025 年展望是正確的相關結果

### 條件搜尋功能（待排）
- 支援 date range、author 等結構化篩選條件
- 前端需要篩選 UI（日期選擇器、作者欄位等）
- 後端 `_build_filters` 已支援 gte/lte operator，需擴充 field 支援

### Deep Research Ranking 整合研究（待排）
- 目前深度研究有獨立 ranking path：LLM 多維度評分（RankingPromptForGenerate）→ LLM 多元性重排（DiversityReranking），共兩次 LLM call
- 一般搜尋已有 MMR 演算法做多元性（毫秒級，零成本），深度研究未使用
- **研究方向**：用 MMR 取代 DiversityReranking LLM call，減少一次 LLM round trip，降低延遲與成本
- **優先級**：Medium（影響深度研究速度）

---

## 中期任務（1-2 月）

1. **A/B 測試基礎設施** — reasoning vs 標準搜尋 feature flag、查詢路由
2. **模型重訓練管道** — XGBoost ranker 自動重訓練
3. **進階 Reasoning 功能** — 交叉參考偵測、時間分析、比較研究

---

## 長期願景（3-6 月）

- 擴展來源覆蓋（20+ sources）
- 多語言支援
- 使用者個人化
- 線上學習

---

## 參考資源

- 線上服務：https://twdubao.com（Hetzner VPS）
- CI/CD：GitHub Actions（push to main → auto deploy）
- 系統狀態機：`docs/reference/architecture/state-machine-diagram.md`
- 已完成工作：`docs/archive/completed-work.md`
