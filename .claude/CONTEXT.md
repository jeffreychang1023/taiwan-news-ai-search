# 專案上下文

## 目前狀態（2026-02-12）

### 目前重點
**全 Source Backfill（2024-02 起）— 7 source 全部從 checkpoint 續跑中**

### 最近完成
- ✅ **Dashboard Bug Fixes + Full Scan 穩定性**（2026-02-11）
  - MOEA FULL_SCAN_OVERRIDES 調整（concurrent=2, delay=2-4s）— 解決 429 限速
  - `null -> null` 顯示 bug 修正（3 層修復：start_crawler + progress handler + engine stats）
  - Task cleanup 自動化（124→13 tasks）
  - 所有 6 source 從 checkpoint 續跑
- ✅ **indexing-spec.md 全面更新**（2026-02-11）
  - MOEA session type 更正、UDN sitemap 推薦、Sitemap Mode 文件、CURL_CFFI_SOURCES 文件
- ✅ **UDN Sitemap Backfill 串接**（2026-02-11）
- ✅ **curl_cffi Reward Hack 清理**（2026-02-11）
- ✅ **Qdrant Profile 切換系統**（2026-02-11）
- ✅ **Crawler 效能與 Dashboard 優化**（2026-02-10）

---

## 目前工作

### 🔄 進行中

1. **全量 Backfill（2024-02 起）** — 6 source 從 checkpoint 續跑中
   - **LTN**: full_scan（ID 4.55M→5.34M），checkpoint=4,557,184
   - **CNA**: full_scan（date 2024-02-19→now），checkpoint=2024-02-19
   - **Chinatimes**: full_scan（date 2024-02-23→now），checkpoint=2024-02-23
   - **einfo**: full_scan（ID 234,701→270K），checkpoint=234,701
   - **ESG BT**: full_scan（date 2024-06-22→now），checkpoint=2024-06-22
   - **MOEA**: full_scan（ID 119,190→121.9K），新設定 ok=8（不再 429）

### 📋 待處理

1. **效能優化** — Reasoning 延遲分析與 token 減少
2. **E2E 測試覆蓋** — 端到端測試完善

---

## 下一步

### 短期
- 監控 backfill 進度，確保各 source 完成
- 完成 E2E 測試覆蓋

### 中期
- Crawler 自動化排程
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

*更新：2026-02-12*
