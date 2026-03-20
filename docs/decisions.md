# NLWeb 決策日誌

> 從 Notion 決策日誌 DB 導出（2026-03-03）+ 持續更新。共 51 筆。
> 欄位：Decision / Category / Modules / Date / Status / Reason / Tradeoff

---

## 產品基礎

### 產品定位：臺灣讀豹 — 繁體中文知識工作者的可信新聞搜尋與分析平台
- **Category**: product | **Modules**: M2-Retrieval, M4-Reasoning, M5-Output | **Date**: 2025-10 | **Status**: active
- **Reason**: 新聞是高品質資料來源，但知識工作者（記者/公關/商業研究/政策研究/學術研究）需要高度信任才敢引用於重要工作。市場缺乏繁體中文特化的可信新聞分析工具。
- **Tradeoff**: 不做通用搜尋、不做英文市場、不追求速度最快（選擇多 agent analyst/critic/writer 架構犧牲速度換取分析品質）

### 市場定位：繁體中文特化，不做多語言
- **Category**: business | **Modules**: M0-Indexing, M2-Retrieval | **Date**: 2025-10 | **Status**: active
- **Reason**: 繁體中文市場缺乏高品質新聞分析工具。特化可以在 embedding、分詞、來源選擇上做到最好。台灣知識工作者是第一批目標用戶。
- **Tradeoff**: 放棄英文和簡體中文市場，專注做好一個語言

### 技術架構：多 Agent 編輯室模式（Analyst/Critic/Writer）
- **Category**: technical | **Modules**: M4-Reasoning | **Date**: 2025-12 | **Status**: active
- **Reason**: 模仿編輯室/研究團隊的工作模式來做資料分析。比單一 LLM 回應更可靠，Critic 機制確保事實查核。目標用戶是知識工作者，品質 > 速度。
- **Tradeoff**: 比單次 LLM call 慢且貴，但品質和可信度顯著提升

### 資料來源策略：只收錄可信來源，不做全網爬取
- **Category**: product | **Modules**: M0-Indexing, crawler | **Date**: 2025-11 | **Status**: active
- **Reason**: 目標用戶需要引用於正式場合（報導、研究報告、政策建議），資料來源的可信度是核心價值。寧可來源少但可信，不做全網聚合。
- **Tradeoff**: 覆蓋面比 Google News 小，但每一筆資料都可信可引用

### 來源選擇：先從主要媒體 + 環境研究來源開始
- **Category**: product | **Modules**: M0-Indexing, crawler | **Date**: 2025-10 | **Status**: active
- **Reason**: 先收錄主要新聞來源（LTN/UDN/CNA/Chinatimes），加上環境研究相關（einfo/ESG BT/MOEA），因為預設使用者之一是環境研究人員。未來持續擴充，無刻意排除。
- **Tradeoff**: 初期覆蓋面有限，但確保每個來源品質穩定後再擴充

---

## M0: Indexing / Crawler

### Crawler: 自建而非用現成服務（Scrapy/Apify）
- **Category**: technical | **Modules**: M0-Indexing, crawler | **Date**: 2025-11 | **Status**: active
- **Reason**: 經過 A/B/C/D testing 比較主流 library/module，自建的成功率最高。台灣新聞網站反爬機制強，現成服務無法有效應對。同時學習其他工具的好方法論融入自建系統。
- **Tradeoff**: 開發維護成本高，但爬取成功率顯著優於現成方案

### Crawler: Subprocess 隔離架構，每個來源獨立 process
- **Category**: technical | **Modules**: crawler | **Date**: 2025-12 | **Status**: active
- **Reason**: 平行爬取提升速度。各來源反爬機制不同（Cloudflare/redirect/rate limit），隔離避免互相影響。單一來源崩潰不影響其他。
- **Tradeoff**: 記憶體用量較高，但速度和穩定性提升

### Chunking: 170字/chunk，句號邊界切分 + overlap
- **Category**: technical | **Modules**: M0-Indexing | **Date**: 2025-12 | **Status**: active
- **Reason**: POC 驗證最佳參數。曾嘗試用句間 cosine similarity 切分，發現中文寫作每句語意向量差異大，不適合。實驗後發現 170 字 + 句號邊界 + overlap 約等於文章一段，效果最好。
- **Tradeoff**: 放棄語意切分（semantic chunking），改用長度優先 + 句號邊界的簡單方案

