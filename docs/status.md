# 專案狀態

> 合併自 CONTEXT.md + NEXT_STEPS.md。單一狀態檔案。

**最後更新**：2026-03-19

---

## 目前重點

**全量 Indexing（上線 blocker）+ VPS 部署驗證**

### 最近完成

- **Infra Migration**（2026-03）：PostgreSQL hybrid search（pgvector + pg_bigm）+ Hetzner VPS 部署（twdubao.com + HTTPS + Cloudflare）+ CI/CD（GitHub Actions → SSH deploy → LINE 通知）
- **Login 系統 B2B**（2026-03）：Email/Password + JWT + Session + Audit + B2B bootstrap token onboarding + 強制登入 + 117 tests pass + E2E 兩輪驗證通過
- **Analytics 系統重整**（2026-03）：schema 統一（`schema_definitions.py`）+ async migration + 29 bugs 修復 + B2B 欄位對齊 + click event 修復 + VPS 驗證通過
- **UI Redesign Phase 1-4**（2026-03-16）：藍灰工具風 → 金炭品牌化（讀豹主題），CSS 變數 + 主視覺 + icon + 全站顏色統一
- **GCP Daily Cron**（2026-03-11）：每天 05:00 台灣時間自動 newest scan，第一輪 backfill 完成
- **搜尋品質修復 5 項**（2026-03-19）：虛假回應 guard、PG 日期 filter、MMR 向量、繁中 prompt、verification_status SSE — 52 個新測試

**詳細歷史**：見 `docs/archive/completed-work.md`

---

## 進行中

### 全量 Indexing（上線 blocker）
- **來源**: `data/crawler/articles/`（463 TSV 檔案，~2M+ 篇）
- **進度**: ~236,744 / ~2M 篇（~11.5%），幾乎只有 chinatimes 完成
- **⚠️ 重要**: 舊 `.indexing_done` 是 Qdrant 時代殘留（標 458/463 完成，不反映 PG 狀態）。ltn、cna、udn、einfo、esg 皆未 indexed 進 PG，需重建 `.indexing_done` 後重跑。
- **已修復**: 2 個截斷 checkpoint（LTN）+ 1 個 DB timeout checkpoint（chinatimes）已清除
- **速度**: ~5.6 chunks/sec（GPU 溫控頻繁暫停）
- **腳本**: `run_indexing.sh`（從 `code/python/` 目錄執行）
- **完成後**: pg_dump → scp → VPS pg_restore → 上線

### GCP Crawler
- **Daily Cron**: 每天 05:00 台灣時間自動 newest scan（6 sources）
- **Registry**: ~2,370,000 筆（桌機 master，已同步至 GCP）

---

## 待處理

### ~~BUG: Retrieval 0 結果時仍生成虛假回應~~ → 已修復（2026-03-19）
- Guard 改為 `if not self.source_map`，8 tests

### ~~Login 系統後續~~ → 已完成
- ✅ Email 服務上線（Resend + Cloudflare Email Routing 完成）
- ✅ Bootstrap token onboarding flow 完成（117/117 tests pass）
- ✅ E2E 第一輪 8 個問題全部修復 + 第二輪驗證通過（2026-03-17）

### Analytics E2E 測試（待 indexed data）
- queries 表驗證通過（user_id, org_id, query_length, embedding_model 皆正確）
- 子表驗證待做：VPS 無 indexed data → retrieval 0 結果 → retrieved_documents / ranking_scores 空
- 待全量 indexing 完成後自然驗證，或本地用 SQLite 跑 E2E

### ~~Code Review 後續~~ → RSN-4 已完成（2026-03-19）
- verification_status 從 Critic → Orchestrator → SSE → 前端 warning banner，6 tests

### SEC-6 後續
- Phase 2：Extracted Knowledge（LLM 結構化輸出，Phase 1 驗證有效後）

### ~~UI Redesign 收尾~~ → 已 commit 至 main（2026-03-16）
- 細節微調待 CEO 目視檢查確認

### Session 切換穩定性 ✅（2026-03-13 完成）
- **問題**：搜尋中切換 session → 原 session 結果空白
- **最終方案**：Cancel + Retry Button — 切 session 時直接 cancel stream，標記 `interruptedSearch`，切回顯示 retry 按鈕
- **歷程**：嘗試過 auto re-search（無限迴圈）→ 背景 stream 繼續（stale reference + 跨 session 污染）→ 加 single-stream-per-mode 限制（還是卡住）→ 全部拆掉改 cancel + retry
- **檔案**：`static/news-search.js`

### ~~搜尋品質~~ → 已修復（2026-03-19）
- ✅ 日期 filter PG 失效：`postgres_client.py` 加 kwargs filters 支援，12 tests
- ✅ MMR 多元性無效：PG 回傳 5-tuple 含向量，19 tests
- ✅ 英文摘要：`prompts.xml` 7 處改為繁體中文，7 tests

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
