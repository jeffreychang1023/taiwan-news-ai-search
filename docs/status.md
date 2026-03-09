# 專案狀態

> 合併自 CONTEXT.md + NEXT_STEPS.md。單一狀態檔案。

**最後更新**：2026-03-05

---

## 目前重點

**Login 系統合併完成 + Infra 適配進行中**

### 最近完成

- **UX Issues #1-11 修復**（19 commits, merged as 77f974a）
  - QueryUnderstanding 統一模組（取代 3 個 pre-checks）
  - Qdrant domain filter → LLM-based boost scoring
  - Deep research session history + UI polish
  - Author search strict filter + print noise cleanup
  - 年份推論規則（防止未來日期誤判）
  - zh-TW 錯誤訊息 + cp950 UnicodeEncodeError 修復
  - Feedback buttons event delegation
  - datePublished 注入 Analyst formatted_context
- **Login 系統合併 + Infra 適配**（branch: `feat/login-system-merge`）
  - 從 RG repo surgical merge：13 新檔、12 修改檔、2 刪除檔
  - Infra 適配完成：env var 統一（`DATABASE_URL`）、AsyncConnectionPool、Rate limit 調緊、Alembic infra migration
  - 詳見 `docs/specs/login-spec.md`
- **Zoe Plan Phase 2-3 完成**
  - `/delegate` + `/update-docs` + `/zoe` skills
  - LINE MCP 通知 + Task 追蹤
- **SEC-6 Phase 1：Agent Isolation**（先前完成）
- **全專案 Code Review 修復**（21 檔案、47 項）

---

## 進行中

**目前三台機器都沒有 crawler 在跑。**（2026-03-05 確認）

### 已停止的 Crawler

1. **GCP — Chinatimes full_scan（新版 multi-category）** → ✅ 已完成
   - Task #29 failed（success=43,632）→ Task #30 completed（success=117,091）
   - 合計 task 26-30：~186,744 篇 success
   - **待辦**：GCP 資料收回（`merge_registry.py` 合併至桌機）、確認 hit rate 提升

2. **桌機 — einfo** → ❌ 已停止
   - 最後 task #18 failed（success=0, failed=626）
   - 需要調查失敗原因後決定是否重啟

3. **筆電** → ❓ 無法連線（SSH timeout，IP 可能已變）

---

## Backfill 狀態

| Source | 狀態 | 數量 |
|--------|------|------|
| LTN | ✅ 完成 | 693,273 篇（watermark 5,342,046） |
| CNA | ✅ 完成 | 242,011 篇（watermark 2026-02-12） |
| UDN | ✅ 完成 | 桌機 2025-08+ / GCP 2024-01→2025-07 / 筆電 2024-10→2025-02（全部合併） |
| ESG BT | ✅ 完成 | backfill 完成 |
| MOEA | ✅ 完成 | 5,805 篇（已合併至桌機） |
| Chinatimes | ✅ 完成 | GCP full_scan 完成（task 26-30 合計 ~186,744 篇），待合併至桌機 |
| einfo | ❌ 停止 | 桌機 task #18 failed（0 success），需調查 |

**Registry 總計**：1,910,520 筆

---

## 待處理

### Login 系統後續
- SEC-1/9/18/19：JWT 認證串接（Login 系統已合併，需完成 baseHandler user_id 注入）
- Tests 重寫（auth_service / auth_middleware / session_service）
- org_id 查詢 filter（user_data_manager list/delete 缺 org_id）
- query_logger 加 org_id
- Qdrant 移除後重寫 user_qdrant_provider → PostgreSQL

### Zoe Plan 後續
- Phase 4：自動化排程（待定）

### Code Review 後續
- RNK-7：BM25 corpus stats 重建（title weighting 改變）
- RSN-4 前端：讀取 verification_status 顯示未驗證提示

### SEC-6 後續
- Phase 2：Extracted Knowledge（LLM 結構化輸出，Phase 1 驗證有效後）
  - `ExtractedFact` schema（fact + source_ids + relevance）
  - Orchestrator 累積邏輯（dedup by fact+source_ids，cap 50）
  - Analyst prompt 注入 accumulated_knowledge

### Crawler 後續
1. **GCP Chinatimes 資料收回**：`merge_registry.py` 將 GCP 資料合併至桌機（full_scan 已完成）
2. **einfo 調查**：桌機 task #18 全部 failed，需查 log 確認原因（proxy？parser？）
3. **筆電連線**：確認筆電 IP 並恢復 SSH 連線
4. 效能優化：Reasoning 延遲分析、token 減少

---

## 短期任務

### 0. SEC-6 Phase 1 驗證
- 啟用 `agent_isolation: true`
- 觀察 gap search 查詢的 SEC-6 log（context 不增長、reference sheet reduction %）
- 比對 flag on/off 的引用覆蓋率

### 1. 效能優化
- 降低 Reasoning 延遲（分析 Analyst/Critic/Writer 瓶頸）
- 優化 prompt token 使用量
- 考慮並行 agent 執行
- 成本分析（各 agent token 使用量）

### 2. 引用品質改善
- 幻覺防護邊界案例測試
- 引用連結驗證
- 來源分層規則調整

### 3. UX 改善
- 澄清流程 UI
- 長查詢進度指示器
- 使用者回饋迴圈

---

## 中期任務（1-2 月）

1. **A/B 測試基礎設施** — reasoning vs 標準搜尋 feature flag、查詢路由（10%→50%→100%）、比較指標儀表板
2. **模型重訓練管道** — XGBoost ranker 自動重訓練、使用者互動資料納入
3. **進階 Reasoning 功能** — 交叉參考偵測、時間分析、比較研究

---

## 長期願景（3-6 月）

- 擴展來源覆蓋（20+ sources）
- 多語言支援
- 使用者個人化
- 線上學習

---

## 參考資源

- Analytics 儀表板：https://taiwan-news-ai-search.onrender.com/analytics
- Neon 資料庫：https://console.neon.tech
- Render 服務：https://dashboard.render.com
- 系統狀態機：`docs/reference/architecture/state-machine-diagram.md`
- 歷史進度：`docs/reference/progress-history.md`
- 已完成工作：`docs/archive/completed-work.md`