### Crawler/Indexing 與 Serving 完全分離
- **Category**: technical | **Modules**: M6-Infra, M0-Indexing, crawler | **Date**: 2025-11 | **Status**: active
- **Reason**: 爬蟲 + Indexing 是離線作業（桌機 + GCP VM），Web server 獨立部署。Crawler Registry SQLite 717MB 只在 indexing 端。兩者不共享運算資源，避免爬蟲影響查詢服務品質。
- **Tradeoff**: 分離增加 indexing pipeline 的資料同步複雜度，但確保 serving 穩定性

---

## M1: Input

### Query Decomposition: LLM 拆解複雜查詢為多個子查詢
- **Category**: technical | **Modules**: M1-Input, M2-Retrieval | **Date**: 2025-12 | **Status**: active
- **Reason**: 知識工作者的查詢常是多層次的（如「比較 A 與 B 公司的 Q3 財報」）。用 LLM 將大問題拆解為多個獨立子查詢，確保檢索模組能精準調閱不同面向的資料。
- **Tradeoff**: 增加一次 LLM call 的延遲和成本，但提升複雜查詢的召回率

### Guardrails: 已有能量攻擊 + jailbreak 防禦，待擴充提示注入防禦
- **Category**: technical | **Modules**: M1-Input, M6-Infra | **Date**: 2026-02 | **Status**: pending
- **Reason**: 目前有：(1) LLM Safety Net + Prompt Guardrails（jailbreak）(2) 並行限制 middleware 計畫（DR 1/session + 3/IP，一般查詢 5/session）。待擴充：間接提示注入、RAG 資料庫下毒、MCP 工具毒化等新型攻擊手法（參考陽明交大游家牧 4大類13種攻擊盤點）。
- **Tradeoff**: Guardrails 會增加延遲，但對知識工作者平台來說可信度是核心價值

---

## M2: Retrieval

### Hybrid Search: 從偽 hybrid 遷移至真 hybrid（兩路獨立 retrieval + fusion）
- **Category**: technical | **Modules**: M2-Retrieval, M3-Ranking | **Date**: 2026-02 | **Status**: active
- **Reason**: 現狀是偽 hybrid：vector top-500 後才用 BM25 re-rank 同一批。keyword-heavy 查詢（作者名、法案名、專有名詞）如果不在 vector top-500 就完全搜不到。正確做法是 BM25 和 vector 各自獨立檢索再 fusion。未來用 PostgreSQL tsvector + pgvector 一個 SQL query 解決。
- **Tradeoff**: 需要過渡資料庫架構，但搜尋品質顯著提升

### Web Search: 只在 Reasoning gap resolution 中使用，不在純搜尋中使用
- **Category**: product | **Modules**: M2-Retrieval, M4-Reasoning | **Date**: 2026-01 | **Status**: active
- **Reason**: 純搜尋功能應基於可信來源，不混入外部網路結果。Web search 只在 Reasoning 的 gap resolution 階段使用，用於補充內部資料庫缺少的資訊。
- **Tradeoff**: 搜尋覆蓋面受限於內部資料庫，但確保結果可信度

---

## M3: Ranking

### Ranking: 5-stage pipeline（Vector+BM25 → LLM → XGBoost → MMR）
- **Category**: technical | **Modules**: M3-Ranking | **Date**: 2025-12 | **Status**: active
- **Reason**: Vector+BM25 = hybrid search。LLM ranking 是 NLWeb 框架預設做法，不需額外訓練和建置成本（只需 API call 成本）。XGBoost 在 shadow mode 跟蹤資料，等足夠使用者行為資料後訓練上線。MMR 增加多元性。未來 hybrid search 改為真正雙路 retrieval 後，pipeline 會調整。
- **Tradeoff**: 每次查詢需 LLM API call（成本），但免去訓練和建置自定義排序模型的成本

### MMR: Intent-based 動態 λ 調整多元性
- **Category**: technical | **Modules**: M3-Ranking | **Date**: 2026-01 | **Status**: active
- **Reason**: 知識工作者有兩種多元性需求：(1) 看一件事的許多子議題（主題多元）(2) 同一件事看不同來源報導差異（來源多元）。用 intent 偵測機制調整 MMR 的 λ 參數：EXPLORATORY=0.5（更多元），SPECIFIC=0.8（更相關）。
- **Tradeoff**: 增加複雜度（intent 偵測 + 動態參數），但符合知識工作者實際使用情境

