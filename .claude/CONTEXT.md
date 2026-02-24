# 專案上下文

## 目前狀態（2026-02-23）

### 目前重點
**SEC-6 Lossless Agent Isolation Phase 1 完成 — Reasoning context 路由隔離**

### 最近完成
- ✅ **SEC-6 Phase 1：Agent Isolation Context 路由**（4 檔案）
  - Feature flag `agent_isolation: false`（預設關閉，零行為變更）
  - Gap search 後只傳新文件給 Analyst（`start_id` offset）
  - Critic 收到 reference sheet（僅被引用的 source）而非 full context
  - Analyst re-run 傳 `previous_draft` 保持分析連續性
  - Writer draft 長度監控 + citation 驗證
  - Code review 修復 3 項 bug（stale fallback context、tautological assertion、silent fail）
- ✅ **全專案 Code Review 修復**（21 檔案、47 項）
  - 詳細: `docs/code-review-0223.md`
- ✅ **Chinatimes Multi-Category 修復已部署 GCP**

---

## 目前工作

### 🔄 進行中

1. **GCP — Chinatimes full_scan（新版，multi-category）**
   - Task ID: `fullscan_chinatimes_29_1771827084`
   - 從 2025-06-30 開始掃描（sitemap 覆蓋至 ~mid-2025）
   - 預期覆蓋率：~95.6%（vs 舊版 ~13%）
   - 需監控確認效果

2. **桌機 — einfo**（背景運行）
   - proxy pool 模式

### 📋 待處理

1. **Code Review 後續**
   - SEC-1/9/18/19：JWT 認證（等登入系統設定完成）
   - RNK-7：BM25 corpus stats 重建（title weighting 改變）
   - RSN-4 前端：讀取 verification_status 顯示未驗證提示
2. **SEC-6 Phase 2**：Extracted Knowledge（LLM 結構化輸出，Phase 1 驗證有效後）
3. **監控 GCP 新 full_scan 效果**：確認 hit rate 提升至預期水準
4. **GCP 完成後合併**：`merge_registry.py` 將 GCP 資料合併至桌機
5. **效能優化** — Reasoning 延遲分析與 token 減少

---

## 下一步

### 短期
- **測試 SEC-6 Phase 1**：啟用 `agent_isolation: true`，觀察 gap search 查詢的 log
- Code Review 後續：BM25 corpus stats 重建、前端 verification alert
- 監控 GCP Chinatimes multi-category full_scan 效果

### 中期
- SEC-6 Phase 2：Extracted Knowledge（`ExtractedFact` schema + 累積邏輯）
- JWT 認證系統（SEC-1/9/18/19）
- 效能優化：Reasoning 延遲分析、token 減少
- 所有 source 第一輪完成後啟動 XGBoost retrain

詳見 `.claude/NEXT_STEPS.md`

---

## 參考資源

- Analytics 儀表板：https://taiwan-news-ai-search.onrender.com/analytics
- Neon 資料庫：https://console.neon.tech
- Render 服務：https://dashboard.render.com
- 實作計畫：`.claude/NEXT_STEPS.md`、`.claude/PROGRESS.md`
- 系統狀態機：`docs/architecture/state-machine-diagram.md`

---

*更新：2026-02-23*
