# M4 Reasoning Module 規格文件

## 概述

M4 Reasoning Module 負責深度研究與推論，採用 Actor-Critic 架構進行多輪迭代，確保回答品質。

### 核心特性

- **Actor-Critic Loop**：Analyst（Actor）+ Critic 迭代改進（最多 3 輪）
- **多 Agent 協作**：Clarification、Analyst、Critic、Writer 四個專門 Agent
- **來源分層過濾**：Strict / Discovery / Monitor 三種模式
- **幻覺防護**：Writer sources ⊆ Analyst sources
- **Free Conversation**：Deep Research 後續 Q&A
- **Phase 2 CoV**：Chain of Verification 事實查核
- **Tier 6 API**：外部知識增強（Stock、Weather、Wikipedia）

### 檔案結構

```
code/python/reasoning/
├── orchestrator.py           # 主控流程
├── agents/
│   ├── base.py              # Agent 基礎類別
│   ├── analyst.py           # 分析 Agent
│   ├── critic.py            # 審查 Agent + CoV
│   ├── clarification.py     # 澄清 Agent
│   └── writer.py            # 撰寫 Agent
├── prompts/
│   ├── analyst.py           # Analyst prompts
│   ├── clarification.py     # Clarification prompts
│   ├── cov.py               # Chain of Verification prompts
│   └── writer.py            # Writer prompts
├── filters/
│   └── source_tier.py       # 來源分層過濾
└── schemas_enhanced.py      # Pydantic schemas
```

---

## 1. 核心資料結構與常數 (Configuration)

### 來源知識庫 (Source Knowledge Base)

用於 Hard Filter 與 Enrichment 階段。

```python
SOURCE_KNOWLEDGE_BASE = {
    # Tier 1: 官方與通訊社 (Strict Mode 核心)
    "中央社": {"tier": 1, "type": "official"},
    "公視": {"tier": 1, "type": "official"},
    "行政院": {"tier": 1, "type": "government"},
    # Tier 2: 主流權威媒體
    "聯合報": {"tier": 2, "type": "news"},
    "經濟日報": {"tier": 2, "type": "news"},
    # Tier 3: 網媒 (Discovery Mode)
    "報導者": {"tier": 3, "type": "digital"},
    # Tier 5: 社群 (Strict Mode 禁止 / Monitor Mode 重點)
    "PTT": {"tier": 5, "type": "social"},
    "Dcard": {"tier": 5, "type": "social"}
}

# 未知來源預設處理
UNKNOWN_SOURCE_CONFIG = {
    "default_tier": 4,
    "strict_mode_action": "exclude",
    "discovery_mode_action": "include_with_warning"
}
```

---

## 2. Python 邏輯模組 (Hard Logic)

### A. 時間與意圖解析 (HybridTimeParser)

- **Level 1 (Regex/Lib)**: 使用 dateparser 解析明確日期。
- **Level 2 (Keyword)**:
    - type="timeline": 關鍵字 ["歷史", "回顧"]
    - type="fuzzy": 關鍵字 ["最近", "近期", "最新"] -> 需標記為需要 LLM 介入或擴大搜尋。
- **Level 3 (Ambiguity Check)**: 若無法解析，回傳 None，觸發 Clarification Agent。

### B. 過濾與增強 (Hard Filter & Enrich)

函數簽章：`hard_filter_and_enrich(results: List[Result], mode: str) -> List[Result]`

1. **Lookup**: 根據 `r.source` 查表 `SOURCE_KNOWLEDGE_BASE`。
2. **Filter Logic**:
    - IF mode == "strict" AND tier > 2: **DROP (continue)**
    - IF mode == "strict" AND tier is Unknown: **DROP**
3. **Enrichment**:
    - 修改 `r.content`，在開頭注入標籤：`"[{tier}級來源 | {type}] {content}"`
    - 若為 Discovery Mode 且 Tier 3-5，注入警語標籤。

### C. 主控流程 (DeepResearchOrchestrator)

採用 **Actor-Critic Loop** 架構。