### XGBoost: Shadow mode，等足夠使用者行為資料才訓練上線
- **Category**: technical | **Modules**: M3-Ranking | **Date**: 2026-01 | **Status**: active
- **Reason**: XGBoost 需要使用者行為資料（點擊、停留時間、引用等）作為 training signal。目前用戶量不足。Shadow mode 先記錄 features 和 LLM 排序結果，累積足夠資料後再切換到 production mode。
- **Tradeoff**: 目前排序品質完全依賴 LLM，但避免用不足的資料訓練出差勁模型

---

## M4: Reasoning

### Reasoning: Actor-Critic + 4 Agent 架構（Clarification/Analyst/Critic/Writer）
- **Category**: technical | **Modules**: M4-Reasoning | **Date**: 2025-12 | **Status**: active
- **Reason**: 模仿編輯室/研究團隊工作流程。Analyst 撰寫分析草稿，Critic 審查邏輯漏洞和來源合規，最多 3 輪迭代。Writer 撰寫最終報告。Clarification 處理模糊查詢。每個 agent 有專注角色和專屬 prompt，比一個 LLM 一次搞定品質更高。
- **Tradeoff**: 每次查詢更多 LLM call（成本 + 延遲），但品質和可靠性顯著提升

### Reasoning: Source tier filtering（Strict/Discovery/Monitor 三種模式）
- **Category**: technical | **Modules**: M4-Reasoning | **Date**: 2025-12 | **Status**: active
- **Reason**: 知識工作者根據情境需要不同信任等級。Strict mode: 只用 Tier 1-2 官方/主流來源。Discovery mode: 包含 Tier 3-5 但加警語。Monitor mode: 比較官方 vs 民間落差。Source Knowledge Base 對每個來源做 tier 分類。
- **Tradeoff**: Strict mode 限制可用來源，但確保引用在正式場合可站得住腳

### SEC-6: Agent Isolation context 路由隔離
- **Category**: technical | **Modules**: M4-Reasoning | **Date**: 2026-02 | **Status**: active
- **Reason**: 沒有隔離時每個 agent 看到完整 context，浪費 token 且分散注意力。Phase 1: Gap search 只送新文件給 Analyst（start_id offset），Critic 收到 reference sheet（僅被引用的 source）而非 full context，Analyst re-run 傳 previous_draft 保持分析連續性，Writer draft 有長度監控 + citation 驗證。
- **Tradeoff**: Context routing 邏輯更複雜，但減少 token 浪費並提升 agent 專注度

### Tier 6 API: Stock/Weather/Wikipedia 外部知識增強
- **Category**: technical | **Modules**: M4-Reasoning | **Date**: 2026-01 | **Status**: active
- **Reason**: Gap resolution 可能需要即時或結構化數據（超出新聞文章範圍）。Stock/Weather/Wikipedia API 基本免費。不是核心功能但備著好用。
- **Tradeoff**: 極小 — API 免費，僅增加少量維護成本

### CoV: Chain of Verification 兩階段事實查核機制
- **Category**: technical | **Modules**: M4-Reasoning | **Date**: 2026-01 | **Status**: active
- **Reason**: 整合於 Critic Agent。兩步驟：(1) Claim Extraction — 從草稿提取 7 類可驗證宣稱（數字、日期、人名、機構、事件、統計、引述）(2) Claim Verification — 逐一比對來源，標記 verified/unverified/contradicted/partially_verified。結果影響 Critic 審查決策：矛盾 → REJECT，3+ 未驗證 → WARN。確保分析報告中的事實宣稱都有來源依據，防止幻覺。
- **Tradeoff**: 每次查核額外 2 次 LLM call（提取 + 驗證），但大幅提升事實準確性和可信度

### TypeAgent: instructor 庫 + Pydantic schema 結構化 LLM 輸出
- **Category**: technical | **Modules**: M4-Reasoning, M6-Infra | **Date**: 2026-01 | **Status**: active
- **Reason**: 所有 reasoning agent（Analyst/Critic/Writer）共用 TypeAgent 基礎設施。用 instructor 庫將 LLM 輸出自動驗證為 Pydantic schema，驗證失敗自動 retry（最多 3 次）。GPT-5.1 走 Mode.RESPONSES_TOOLS（Responses API）。失敗時 fallback 到手動 JSON 解析（safe_parse_llm_json）。Singleton pattern 初始化 instructor client。確保所有 agent 輸出型別安全且結構一致。
- **Tradeoff**: 依賴 instructor 庫 + OpenAI 特定 API mode，但消除手動 JSON 解析的脆弱性且提供自動重試

---

## M5: Output

