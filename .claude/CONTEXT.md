# 專案上下文

## 目前狀態（2026-01-28）

### 目前重點
**Reasoning 系統強化** - Free Conversation Mode + CoV 事實查核

### 最近完成
- ✅ **Free Conversation Mode**（2026-01-28）
  - 注入之前的 Deep Research 報告進行後續 Q&A
  - 支援多輪對話延續研究上下文
- ✅ **Phase 2 CoV**（2026-01-28）
  - Chain of Verification 事實查核
  - 整合於 Critic Agent
- ✅ Tier 6 API 整合（Stock, Weather, Wikipedia）
- ✅ Track D：Reasoning 系統（Actor-Critic 架構）
- ✅ Track E：Deep Research Method（時間範圍、澄清、引用）
- ✅ Track F：XGBoost Phase C（ML ranking 完整部署）

### 先前完成
- ✅ Track A：Analytics 基礎設施
- ✅ Track B：BM25 實作
- ✅ Track C：MMR 實作
- ✅ XGBoost Phase A/B
- ✅ M0 Phase 0：POC 分塊策略驗證

---

## 目前工作

### 🔄 Reasoning 系統優化

**已完成強化**：
- Free Conversation Mode：後續 Q&A 可延續 Deep Research 上下文
- CoV 事實查核：Critic Agent 執行 Chain of Verification

**待優化項目**：
- 延遲分析與 token 減少
- 引用 UX 改進
- 效能監控

### 📋 M0 Indexing Module（暫緩）

**Phase 0 POC 結論**（已完成）：
- 採用長度優先策略：170 字/chunk
- 區別度 ~0.56（理想範圍）
- POC 程式碼位於 `code/python/indexing/poc_*.py`

**詳細計畫**：`docs/index-plan.md`

---

## 下一步

### 短期
- 效能優化：Reasoning 延遲分析
- 引用品質改善
- 成本優化：token 使用量分析

### 中期
- M0 Indexing Module Phase 1-4
- 遷移現有 Qdrant 資料到新格式

詳見 `.claude/NEXT_STEPS.md`

---

## 參考資源

- Analytics 儀表板：https://taiwan-news-ai-search.onrender.com/analytics
- Neon 資料庫：https://console.neon.tech
- Render 服務：https://dashboard.render.com
- 實作計畫：`.claude/NEXT_STEPS.md`、`.claude/PROGRESS.md`
- 系統狀態機：`docs/architecture/state-machine-diagram.md`

---

*更新：2026-01-28*