```python
MAX_ITERATIONS = 3

# Main Loop Logic
current_context = search_results
draft = None

while iteration < MAX_ITERATIONS:
    # 1. Analyst Phase
    if review and review.status == "REJECT":
        response = analyst_agent.revise(draft, review, current_context)
    else:
        response = analyst_agent.research(query, current_context, mode)

    # 2. Output Type Check
    if response.status == "SEARCH_REQUIRED":
        # Gap Detection Triggered
        new_results = search_tool.search(response.new_queries)
        current_context += hard_filter(new_results)
        continue # Skip Critic, let Analyst think again with new data

    # 2.5 Gap Resolution via Tier 6 APIs (新增)
    if response.gap_resolutions:
        for gap in response.gap_resolutions:
            data = tier6_api.resolve(gap)
            current_context += data
        continue

    draft = response.draft

    # 3. Critic Phase (含 CoV)
    review = critic_agent.review(draft, query, mode)

    if review.status == "PASS":
        break
    if review.status == "WARN":
        break # Accept with warnings

    iteration += 1

# 4. Writer Phase
final_report = writer_agent.compose(draft, review, mode)
```

---

## 3. Agent System Prompts (Soft Logic)

### A. Analyst Agent

**角色**: 首席分析師 (Lead Analyst)
**檔案**: `reasoning/agents/analyst.py`
**Input**: Query, Context, Search Mode
**Output**:

1. `SEARCH_REQUIRED` JSON (若資料不足)
2. `GAP_RESOLUTION` JSON (若需要外部 API，見 Tier 6 API)
3. Markdown Draft (若資料充足)

**核心邏輯 (Thinking Process)**:

1. **Search Mode Compliance**:
    - Strict: 僅使用 Tier 1-2。忽略 PTT/社群。
    - Discovery: 綜合分析，社群來源需標註「未經證實」。
    - Monitor: 尋找 Tier 1 (官方) 與 Tier 5 (民間) 的**落差 (Gap)**。
2. **Reasoning**: 必須建立推論鏈 (Chain of Reasoning)，嚴禁幻覺。

**Revise Prompt (修改模式)**:
- 輸入包含：Original Draft, Critic Critique, Specific Suggestion。
- 指令：只針對 Critic 的批評進行修改，不要重寫整篇。

### B. Critic Agent

**角色**: 邏輯與品質審查員 (Logic & Quality Controller)
**檔案**: `reasoning/agents/critic.py`
**Input**: Draft, Query, Mode
**Output**: JSON Only

```json
{
    "status": "PASS | WARN | REJECT",
    "evaluation": {
        "mode_compliance": "符合/違反",
        "reasoning_flaws": ["邏輯漏洞1", "來源不合規"],
        "cov_result": {
            "verified_facts": ["事實1", "事實2"],
            "unverified_claims": ["待查核1"],
            "contradictions": []
        }
    },
    "critique": "給 Analyst 的具體批評",
    "suggestion": "具體修改建議 (可執行)"
}
```

**審查標準**:

- **Strict Mode**: 引用 Tier 3+ 來源 -> **REJECT**。
- **Discovery Mode**: 引用社群但未加警語 -> **WARN**。
- **Monitor Mode**:
    - 未呈現「官方 vs 民間」對比 -> **REJECT**。
    - 未評估風險等級 -> **WARN**。

### C. Clarification Agent

**角色**: 意圖澄清助手
**檔案**: `reasoning/agents/clarification.py`
**Trigger**: 當 TimeParser 失敗或 Query 過於模糊。
**Output**: JSON (提供 2-4 個選項讓用戶選，而非開放式問答)。

```json
{
    "needs_clarification": true,
    "questions": [
        {
            "question": "您想查詢哪個時間範圍的新聞？",
            "options": ["過去一週", "過去一個月", "過去一年", "不限時間"]
        }
    ]
}
```

### D. Writer Agent

**角色**: 報告編輯
**檔案**: `reasoning/agents/writer.py`
**Task**: 整合 Analyst 草稿與 Critic 意見 (如果是 WARN)，輸出最終 Markdown。

**Templates** (定義於 `config/config_reasoning.yaml`):

- **Strict**: "查核結果", "事實依據", "結論"。
- **Discovery**: "研究摘要", "官方觀點", "輿情觀察"。
- **Monitor**: "情報摘要", "落差分析表 (Gap Analysis)", "建議行動"。