### API: NLWeb 框架自帶 + SSE/WebSocket 混合架構
- **Category**: technical | **Modules**: M5-Output | **Date**: 2025-11 | **Status**: active
- **Reason**: 部分 API 結構繼承自 NLWeb 框架設計。搜尋結果用 SSE 推送（單向、server → client），Chat 對話用 WebSocket（雙向）。大多數通訊是單向推送（搜尋結果、reasoning 進度、分析報告），SSE 較 WebSocket 節省資源。
- **Tradeoff**: 混合架構增加前端複雜度（需同時處理 SSE + WebSocket），但各取所長

### Frontend: 原生 HTML/JS/CSS 分離，無框架
- **Category**: technical | **Modules**: M5-Output | **Date**: 2025-12 | **Status**: active
- **Reason**: 不用 React/Vue 等框架，因為：(1) AI 輔助開發時，原生 HTML/JS/CSS 分離檔案讓 Claude 更容易讀取和編輯（單檔過大會超出 context window）。(2) 專案規模還不需要框架級別的狀態管理。(3) 減少 build pipeline 複雜度。
- **Tradeoff**: 無元件化、無自動 re-render，但簡化部署且適合 AI-assisted development 工作流

### Streaming UX: 即時顯示 reasoning 過程而非等待最終結果
- **Category**: product | **Modules**: M5-Output, M4-Reasoning | **Date**: 2026-01 | **Status**: active
- **Reason**: Deep research 需 30秒~數分鐘。用戶等待時看到分析階段進度（Analyst → Critic → Writer）、中間結果、引用來源，而非空白等待。透明度提升信任感，且讓用戶可提前判斷方向是否正確。
- **Tradeoff**: 前端狀態機更複雜（多階段進度條 + 中間結果更新），但用戶體驗顯著提升

### Rate Limiter: user_id 為主、IP 為輔的雙層併發限制
- **Category**: technical | **Modules**: M5-Output, M6-Infra | **Date**: 2026-02-15（updated 2026-03-19） | **Status**: pending
- **Reason**: 防 DDoS/能量消耗攻擊。B2B 模型下所有使用者已認證，以 **user_id 為主要限制鍵**（比 IP 更精確，不受共享 IP 影響）。**IP 限制只套用在未認證請求**（防爬蟲/DDoS），已認證用戶完全走 user_id/session 級限制。DR 1/session，一般查詢 5/session。In-memory asyncio 方案（單實例部署）+ TTL 5 分鐘清理僵屍記錄。SSE 斷線 TTL 10分鐘自動釋放 slot。
- **Tradeoff**: 依賴 auth middleware 先解析 user_id。同 IP 的已認證用戶互不影響，但未認證請求的 IP 限制（DR 3/IP）可能誤擋共享 IP 的未登入用戶

---

## M6: Infrastructure

### 全文儲存: SQLite + Zstd 壓縮
- **Category**: technical | **Modules**: M6-Infra | **Date**: 2025-11 | **Status**: active
- **Reason**: 輕量、本地優先。200 萬篇文章全文壓縮後約 5-20GB。AI 推論時需讀取文章全文作為 context。無外部依賴。但 Render PaaS 無持久化磁碟，將隨 infra migration 整合到 PostgreSQL。
- **Tradeoff**: SQLite 簡單但無法在無磁碟 PaaS 部署，且與向量 DB 分離增加複雜度

### LLM: 雙模型策略（gpt-4o-mini + gpt-5.1）
- **Category**: technical | **Modules**: M6-Infra, M4-Reasoning | **Date**: 2026-01 | **Status**: active
- **Reason**: 簡單問題（query 分析、意圖偵測、基本排序）用 gpt-4o-mini 控制成本。Reasoning module（Analyst/Critic/Writer 多輪迭代）用 gpt-5.1 確保分析品質。每次查詢 2-5 次 LLM call，混合使用平衡成本與品質。
- **Tradeoff**: 雙模型需管理路由邏輯，但比全用大模型省成本，比全用小模型品質更好

### Analytics: 雙 DB（本地 SQLite / Production PostgreSQL）
- **Category**: technical | **Modules**: M6-Infra | **Date**: 2025-12 | **Status**: active
- **Reason**: 透過 `POSTGRES_CONNECTION_STRING` 環境變數自動偵測切換（fallback: `DATABASE_URL` → `ANALYTICS_DATABASE_URL`）。本地開發用 SQLite（免設定），Production 用 VPS PostgreSQL（與 Auth / Search 共用 `nlweb` database）。查詢日誌、效能監控、使用者行為追蹤。~~將隨 infra migration 整合~~ → 已整合完成。
- **Tradeoff**: 雙 DB 需維護相容性，但本地開發零設定成本

