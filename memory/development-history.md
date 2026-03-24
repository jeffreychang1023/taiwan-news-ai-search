---
name: 專案開發歷程
description: NLWeb 7 個月的開發演進記錄。了解專案背景或技術演進時讀取。
type: project
---

# 專案開發歷程

> 資料來源：Notion Journal 月份總結 + docs/status.md + CEO 確認。2026-03-09 整理。

---

## Month 1（2025/09/15 ~ 10/10）：從零開始

- **環境建置**：Chocolatey → Python → VS Code → Git → Qdrant Cloud
- **第一個爬蟲**：iThome，爬了 17 篇文章
- **NLWeb 框架跑起來**：修 GPT temperature/timeout、換 GPT-4.1
- **產品規劃**：使用者訪談（Tina、凱晏）、PRD template、功能表、商業模式、MVP 時程
- **學習**：Python 基礎、REST API、System Design、Git、RAG

## Month 2（2025/10/13 ~ 11/07）：第一個可用產品

- **iThome 爬蟲擴大**：4 位作者共 3,100 篇，上傳 Qdrant Cloud（**這是至今唯一的大規模 indexing**）
- **搜尋優化**：BM25 + 向量混合（application-level re-ranking）、中文 N-gram、時效性增強
- **部署上線**：Docker → Render（第一次雲端部署）
- **Analytics 系統設計**：query_logger、SQLite 4 表、Dashboard
- **前端 MVP**：簡易搜尋介面
- **9 週 ML 優化計畫**設計

## Month 3（2025/11/10 ~ 12/05）：ML 基礎設施

- **Logging 系統** Phase 1 & 2：為 ML 訓練收集資料
- **BM25 & MMR** 整合進 ranking pipeline
- **XGBoost** 訓練管道 + shadow mode 建立
- **架構 v2.0 定案**：Source Tier + Reasoning Loop 概念確立
- **文件大清理**：CLAUDE.md 減 37%、CONTEXT.md 減 85%

## Month 4（2025/12/08 ~ 2026/01/02）：Reasoning 系統

- **Deep Research 核心**：
  - Analyst/Critic/Writer 三 agent 骨架
  - Actor-Critic 迭代閉環（最多 3 輪）
  - Gap Detection + Web Search 補充
  - D3.js 知識圖譜視覺化
- **DSQA 論文對齊**：確立「高可靠研究系統」定位
- **SSE 進度顯示**、**Clarification 表單式 UI**
- **BRD/MRD 文件**完成

## Month 5（2026/01/05 ~ 01/30）：功能密集交付

- **User Data 上傳**：4 階段全部完成（解析/chunking/Qdrant 索引/前端 UI）
- **TypeAgent + CoV** 落地：instructor 庫 + Pydantic schema + 7 種驗證
- **Web Search Tool Call** 完整收尾（Google Cache/Timeout + Wikipedia 並行）
- **CTS 信任評分系統**設計（0~100 分）
- **前端大重構**：搜尋框重構、Tab 面板、25 bug 修復
- **效能根因分析**：雙請求 + 無 progressive rendering 是核心瓶頸
- **SQLite code indexer** 工具完成

## Month 6（2026/02/01 ~ 02/28）：Crawler 系統 + UX 打磨

- **Crawler 系統建成**：
  - 7 個 parser（LTN/UDN/CNA/Chinatimes/einfo/ESG BT/MOEA）
  - Subprocess 隔離架構
  - Dashboard 管理介面
  - 三級更新頻率設計
- **Indexing Module 建置**：pipeline.py + chunking + embedding + upload
- **開始爬取**：啟動多個來源的 backfill（但主要是 crawling，不是 indexing 到向量 DB）
- **30+ UX 修復**：UIUX 大規模更新、11 題驗證清單
- **Qdrant Profile 切換**：online（OpenAI 1536D）/ offline（bge-m3 1024D）
- **公司設立流程**啟動
- **Richard 訪談**：新聞業深度回饋

## Month 7（2026/03/01 ~ 03/09，進行中）：Infra Migration + Zoe

- **Zoe Plan Phase 1-3** 完成（決策日誌、/delegate、/update-docs、/zoe、LINE MCP）
- **Infra Migration**：
  - Phase 1 ✅：本地驗證（Qwen3-4B INT8、PostgreSQL Docker、40K 測試資料、品質 PASS）
  - Phase 2 ✅：程式碼改寫（PostgreSQL hybrid search、BM25 移除、pg_bigm）
  - Phase 3 🟡：VPS 部署完成（twdubao.com + HTTPS），但**全量 indexing 未執行**

---

## 關鍵事實（CEO 2026-03-09 確認）

| 項目 | 實際狀況 |
|------|----------|
| Qdrant Cloud 資料量 | 幾千～一兩萬篇（主要是 Month 2 的 iThome 3,100 篇 + 少量測試） |
| Crawler Registry | ~1.9M 筆（只代表「爬到的」，不是「已 indexed 的」） |
| 大規模 indexing | **從未執行過**。Crawling 和 indexing 是分離流程，crawler 跑了但 indexing pipeline 未大規模執行 |
| TSV 原始資料 | 分散於桌機、GCP、筆電三台（筆電大部分已搬桌機） |
| VPS PostgreSQL | ~40K 篇（Phase 1 驗證用測試資料） |
| 上線 blocker | 全量 indexing 未執行 → VPS 沒有足夠資料 → 無法取代 Render |

---

## 技術演進軌跡

```
Embedding:  OpenAI 3-large (#27) → bge-m3 (#11, 本地) → Qwen3-4B (#6, 本地 INT8)
搜尋架構:   純 Vector → Vector + App-level BM25 → PostgreSQL hybrid (pgvector + pg_bigm)
資料庫:     Qdrant Cloud + SQLite + Neon PG → PostgreSQL 一體化（VPS）
Ranking:    LLM only → LLM + BM25 + XGBoost(shadow) + MMR → LLM + XGBoost(shadow) + MMR
部署:       本地 → Render + Qdrant Cloud → Hetzner VPS + Cloudflare
Reasoning:  無 → Analyst/Critic/Writer + Gap Detection + CoV + Web Search
```
