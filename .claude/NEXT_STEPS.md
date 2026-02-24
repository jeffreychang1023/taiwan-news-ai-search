# 下一步

## 目前重點（2026-02）

### 🔄 進行中：Backfill 收尾

**目標**：完成所有 7 source 的歷史資料爬取

**已完成 Sources**：
- ✅ LTN：693,273 篇（watermark 5,342,046）
- ✅ CNA：242,011 篇（watermark 2026-02-12）
- ✅ UDN：桌機 2025-08+、GCP 2024-01→2025-07、筆電 2024-10→2025-02（全部合併）
- ✅ ESG BT：backfill 完成
- ✅ MOEA：5,805 篇（筆電，已合併至桌機）
- ✅ 筆電資料合併至桌機（registry 總計 1,910,520 筆）

**進行中**：
1. **GCP — Chinatimes full_scan（新版 multi-category）**
   - Task: `fullscan_chinatimes_29_1771827084`
   - **修復後重啟**：清除 1M+ 舊 not_found、watermark 重設至 2025-06-30
   - 預期覆蓋率 ~95.6%（舊版 ~13%，top 40 category codes）
   - 需持續監控確認效果
2. **桌機 — einfo**（背景，proxy pool）

### 📋 Backfill 完成後

1. **監控 GCP 新 full_scan**：確認 hit rate 從 ~2.5% 提升至預期水準
2. **GCP 資料收回**：`merge_registry.py` 將 GCP Chinatimes 資料合併至桌機
3. **效能優化**：Reasoning 延遲分析、token 減少

---

## 短期任務（Backfill 完成後）

### 0. SEC-6 Phase 1 驗證與 Phase 2
**優先級**：高

**Phase 1 已完成**（`agent_isolation: false`，待驗證）：
- 啟用 `agent_isolation: true`
- 觀察 gap search 查詢的 SEC-6 log（context 不增長、reference sheet reduction %）
- 比對 flag on/off 的引用覆蓋率

**Phase 2（Phase 1 驗證後）**：
- `ExtractedFact` schema（fact + source_ids + relevance）
- Orchestrator 累積邏輯（dedup by fact+source_ids，cap 50）
- Analyst prompt 注入 accumulated_knowledge

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

Track A-W（共 23 個）已完成。詳見 `.claude/COMPLETED_WORK.md`。

---

*更新：2026-02-23*