### 資料庫架構：從 3DB（Qdrant+SQLite+Neon PG）整合至 PostgreSQL 一體化
- **Category**: technical | **Modules**: M2-Retrieval, M6-Infra | **Date**: 2026-02 | **Status**: active
- **Reason**: 目前 3 個 DB 架構過於複雜。PostgreSQL + pgvector + tsvector 可以一個 DB 解決向量搜尋 + 全文搜尋 + analytics + 文章全文儲存。簡化部署和維運。
- **Tradeoff**: 放棄 Qdrant 專業向量 DB 的進階功能，換取架構簡潔性

### 部署：從 Render PaaS 遷移至 Hetzner VPS
- **Category**: technical | **Modules**: M6-Infra | **Date**: 2026-02 | **Status**: active
- **Reason**: 月費 €15-22 全包，比目前便宜。一台機器跑 PostgreSQL + Web Server + Embedding，架構簡化。現階段無正式上線產品，是遷移好時機。
- **Tradeoff**: 自管 VPS 需要更多運維工作，但成本和彈性更好

### Embedding 模型：Qwen3-Embedding-4B（開源，繁中 #6）
- **Category**: technical | **Modules**: M2-Retrieval, M6-Infra | **Date**: 2026-02 | **Status**: active
- **Reason**: 97.05% hit rate vs OpenAI 90.21%（繁中 benchmark）。開源免費。RTX 3060 6GB 跑得動（INT8）。取代現有的 OpenAI 3-large（#27）和 bge-m3（#11）。
- **Tradeoff**: 維度較高（2560 vs 1024/1536）占用更多空間，但準確度提升顯著

### Infrastructure Migration: PostgreSQL 一體化 + Hetzner VPS + Qwen3 Embedding
- **Category**: technical | **Modules**: M6-Infra, M2-Retrieval | **Date**: 2026-03 | **Status**: pending
- **Reason**: 大神建議 + 內部研究確認。核心問題：(1) 偽 Hybrid Search（BM25 只是 re-ranker，vector 沒命中的文章永遠找不到）(2) 3 個 DB 過度複雜 (3) PaaS 溢價。解法：PostgreSQL + pgvector + tsvector 一個 SQL query 同時走向量 + 全文 + 結構化過濾。Embedding 改 Qwen3-Embedding-4B（開源，繁中 benchmark #6，本地推論）。部署在 Hetzner CAX41 ARM VPS（32GB RAM, 320GB SSD, €22/月）。三階段：Phase 1 本機驗證 → Phase 2 改程式碼 → Phase 3 上線。
- **Tradeoff**: 需大量改寫程式碼 + 全量 re-index 200 萬篇，但根本解決 hybrid search 問題且大幅簡化架構和降低成本

### CI/CD：GitHub Actions + SSH deploy（非 Docker registry push）
- **Category**: infrastructure | **Modules**: M6-Infra | **Date**: 2026-03-13 | **Status**: active
- **Decision**: Push to `main` 觸發 GitHub Actions，SSH 到 VPS 執行 `git pull` + `docker compose up --build`。不用 Docker registry。
- **Reason**: 單一 VPS 部署，不需要 container registry 的複雜度。`appleboy/ssh-action` 簡單直接。LINE Bot push message 通知 success/failure 讓 CEO 即時知道部署狀態。
- **Tradeoff**: 依賴 VPS 上有 git repo 和 Docker build 能力（build 較慢），但省去 registry 費用和設定。未來多台部署時需改用 registry-based 方案。

### Zoe 派工系統：Skill-based delegation 而非 prompt template
- **Category**: technical | **Modules**: 全模組 | **Date**: 2026-03-04 | **Status**: active
- **Reason**: CEO 指令透過 `/delegate` skill 分析上下文（status/decisions/patterns/lessons），動態發現相關 spec，選擇正確的 skill 執行（systematic-debugging/brainstorming/writing-plans 等），而非手寫 prompt template。確保每次派工都有完整上下文且不遺漏已知陷阱。
- **Tradeoff**: 依賴 skill 生態系統品質，但比手動組裝 prompt 更一致且可學習

