# 專案上下文

## 目前狀態（2026-02-15）

### 目前重點
**三機協作 Backfill — LTN/CNA 完成，桌機+GCP 雙機跑 Chinatimes sitemap，GCP UDN Phase 2 + Retry 完成**

### 最近完成
- ✅ **GCP UDN Phase 2 + Retry 完成**（UDN sitemap 202401→202409 + failed URL retry）
- ✅ **Chinatimes 雙機協作部署**（`scripts/gcp-chinatimes-sitemap.sh`）
  - engine.py `run_sitemap()` 新增 `sitemap_offset` + `sitemap_count` 參數
  - GCP 自管理腳本從 sub-sitemap #980 往回跑，桌機從 #1 往前跑
  - 適應性批次大小（空區間 x3、密集區 /2）、crash recovery、coverage 報告
- ✅ **Sitemap Date Filter 修復**（`engine.py` `_filter_article_urls_by_date()`）
  - 修復 lastmod 日期優先於 URL 日期的 bug（Chinatimes lastmod=2024 但文章實為 2010）
  - 改為 URL 日期優先、lastmod fallback

---

## 目前工作

### 🔄 進行中

1. **桌機 — Chinatimes sitemap**（重啟，使用 fixed date filter）
   - 已爬 ~53K 篇，298K skipped，重啟後快速 skip 已爬文章
   - 2024+ 文章集中在前 ~30 個 sub-sitemap

2. **GCP — Chinatimes sitemap 雙機協作**（自動腳本運行中）
   - 從 sub-sitemap #980 往回跑，date_from=202401 正確過濾舊文章
   - 自動加速掃過空區間（batch 20→200），與桌機保持 50 緩衝區
   - 腳本：`scripts/gcp-chinatimes-sitemap.sh`

3. **桌機 — einfo full_scan**
   - full_scan + proxy pool，ID 238K → 270K

### 📋 待處理

1. **筆電 MOEA backfill** — `{"sources":["moea"],"start_id":100000,"end_id":122000}`
2. **筆電 UDN sitemap** — MOEA 完成後，`{"source":"udn","mode":"sitemap","date_from":"202410","date_to":"202502"}`
3. **效能優化** — Reasoning 延遲分析與 token 減少

---

## 下一步

### 短期
- 桌機全力 Chinatimes sitemap（2024+ 文章集中在前 ~30 個 sub-sitemap，幾天內可完成）
- GCP 自動掃過舊區間，到達桌機附近自動停止
- 筆電先跑 MOEA backfill，再跑 UDN sitemap 202410→202502

### 中期
- Chinatimes/einfo 完成後，所有 source 第一輪完成
- GCP 資料收回（merge_registry.py）
- 效能優化：延遲分析、token 減少

詳見 `.claude/NEXT_STEPS.md`

---

## 參考資源

- Analytics 儀表板：https://taiwan-news-ai-search.onrender.com/analytics
- Neon 資料庫：https://console.neon.tech
- Render 服務：https://dashboard.render.com
- 實作計畫：`.claude/NEXT_STEPS.md`、`.claude/PROGRESS.md`
- 系統狀態機：`docs/architecture/state-machine-diagram.md`

---

*更新：2026-02-15*