**幻覺防護**:
- Writer 只能使用 Analyst 已引用的來源
- 驗證：`writer_sources ⊆ analyst_sources`

---

## 4. Phase 2 CoV（Chain of Verification）

**檔案**: `reasoning/prompts/cov.py`, `reasoning/agents/critic.py`

### 概述

CoV 是整合於 Critic Agent 的事實查核機制，用於驗證 Analyst 輸出的事實準確性。

### 流程

```
Analyst Draft → Critic (含 CoV)
                    ↓
            1. 提取關鍵事實宣稱
            2. 交叉比對來源
            3. 標記驗證狀態
                    ↓
            CoV Result → 影響 Review Status
```

### 驗證狀態

| 狀態 | 說明 | 影響 |
|------|------|------|
| `verified` | 多來源確認 | 無 |
| `unverified` | 僅單一來源 | WARN |
| `contradicted` | 來源矛盾 | REJECT |

### Prompt 結構

```python
COV_PROMPT = """
請對以下草稿中的關鍵事實宣稱進行驗證：

草稿：{draft}

可用來源：{sources}

請：
1. 列出所有關鍵事實宣稱
2. 標註每個宣稱的來源依據
3. 檢查是否有矛盾或未經證實的宣稱
4. 輸出 JSON 格式的驗證結果
"""
```

---

## 5. Tier 6 API 整合（Knowledge Enrichment）

**實作位置**: `reasoning/orchestrator.py` (Gap Resolution 邏輯)

### 概述

當 Analyst 偵測到資料缺口（Gap）時，可透過 Tier 6 API 取得外部知識補充。

### 可用 API

| API ID | 名稱 | 用途 | 檔案 |
|--------|------|------|------|
| `llm_knowledge` | LLM 內建知識 | 一般知識問答 | - |
| `google` | Google Custom Search | Web 搜尋 | `retrieval_providers/google_search_client.py` |
| `yfinance` | Yahoo Finance | 股票資訊 | `retrieval_providers/yfinance_client.py` |
| `twse` | 台灣證交所 | 台股資訊 | `retrieval_providers/twse_client.py` |
| `wikipedia` | Wikipedia | 百科知識 | `retrieval_providers/wikipedia_client.py` |
| `wikidata` | Wikidata | 結構化知識 | `retrieval_providers/wikidata_client.py` |
| `cwb_weather` | 中央氣象局 | 台灣天氣 | `retrieval_providers/cwb_weather_client.py` |
| `openweathermap` | OpenWeatherMap | 全球天氣 | `retrieval_providers/global_weather_client.py` |

### Gap Resolution 流程

```python
# Analyst 回傳 Gap Resolution 請求
{
    "status": "GAP_RESOLUTION_NEEDED",
    "gap_resolutions": [
        {"api": "stock_tw", "query": "2330.TW"},
        {"api": "wikipedia", "query": "台積電"}
    ]
}

# Orchestrator 處理
for gap in gap_resolutions:
    result = tier6_dispatcher.resolve(gap.api, gap.query)
    context.append(format_tier6_result(result))
```

### 結果格式化

```python
def format_tier6_result(api_id: str, data: dict) -> str:
    """格式化 Tier 6 API 結果為 Context 字串"""
    if api_id == "stock_tw":
        return f"[股票資訊] {data['symbol']}: 收盤價 {data['close']}, 漲跌 {data['change']}%"
    elif api_id == "wikipedia":
        return f"[Wikipedia] {data['title']}: {data['summary'][:500]}..."
    # ...
```

---

## 6. Free Conversation Mode

**檔案**: `methods/generate_answer.py`

### 概述

Free Conversation Mode 允許用戶在 Deep Research 完成後進行後續 Q&A，延續研究上下文。

### 觸發條件

```python
if has_previous_deep_research_report(conversation_id):
    mode = "free_conversation"
    context = load_previous_report(conversation_id)
```

### 流程

```
Deep Research 完成 → 用戶後續提問 → Free Conversation
                                        ↓
                          1. 載入之前的研究報告
                          2. 將報告作為 Context 注入
                          3. 使用 LLM 回答後續問題
                                        ↓
                              支援多輪對話
```

### Context 注入