### LLM 推論：現階段用外部 API，self-host 時導入 LMCache（KV cache 共享）
- **Category**: technical | **Modules**: M4-Reasoning, M6-Infra | **Date**: 2026-03-04 | **Status**: future
- **Reason**: LMCache（github.com/LMCache/LMCache）是 vLLM/SGLang 的 KV cache 管理層，跨請求共享已計算的 prefix cache，宣稱 RAG + 多輪對話 3-10x 延遲降低。對我們的架構特別有價值：(1) Reasoning 三 agent 共用 system prompt → prefix caching 省 3 倍 prefill (2) RAG 熱門 chunks 跨查詢共享 (3) 多輪對話 history caching (4) Query Decomposition 子查詢共享 context。但現階段全用外部 API（OpenAI/Anthropic/Azure），LMCache 無法介入。觸發條件：日請求量 >5K 或 API 月費 >$500 時評估 self-host ROI。路線：Phase 1 vLLM self-host 輕量 model（ranking/query analysis）→ Phase 2 LMCache 介入 → Phase 3 全面 self-host + multi-tier cache。
- **Tradeoff**: Self-host 需要 GPU 資源（A100/H100）和運維成本，但長期可大幅降低延遲和成本。現階段 API 是正確選擇（開發期成本最低）

### Indexing 本機 GPU，Serving 雲端 PostgreSQL（GPU/DB 分離）
- **Category**: technical | **Modules**: M0-Indexing, M6-Infra | **Date**: 2026-03-04 | **Status**: active
- **Reason**: Embedding 需要 GPU（Qwen3-4B INT8），但搜尋只需要 PostgreSQL（pgvector + pg_bigm）。桌機 RTX 3060 負責 indexing，Hetzner VPS 負責 serving。新文章日常量小（每天幾百篇），桌機幾分鐘 embed 完直接 INSERT 到遠端 DB。資料搬遷用 pg_dump/pg_restore。
- **Tradeoff**: 桌機需常開做 indexing（或改用 VPS CPU embedding，但速度慢很多）。未來量大時考慮 VPS 加 GPU 或用方案 B（CPU embedding on VPS）

### Hybrid Search 合併策略：聯集法（非加權分數）
- **Category**: technical | **Modules**: M2-Retrieval | **Date**: 2026-03-05 | **Status**: active
- **Reason**: Vector 和 Text 兩路搜尋各自取 top-N，取聯集去重後全部交給下游 LLM → XGBoost → MMR 排序。不在 retrieval 階段做加權合併（如 0.7 vec + 0.3 text），因為加權法會壓低純文字命中的結果（例：作者搜尋，正確文章 text=1.0 但 vec=0，加權後只有 0.3，反而排在不相關但語意沾邊的文章後面）。Retrieval 只負責「不漏掉好文章」，排序完全交給已驗證的三層 ranker。
- **Tradeoff**: 候選數量較多（最多 2N 篇），下游 ranker 負擔稍增，但 LLM reasoning 本來就要看每篇文章，多幾十篇影響不大

### Login 系統接手：Surgical Merge + Infra 適配
- **Category**: technical | **Modules**: M6-Infra, Auth | **Date**: 2026-03-05 | **Status**: active
- **Reason**: 外部 dev (RG) 在舊架構上實作了 Email/Password 登入系統。程式碼品質經審計後確認可用，但基於舊 infra（Qdrant + Neon + Render）。採用 surgical merge 策略：只提取 login 相關 delta，主 repo 為 source of truth。同時做 infra 適配：env var 統一至 `DATABASE_URL`、auth_db.py 改用 `AsyncConnectionPool`、rate limit 調緊至 production 值、新增 Alembic migration 統一管理 articles/chunks tables。
- **Tradeoff**: Qdrant 相關修改（user_qdrant_provider、qdrant_storage）暫不動，等 Phase 3 Qdrant 移除時統一重寫。baseHandler user_id 注入、tests 重寫、org_id query filter 列為後續 TODO。

### pgvector Index：IVF 取代 HNSW（記憶體優先）
- **Category**: technical | **Modules**: M2-Retrieval, M6-Infra | **Date**: 2026-03-04 | **Status**: active
- **Reason**: 外部顧問建議。HNSW 需要整個 index 常駐 RAM（6M vectors × 1024D = 16-32GB），IVF 只載入被查詢的 cluster（8-16GB）。IVF recall@10 較低（85-95% vs HNSW 95-99%），但我們有三層補償：(1) hybrid search 的 tsvector 文字搜尋路線補回語意搜尋漏掉的 (2) LLM + XGBoost + MMR reranker 確保最終排序品質 (3) nprobe 參數可調整 recall-latency 平衡。額外好處：IVF 建 index 分鐘級（HNSW 數小時），VPS 可降規至 CCX23（€15/月）。
- **Tradeoff**: 語意搜尋 recall 略降，但 hybrid search + reranker 補回。Phase 1 S4 需驗證不同 nprobe 值的品質

