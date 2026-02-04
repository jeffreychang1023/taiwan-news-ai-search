# 

## 1. 核心資料結構與常數 (Configuration)

### 來源知識庫 (Source Knowledge Base)

用於 Hard Filter 與 Enrichment 階段。

codePython

```
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

## 2. Python 邏輯模組 (Hard Logic)

### A. 時間與意圖解析 (HybridTimeParser)

- **Level 1 (Regex/Lib)**: 使用 dateparser 解析明確日期。
    
- **Level 2 (Keyword)**:
    
    - type="timeline": 關鍵字 ["歷史", "回顧"]
        
    - type="fuzzy": 關鍵字 ["最近", "近期", "最新"] -> 需標記為需要 LLM 介入或擴大搜尋。
        
- **Level 3 (Ambiguity Check)**: 若無法解析，回傳 None，觸發 Clarification Agent。
    

### B. 過濾與增強 (Hard Filter & Enrich)

函數簽章：hard_filter_and_enrich(results: List[Result], mode: str) -> List[Result]

1. **Lookup**: 根據 r.source 查表 SOURCE_KNOWLEDGE_BASE。
    
2. **Filter Logic**:
    
    - IF mode == "strict" AND tier > 2: **DROP (continue)**
        
    - IF mode == "strict" AND tier is Unknown: **DROP**
        
3. **Enrichment**:
    
    - 修改 r.content，在開頭注入標籤："[{tier}級來源 | {type}] {content}"
        
    - 若為 Discovery Mode 且 Tier 3-5，注入警語標籤。
        

### C. 主控流程 (DeepResearchOrchestrator)

採用 **Actor-Critic Loop** 架構。

codePython

```
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

    draft = response.draft

    # 3. Critic Phase
    review = critic_agent.review(draft, query, mode)
    
    if review.status == "PASS":
        break
    if review.status == "WARN":
        break # Accept with warnings

    iteration += 1

# 4. Writer Phase
final_report = writer_agent.compose(draft, review, mode)
```

## 3. Agent System Prompts (Soft Logic)

### A. Analyst Agent

**角色**: 首席分析師 (Lead Analyst)  
**Input**: Query, Context, Search Mode  
**Output**:

1. SEARCH_REQUIRED JSON (若資料不足)
    
2. Markdown Draft (若資料充足)
    

**核心邏輯 (Thinking Process)**:

1. **Search Mode Compliance**:
    
    - Strict: 僅使用 Tier 1-2。忽略 PTT/社群。
        
    - Discovery: 綜合分析，社群來源需標註「未經證實」。
        
    - Monitor: 尋找 Tier 1 (官方) 與 Tier 5 (民間) 的**落差 (Gap)**。
        
2. **Reasoning**: 必須建立推論鏈 (Chain of Reasoning)，嚴禁幻覺。
    

**Revise Prompt (修改模式)**:

- 輸入包含：Original Draft, Critic Critique, Specific Suggestion。
    
- 指令：只針對 Critic 的批評進行修改，不要重寫整篇。
    

### B. Critic Agent

**角色**: 邏輯與品質審查員 (Logic & Quality Controller)  
**Input**: Draft, Query, Mode  
**Output**: JSON Only

codeJSON

```
{
    "status": "PASS | WARN | REJECT",
    "evaluation": {
        "mode_compliance": "符合/違反",
        "reasoning_flaws": ["邏輯漏洞1", "來源不合規"]
    },
    "critique": "給 Analyst 的具體批評",
    "suggestion": "具體修改建議 (可執行)"
}
```

**審查標準**:

- **Strict Mode**: 引用 Tier 3+ 來源 -> **REJECT**。
    
- **Discovery Mode**: 引用社群但未加警語 -> **WARN**。
    
- **Monitor Mode**:
    
    - 未呈現「官方 vs 民間」對比 -> **REJECT**。
        
    - 未評估風險等級 -> **WARN**。
        

### C. Clarification Agent

**角色**: 意圖澄清助手  
**Trigger**: 當 TimeParser 失敗或 Query 過於模糊。  
**Output**: JSON (提供 2-4 個選項讓用戶選，而非開放式問答)。

### D. Writer Agent

**角色**: 報告編輯  
**Task**: 整合 Analyst 草稿與 Critic 意見 (如果是 WARN)，輸出最終 Markdown。  
**Templates**:

- Strict: "查核結果", "事實依據", "結論"。
    
- Discovery: "研究摘要", "官方觀點", "輿情觀察"。
    
- Monitor: "情報摘要", "落差分析表 (Gap Analysis)", "建議行動"。
    

## 4. 特殊邏輯：Monitor Mode Gap Analysis

在 Monitor Mode 下，Critic 必須檢查 Draft 是否包含以下結構：

1. **來源分類**: 官方組 (Tier 1-2) vs 民間組 (Tier 4-5)。
    
2. **落差維度**: 時間點、數據、態度、歸因。
    
3. **風險評級**: 高/中/低。
    

## 5. 錯誤處理 (Error Handling)

**類別**: ResearchError  
**Error Types**:

- NO_VALID_SOURCES: Strict Mode 下過濾後無剩餘資料 -> 建議切換 Discovery Mode。
    
- SEARCH_FAILED: API 錯誤。
    
- LLM_PARSE_ERROR: JSON 解析失敗 (需 Retry)。