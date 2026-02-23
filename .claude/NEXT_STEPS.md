# 下一步

## 目前重點（2026-02）

### 🔄 進行中：三機 Backfill 收尾

**目標**：完成所有 7 source 的歷史資料爬取

**已完成 Sources**：
- ✅ LTN：693,273 篇（watermark 5,342,046）
- ✅ CNA：242,011 篇（watermark 2026-02-12）
- ✅ UDN 桌機：2025-08+（完成）
- ✅ ESG BT：backfill 完成

**進行中**：
1. **桌機 — Chinatimes sitemap**（重啟，fixed date filter）
   - 已爬 ~53K 篇，2024+ 文章集中前 ~30 sub-sitemap
2. **GCP — Chinatimes sitemap 雙機協作**（自動腳本運行中）
   - 從 sub-sitemap #980 往回跑，自動加速空區間
   - GCP UDN Phase 2 + Retry 已完成
3. **桌機 — einfo full_scan**
   - ID 238K → 270K，proxy pool
4. **筆電待部署**
   - MOEA backfill（start_id=100000, end_id=122000）
   - UDN sitemap 2024-10→2025-02

### 📋 Backfill 完成後

1. **資料收回**：筆電/GCP 資料 merge_registry.py + retry failed_urls
2. **效能優化**：Reasoning 延遲分析、token 減少

---

## 短期任務（Backfill 完成後）

### 1. 效能優化
**優先級**：高

- 降低 Reasoning 延遲（分析 Analyst/Critic/Writer 瓶頸）
- 優化 prompt token 使用量
- 考慮並行 agent 執行
- 成本分析（各 agent token 使用量）

### 2. 引用品質改善
**優先級**：高

- 幻覺防護邊界案例測試
- 引用連結驗證
- 來源分層規則調整

### 3. UX 改善
**優先級**：中

- 澄清流程 UI
- 長查詢進度指示器
- 使用者回饋迴圈

---

## 中期任務（1-2 月）

### 1. A/B 測試基礎設施
- reasoning vs 標準搜尋 feature flag
- 查詢路由（10% → 50% → 100%）
- 比較指標儀表板

### 2. 模型重訓練管道
- XGBoost ranker 自動重訓練
- 使用者互動資料納入

### 3. 進階 Reasoning 功能
- 交叉參考偵測（矛盾/確認）
- 時間分析（趨勢/時間線）
- 比較研究

---

## 長期願景（3-6 月）

- 擴展來源覆蓋（20+ sources）
- 多語言支援
- 使用者個人化
- 線上學習

---

## 已完成

Track A-T（共 20 個）已完成。詳見 `.claude/COMPLETED_WORK.md`。

---

*更新：2026-02-23*