### IVFFlat probes=50（benchmark 驗證）
- **Category**: technical | **Modules**: M2-Retrieval | **Date**: 2026-03-05 | **Status**: active
- **Reason**: Benchmark 118K chunks, lists=1000。probes=50 → R@10=98.7%, R@50=97.1%, avg 29ms。probes=20（原設定）R@10=97.0% 但 R@50 只有 91.2%。probes=100 只多 1% recall 不值得。另發現 DB 中有未知來源的 HNSW index（同大小 ~930MB），已刪除。
- **Tradeoff**: 29ms vs 21ms（probes=20），多 8ms 換 6% R@50 提升

### Query-time Embedding：OpenRouter API（非本地模型）
- **Category**: technical | **Modules**: M2-Retrieval, M6-Infra | **Date**: 2026-03-05 | **Status**: active
- **Reason**: Qwen3-Embedding-4B 在 OpenRouter 有（DeepInfra 託管），$0.02/M tokens。Indexing 仍用桌機 GPU（INT8）。Benchmark 8 query 驗證：加 query prompt template 後 API vs 本地 cosine similarity avg=0.982, min=0.960 → PASS。VPS 不需裝模型，RAM 需求從 32GB 降至 8-16GB。
- **Tradeoff**: 依賴外部 API（但 query-time 量極小，月費 <$1），API 回傳 2560D 需截至 1024D

### Session 切換：Cancel + Retry Button（非背景 Stream）
- **Category**: technical | **Modules**: M5-Output | **Date**: 2026-03-13 | **Status**: active
- **Reason**: 搜尋中切換 session 會中斷 SSE stream，導致搜尋結果遺失（session 空白）。曾嘗試「背景 stream 繼續」方案但失敗（stale reference、跨 session 資料污染、多條 stream 狀態管理過複雜）。最終採用最簡方案：切 session 時直接 cancel stream，在舊 session 標記 `interruptedSearch`，切回時顯示「搜尋被中斷，點此重新搜尋」按鈕。
- **Tradeoff**: 搜尋結果會遺失（需重新搜尋），但狀態管理極簡，不會有瘋狂打 API 或跨 session 污染的問題

### 前端 Session 資料架構：localStorage 為主，Server Session 為輔
- **Category**: technical | **Modules**: M5-Output, Auth | **Date**: 2026-03-13 | **Status**: active
- **Reason**: 搜尋結果（sessionHistory）、對話紀錄（chatHistory）存於 localStorage，server session 只存 metadata。這是因為搜尋結果量大、即時性要求高，server round-trip 不划算。Login 後 server session 用於跨裝置恢復 metadata。
- **Tradeoff**: 換瀏覽器/清 cache 會遺失本地搜尋結果，但 MVP 階段可接受

### B2B Onboarding：Bootstrap Token（非自助註冊）
- **Category**: product | **Modules**: Auth | **Date**: 2026-03-17 | **Status**: active
- **Decision**: B2B 用戶不開放自助註冊。Admin 透過 CLI 產生一次性 bootstrap token，發給目標用戶；用戶在 `/setup?token=xxx` 頁面完成首次帳號設定。Login modal 移除「註冊」tab。
- **Reason**: B2B 服務需要控管誰能進入系統。開放自助註冊會引入未授權用戶，增加管理成本和安全風險。Bootstrap token 一次性設計確保每個 token 只能建立一個帳號，admin 全程掌控用戶引導。
- **Tradeoff**: 用戶無法自行申請，所有帳號建立需 admin 介入。但 B2B 模型本來就需要銷售/onboarding 流程，此設計與業務流程一致。