```python
def build_free_conversation_context(report: str, user_question: str) -> str:
    return f"""
以下是之前的研究報告：

{report}

---

用戶後續問題：{user_question}

請根據上述研究報告回答用戶問題。如果報告中沒有相關資訊，請明確告知。
"""
```

### API 端點

```
POST /api/free_conversation
{
    "conversation_id": "uuid",
    "message": "用戶問題",
    "previous_report": "之前的研究報告（可選，若有 conversation_id 會自動載入）"
}
```

---

## 7. 特殊邏輯：Monitor Mode Gap Analysis

在 Monitor Mode 下，Critic 必須檢查 Draft 是否包含以下結構：

1. **來源分類**: 官方組 (Tier 1-2) vs 民間組 (Tier 4-5)。
2. **落差維度**: 時間點、數據、態度、歸因。
3. **風險評級**: 高/中/低。

---

## 8. 錯誤處理 (Error Handling)

**類別**: `ResearchError`

| Error Type | 說明 | 處理 |
|------------|------|------|
| `NO_VALID_SOURCES` | Strict Mode 下過濾後無剩餘資料 | 建議切換 Discovery Mode |
| `SEARCH_FAILED` | 搜尋 API 錯誤 | 重試或降級 |
| `LLM_PARSE_ERROR` | JSON 解析失敗 | 重試（最多 3 次）|
| `TIER6_API_ERROR` | 外部 API 錯誤 | 跳過該 Gap，繼續處理 |
| `MAX_ITERATIONS_REACHED` | 達到最大迭代次數 | 使用當前最佳 Draft |

### 優雅降級

```python
try:
    result = orchestrator.run(query)
except ResearchError as e:
    if e.type == "NO_VALID_SOURCES":
        # 提示用戶切換模式
        return suggest_mode_change("discovery")
    elif e.type == "MAX_ITERATIONS_REACHED":
        # 使用最後的 Draft
        return format_partial_result(e.last_draft)
```

---

## 9. 配置檔案

**檔案**: `config/config_reasoning.yaml`

```yaml
orchestrator:
  max_iterations: 3
  max_total_chars: 20000
  enable_cov: true
  enable_tier6_api: true

agents:
  analyst:
    model: "gpt-4o"
    temperature: 0.3
  critic:
    model: "gpt-4o"
    temperature: 0.1
  writer:
    model: "gpt-4o"
    temperature: 0.5

tier6_api:
  enabled_apis:
    - llm_knowledge
    - web_search
    - stock_tw
    - wikipedia
  timeout_seconds: 10

source_tiers:
  strict_max_tier: 2
  discovery_max_tier: 5
  monitor_official_tiers: [1, 2]
  monitor_social_tiers: [4, 5]
```

---

## 10. 除錯工具

### ConsoleTracer

即時事件視覺化，用於開發除錯。

```python
from reasoning.debug import ConsoleTracer

tracer = ConsoleTracer()
orchestrator = DeepResearchOrchestrator(tracer=tracer)
```

### IterationLogger

JSON 事件流日誌，用於事後分析。

```python
from reasoning.debug import IterationLogger

logger = IterationLogger(log_dir="logs/reasoning")
orchestrator = DeepResearchOrchestrator(logger=logger)
```

---

## 11. Changelog

### 2026-03-19 — RSN-11 Guard Fix + Verification Status SSE

**RSN-11 Guard Fix（P0 Bug）**：
- `orchestrator.py` L604 的空結果 guard 從 `if not self.formatted_context` 改為 `if not self.source_map`
- 原因：`_get_current_time_header()` 永遠回傳非空字串，讓 formatted_context 永不為空，即使 retrieval 回傳 0 結果
- `source_map` 只有真正的 retrieval 結果才會填入，不受 header 影響
- 測試：`tests/unit/test_zero_results_guard.py`（8 tests）

**RSN-4 Verification Status SSE Propagation**：
- Critic agent 的 `verification_status` / `verification_message`（CoV 查核結果）現在傳到前端
- 資料流：`critic.py __dict__` → `orchestrator._format_result` → `api.py final_result SSE` → `news-search.js warning banner`
- 前端在 unverified / partially_verified 時顯示黃色 warning banner
- 測試：`tests/unit/test_verification_status_sse.py`（6 tests）

---

*更新：2026-03-19*
