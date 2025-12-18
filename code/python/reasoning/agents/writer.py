"""
Writer Agent - Final report formatting for the Actor-Critic system.
"""

from typing import Dict, Any, List
from reasoning.agents.base import BaseReasoningAgent
from reasoning.schemas import WriterComposeOutput, CriticReviewOutput


class WriterAgent(BaseReasoningAgent):
    """
    Writer Agent responsible for formatting final reports.

    The Writer takes approved drafts and formats them into polished,
    well-structured reports with proper citations and formatting.
    """

    def __init__(self, handler, timeout: int = 45):
        """
        Initialize Writer Agent.

        Args:
            handler: Request handler with LLM configuration
            timeout: Timeout in seconds for LLM calls
        """
        super().__init__(
            handler=handler,
            agent_name="writer",
            timeout=timeout,
            max_retries=3
        )

    async def compose(
        self,
        analyst_draft: str,
        critic_review: CriticReviewOutput,
        analyst_citations: List[int],
        mode: str,
        user_query: str
    ) -> WriterComposeOutput:
        """
        Compose final report from approved draft.

        Args:
            analyst_draft: Draft content from Analyst
            critic_review: Review from Critic with validated schema
            analyst_citations: Whitelist of citation IDs from Analyst (防幻覺機制)
            mode: Research mode (strict, discovery, monitor)
            user_query: Original user query

        Returns:
            WriterComposeOutput with validated schema
        """
        # Build suggested confidence level based on Critic status
        suggested_confidence = self._map_status_to_confidence(critic_review.status)

        # Build the compose prompt from PDF (pages 26-31)
        compose_prompt = self._build_compose_prompt(
            analyst_draft=analyst_draft,
            critic_review=critic_review,
            analyst_citations=analyst_citations,
            mode=mode,
            user_query=user_query,
            suggested_confidence=suggested_confidence
        )

        # Call LLM with validation
        result = await self.call_llm_validated(
            prompt=compose_prompt,
            response_schema=WriterComposeOutput,
            level="high"
        )

        return result

    def _map_status_to_confidence(self, status: str) -> str:
        """
        Map Critic status to suggested confidence level.

        Args:
            status: Critic review status (PASS, WARN, REJECT)

        Returns:
            Suggested confidence level string
        """
        mapping = {
            "PASS": "High",
            "WARN": "Medium",
            "REJECT": "Low"
        }
        return mapping.get(status, "Medium")

    def _build_compose_prompt(
        self,
        analyst_draft: str,
        critic_review: CriticReviewOutput,
        analyst_citations: List[int],
        mode: str,
        user_query: str,
        suggested_confidence: str
    ) -> str:
        """
        Build compose prompt from PDF System Prompt (pages 26-31).

        Args:
            analyst_draft: Draft content from Analyst
            critic_review: Review from Critic
            analyst_citations: Whitelist of citation IDs
            mode: Research mode
            user_query: Original user query
            suggested_confidence: Suggested confidence level from status mapping

        Returns:
            Complete compose prompt string
        """
        # Format Critic feedback
        critic_feedback = self._format_critic_feedback(critic_review)

        # Get template for mode
        template = self._get_template_for_mode(mode)

        # Handle REJECT status (Graceful Degradation)
        reject_warning = ""
        if critic_review.status == "REJECT":
            reject_warning = """
⚠️ **本報告未通過完整審核，以下內容可能存在瑕疵，請謹慎參考。**

**未解決的問題：**
"""
            if critic_review.logical_gaps:
                reject_warning += "\n- " + "\n- ".join(critic_review.logical_gaps)
            if critic_review.source_issues:
                reject_warning += "\n- " + "\n- ".join(critic_review.source_issues)
            reject_warning += "\n\n---\n\n"

        prompt = f"""你是 **報告編輯 (Writer Agent)**。

你負責將 Analyst 的研究草稿與 Critic 的審查意見整合為最終報告。

---

## 輸入資料

### Analyst 的草稿

{analyst_draft}

### Critic 的審查結果

{critic_feedback}

### 可用引用 ID（白名單）

**重要**：你只能使用以下 Analyst 驗證過的引用 ID，嚴禁無中生有：

{analyst_citations}

---

## 任務流程

### 1. 整合修改

根據 `critic_review` 的內容調整草稿：

**若 status == "PASS"**:
- 直接進行格式化，不需修改內容

**若 status == "WARN"**:
- 根據 `critique` 加入必要的警語或註解
- 在報告末尾加入「資料限制」區塊

**若 status == "REJECT"** (表示已達迭代上限):
- 在報告開頭加入醒目警告（已為你準備好）
- 明確列出未解決的問題

### 2. 格式化輸出

請根據 `search_mode = {mode}` 套用以下模板：

{template}

---

## 輸出要求

請**嚴格**按照 WriterComposeOutput schema 輸出，包含以下欄位：

```json
{{
  "final_report": "完整的 Markdown 報告字串",
  "sources_used": [1, 3, 5],  // 必須是 analyst_citations 的子集
  "confidence_level": "High | Medium | Low",
  "methodology_note": "研究方法說明"
}}
```

### Confidence Level 判定指引

- **建議值**：{suggested_confidence}（根據 Critic 的 status 自動計算）
- **調整原則**：通常情況下請採用建議值，但如果你發現內容證據力極強或極弱，可以自行調整。

### Sources Used 限制

**CRITICAL**：`sources_used` 列表中的每個 ID 都必須在 `analyst_citations` 白名單中。
- ✅ 正確：analyst_citations = [1, 2, 3]，你使用 [1, 3]
- ❌ 錯誤：analyst_citations = [1, 2, 3]，你使用 [1, 5]（5 不在白名單中）

---

## REJECT 狀態處理

{reject_warning if reject_warning else "（當前狀態非 REJECT，無需特殊處理）"}

---

## 重要提醒

1. 你的輸出必須是**符合 WriterComposeOutput schema 的 JSON**。
2. `final_report` 必須是完整的 Markdown 字串。
3. 嚴格遵守引用白名單，不要發明新的 ID。
4. `methodology_note` 應簡要說明研究過程（如「經過 X 輪 Analyst-Critic 迭代」）。

**CRITICAL JSON 輸出要求**：
- 輸出必須是完整的、有效的 JSON 格式
- 確保所有大括號 {{}} 和方括號 [] 正確配對
- 確保所有字串值用雙引號包圍且正確閉合
- 不要截斷 JSON - 確保結構完整
- 如果 final_report 內容過長，優先縮短報告長度，但保持 JSON 結構完整

**必須包含的欄位**（WriterComposeOutput schema）：
- final_report: 字串（完整的 Markdown 報告）
- sources_used: 整數陣列（必須是 analyst_citations 的子集）
- confidence_level: "High" 或 "Medium" 或 "Low"
- methodology_note: 字串（研究方法說明）

---

現在，請開始編輯最終報告。

**User Query**: {user_query}
**Search Mode**: {mode}
"""
        return prompt

    def _format_critic_feedback(self, critic_review: CriticReviewOutput) -> str:
        """
        Format Critic feedback for display in prompt.

        Args:
            critic_review: Critic's validated review

        Returns:
            Formatted feedback string
        """
        feedback = f"""**Status**: {critic_review.status}

**Mode Compliance**: {critic_review.mode_compliance}

**Critique**:
{critic_review.critique}

**Suggestions**:
"""
        if critic_review.suggestions:
            feedback += "\n".join(f"- {s}" for s in critic_review.suggestions)
        else:
            feedback += "（無具體建議）"

        if critic_review.logical_gaps:
            feedback += "\n\n**Logical Gaps**:\n"
            feedback += "\n".join(f"- {g}" for g in critic_review.logical_gaps)

        if critic_review.source_issues:
            feedback += "\n\n**Source Issues**:\n"
            feedback += "\n".join(f"- {i}" for i in critic_review.source_issues)

        return feedback

    def _get_template_for_mode(self, mode: str) -> str:
        """
        Get Markdown template for the specified mode.

        Args:
            mode: Research mode (strict, discovery, monitor)

        Returns:
            Markdown template string
        """
        if mode == "strict":
            return self._get_strict_mode_template()
        elif mode == "discovery":
            return self._get_discovery_mode_template()
        elif mode == "monitor":
            return self._get_monitor_mode_template()
        else:
            # Fallback template
            return """## 研究結果

[結論摘要]

### 主要發現

[主要發現內容]

### 資料限制

[說明目前資訊的局限性]
"""

    def _get_strict_mode_template(self) -> str:
        """
        Get Strict Mode template from PDF P.27.

        Returns:
            Strict Mode Markdown template
        """
        return """## 查核結果

[結論摘要 - 1-2 句話]

### 事實依據

| 事實 | 來源 | 日期 |
|-----|------|-----|
| [事實 1] | [Tier 1/2 來源名稱] | YYYY-MM-DD |
| [事實 2] | ... | ... |

### 結論

[基於上述事實的推論，明確標註確定性程度]

### 資料限制

[說明目前資訊的局限性]
"""

    def _get_discovery_mode_template(self) -> str:
        """
        Get Discovery Mode template from PDF P.28.

        Returns:
            Discovery Mode Markdown template
        """
        return """## 研究摘要

[核心發現 - 2-3 句話]

### 官方/主流觀點

[Tier 1-2 來源的資訊，附來源標註]

### 輿情觀察

> ⚠️ 以下內容來自社群討論，尚未經官方證實

[Tier 3-5 來源的資訊，加註警語]

### 觀點落差

[若有矛盾，明確列出]

### 建議後續關注

[可追蹤的發展方向]
"""

    def _get_monitor_mode_template(self) -> str:
        """
        Get Monitor Mode template from PDF P.29.

        Returns:
            Monitor Mode Markdown template
        """
        return """## 情報摘要

**監測主題**: [用戶查詢]
**報告時間**: [當前日期]

### 官方立場

[Tier 1-2 來源的官方說法]

### 輿情訊號

[Tier 4-5 來源的民間討論重點]

### 🔺 資訊落差警示

| 落差維度 | 官方 | 民間 | 風險等級 |
|---------|-----|------|---------|
| [維度 1] | ... | ... | 🔴高/🟡中/🟢低 |

### 建議行動

1. [具體的公關或決策建議]
2. [需要持續監測的指標]
"""