### Transactional Email：Resend SaaS + Cloudflare Email Routing（非自架 SMTP）
- **Category**: technical | **Modules**: Auth, M6-Infra | **Date**: 2026-03-16 | **Status**: active
- **Reason**: 系統需發送 transactional email（帳號啟用、密碼重設、鎖定通知、邀請信）。`email_service.py` 已整合 Resend SDK，零改動可上線。自架 SMTP（Postfix）到達率差（無 IP reputation，企業信箱會進垃圾郵件），維護成本高。Resend 免費額度 3000 封/月，B2B 初期綽綽有餘。官方收信 email 用 Cloudflare Email Routing 免費轉寄到 Gmail。
- **需要設定**：(1) Resend 帳號 + API key → VPS env var `RESEND_API_KEY` (2) Cloudflare DNS 加 SPF/DKIM/DMARC records（Resend 提供）(3) `RESEND_FROM_EMAIL=noreply@twdubao.com` (4) Cloudflare Email Routing 設 `support@twdubao.com` 轉寄
- **Tradeoff**: 依賴第三方 SaaS（但 transactional email 量極小，免費額度足夠；到達率遠優於自架）

### E2E Gate：程式碼改動在 E2E 測試通過前不算完成
- **Category**: process | **Modules**: All | **Date**: 2026-03-19 | **Status**: active
- **Reason**: 52 個 unit test 全過、smoke 17/17 PASSED，但 agent E2E 發現 3 個 unit test 無法抓到的問題（重複文章、前端 JS crash、日期篩選前端渲染失敗）。Unit test 只驗證模組內部邏輯，E2E 才能驗證端到端行為。
- **Tradeoff**: 增加每次改動的驗證時間（agent E2E 10-20 分鐘 + CEO 人工 E2E），但避免「unit test 全過但 production 壞掉」的風險。Pipeline: Unit Test → Smoke → Agent E2E → fix → write e2etest.md → CEO 人工 E2E → Pass = 完成。

### Skill 策略：優化現有 skills，不新增。用 autoresearch 方法論迭代
- **Category**: process | **Modules**: Claude Code Skills | **Date**: 2026-03-18 | **Status**: active
- **Reason**: Anthropic 官方文章核心觀點是「好 skill 只做好一件事」，不是追求覆蓋率。現有 14 個 skill 已覆蓋日常需求，問題在品質（缺 Gotchas、大型單檔浪費 context、description 不精準）不在數量。優化順序：/learn → /zoe → newest-scan 拆檔 → crawler-monitor → 其餘。後續用 autoresearch 方法論（binary eval + 單變數 mutation）針對性迭代。
- **Tradeoff**: 放棄 nlweb-verify、crawler-runbook 等新 skill 提案（至少目前）。接受現有覆蓋缺口，換取既有 skill 的品質提升。Autoresearch 的具體執行方式待定。

### Guardrail Phase 1：6 項防禦全部實作
- **Category**: technical | **Modules**: M1-Input, M5-Output, M6-Infra | **Date**: 2026-03-20 | **Status**: active（待 CEO E2E）
- **Reason**: 上線前最小可行防禦。P1-1 併發限制（user_id 為主、IP 為輔）+ P1-2 QuerySanitizer（500 字、模板變數剝離）+ P1-3 Prompt 防洩漏 + P1-4 Chunk 隔離標記（隨機 token 邊界）+ P1-5 Spending Cap（$100/月、alert 30/50/80/100%）+ P1-6 Event Logging（guardrail_events table）。
- **Tradeoff**: Phase 1 不攔截（只消毒+記錄），Phase 2 才開始攔截明確惡意查詢。頻率限制等上線數據再設。

---

## 歷史決策（已被取代）

> 保留供理解「為什麼曾經這樣做」的背景。

### ~~Vector DB: Qdrant~~ → 已被 PostgreSQL + pgvector 取代
- **Category**: technical | **Modules**: M6-Infra | **Date**: 2025-11 | **Status**: superseded (2026-03)
- **Reason**: 原：Qdrant 提供語意搜尋核心能力。已由 PostgreSQL + pgvector + pg_bigm hybrid search 取代（`retrieval_providers/postgres_client.py`）。Qdrant 相關檔案（`qdrant.py`、`qdrant_uploader.py`）仍保留供參考但不再用於 production retrieval。
- **Tradeoff**: 放棄 Qdrant 專業向量 DB 進階功能，換取 PostgreSQL 一體化架構

### ~~Embedding: 雙模型 Profile Switching（OpenAI 1536D / bge-m3 1024D）~~ → 已被 Qwen3-4B 取代
- **Category**: technical | **Modules**: M6-Infra, M2-Retrieval | **Date**: 2026-01 | **Status**: superseded (2026-02)
- **Reason**: 原：QDRANT_PROFILE env var 控制 online/offline 模式。已由 Qwen3-Embedding-4B 取代（`embedding_providers/qwen3_embedding.py`）。詳見 Qwen3-4B 決策條目。
- **Tradeoff**: 原 Profile 機制已不再使用
