# 專案狀態

> 合併自 CONTEXT.md + NEXT_STEPS.md。單一狀態檔案。

**最後更新**：2026-03-16

---

## 目前重點

**全量 Indexing（上線 blocker）+ VPS 部署驗證**

### 最近完成

- **Login Code Review 修復 + Session 切換**（2026-03-13）
  - Code Review: CRITICAL(3) + HIGH(5) + MEDIUM(5) + LOW(2) 全部修復
  - Deep Research 401 fix: 加入 PUBLIC_ENDPOINTS
  - Session cleanup type error fix: time.time() → datetime
  - Session 切換: cancel + retry button（三種 mode 都支援）
- **UI Redesign Phase 1-4**（2026-03-13）
  - 純視覺換皮：藍灰工具風 → 金炭品牌化（讀豹/雲豹主題）
  - Phase 1: CSS 變數換色盤 + Noto Sans TC 字體
  - Phase 2: 首頁主視覺（Banner + 雲豹吉祥物 + 報紙背景）
  - Phase 3: 左側欄 icon 替換 + 右側 tab 深色底 + session B_Black.png 背景
  - Phase 4: 全站硬編碼顏色掃描 + CSS 變數統一
  - 檔案：`static/news-search.css`、`static/news-search-prototype.html`
  - 素材：`static/images/`（12 張品牌素材）
  - 計畫文件：`docs/plans/ui-redesign-plan.md`
  - Branch: `feature/ui-redesign`（未 commit）
- **GitHub Actions CI/CD Pipeline**（2026-03-13）
  - Push to `main` → GitHub Actions → SSH deploy to VPS → Docker rebuild → Health check → LINE 通知
  - 檔案：`.github/workflows/deploy.yml`
  - Deploy SSH key（ed25519）+ VPS git repo 初始化（原為 SCP）
  - LINE Bot push message 通知 success/failure
  - 6 次迭代修復：SSH key 格式、health check port/retry、commit message shell escaping、YAML newline
- **GCP Daily Cron**（2026-03-11）：每天 05:00 台灣時間自動 newest scan
- **Login 系統 B2B Production Ready**（2026-03-16）：
  - Bug fixes（SQLite boolean compat、datetime fix、PUBLIC_ENDPOINTS、route ordering）
  - 113/113 tests pass（適配 B2B bootstrap model）
  - 6 個新後端 API：`change-password`、`logout-all`、admin `logout-user`、`user/active`、`user` DELETE、`user/role`
  - 強制登入：`/ask`、`/api/deep_research`、`/api/feedback` 從 PUBLIC_ENDPOINTS 移除
  - Multi-org session 隔離確認（org_id filter 已有）
  - 前端：auth guard、改密碼 modal、登出 dropdown、admin org modal 擴充（角色切換、停用/啟用、強制登出、刪除）
  - 決策記錄：Transactional email 用 Resend + Cloudflare Email Routing（decisions.md #42）
- **Login B2B + Best Practice**（2026-03-11）：B2B bootstrap + httpOnly cookie + token rotation + async email + XFF validation
- **Login 系統合併**（2026-03-09）：Email/Password + JWT + Session + Audit
- **Infra Migration Phase 2**：PostgreSQL hybrid search + BM25 清理 + Reranking 4-stage pipeline
- **Phase 3 Hetzner VPS 部署**：twdubao.com + HTTPS + Cloudflare

**詳細歷史**：見 `docs/archive/completed-work.md`

---

## 進行中

### 全量 Indexing（上線 blocker）
- **來源**: `data/crawler/articles/`（451 TSV 檔案，6.1GB，~2,058,683 篇）
- **進度**: 222,460 / ~2,058,683 篇（~10.8%），31/451 檔案完成
- **速度**: ~5.6 chunks/sec（GPU 溫控頻繁暫停）
- **腳本**: `run_indexing.sh`（從 `code/python/` 目錄執行）
- **完成後**: pg_dump → scp → VPS pg_restore → 上線

### GCP Crawler
- **Daily Cron**: 每天 05:00 台灣時間自動 newest scan（6 sources）
- **Registry**: ~2,370,000 筆（桌機 master，已同步至 GCP）

---

## 待處理

### Login 系統後續
- Email 服務上線：CEO 註冊 Resend + Cloudflare DNS 設定（decisions.md #42）
- E2E 測試（login 系統）
- Code review（login 系統新 API）
- 前端改動 commit（feature/ui-redesign branch 含 auth guard + admin modal）

### Code Review 後續
- RNK-7：BM25 corpus stats 重建（title weighting 改變）
- RSN-4 前端：讀取 verification_status 顯示未驗證提示

### SEC-6 後續
- Phase 2：Extracted Knowledge（LLM 結構化輸出，Phase 1 驗證有效後）

### UI Redesign 收尾
- 細節微調（Phase 4 後 CEO 目視檢查待修項目）
- Branch `feature/ui-redesign` 尚未 commit

### Session 切換穩定性 ✅（2026-03-13 完成）
- **問題**：搜尋中切換 session → 原 session 結果空白
- **最終方案**：Cancel + Retry Button — 切 session 時直接 cancel stream，標記 `interruptedSearch`，切回顯示 retry 按鈕
- **歷程**：嘗試過 auto re-search（無限迴圈）→ 背景 stream 繼續（stale reference + 跨 session 污染）→ 加 single-stream-per-mode 限制（還是卡住）→ 全部拆掉改 cancel + retry
- **檔案**：`static/news-search.js`

### 搜尋品質
- CEO 手動發現 3 問題：多元性、英文摘要、日期（2026-03-12 回報，待排查）

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
