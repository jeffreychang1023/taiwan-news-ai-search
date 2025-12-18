"""
Critic Agent - Quality review and compliance checking for the Actor-Critic system.
"""

from typing import Dict, Any
from reasoning.agents.base import BaseReasoningAgent
from reasoning.schemas import CriticReviewOutput


class CriticAgent(BaseReasoningAgent):
    """
    Critic Agent responsible for reviewing drafts and ensuring quality.

    The Critic evaluates drafts for logical consistency, source compliance,
    and mode-specific requirements (strict/discovery/monitor).
    """

    def __init__(self, handler, timeout: int = 30):
        """
        Initialize Critic Agent.

        Args:
            handler: Request handler with LLM configuration
            timeout: Timeout in seconds for LLM calls
        """
        super().__init__(
            handler=handler,
            agent_name="critic",
            timeout=timeout,
            max_retries=3
        )

    async def review(
        self,
        draft: str,
        query: str,
        mode: str
    ) -> CriticReviewOutput:
        """
        Review draft for quality and compliance.

        Args:
            draft: Draft content to review
            query: Original user query
            mode: Research mode (strict, discovery, monitor)

        Returns:
            CriticReviewOutput with validated schema
        """
        # Build the review prompt from PDF (pages 16-21)
        review_prompt = self._build_review_prompt(
            draft=draft,
            query=query,
            mode=mode
        )

        # Call LLM with validation
        result = await self.call_llm_validated(
            prompt=review_prompt,
            response_schema=CriticReviewOutput,
            level="high"
        )

        return result

    def _build_review_prompt(
        self,
        draft: str,
        query: str,
        mode: str
    ) -> str:
        """
        Build review prompt from PDF System Prompt (pages 16-21).

        Args:
            draft: The draft content to review
            query: Original user query
            mode: Research mode (strict, discovery, monitor)

        Returns:
            Complete review prompt string
        """
        # Build mode-specific compliance rules (Task 1)
        mode_compliance_rules = self._build_mode_compliance_rules(mode)

        # Build Monitor Mode specific section (only if mode == monitor)
        monitor_section = ""
        if mode == "monitor":
            monitor_section = self._build_monitor_mode_section()

        prompt = f"""你是一個無情的 **邏輯審查員 (Logic & Quality Controller)**。

你的唯一任務是審核 Analyst 提交的研究報告草稿。

你**不負責**搜尋新資訊，你負責確保報告在邏輯、事實引用與結構上的嚴謹性。

---

## 當前審查配置

- **Search Mode**: {mode}
- **User Query**: {query}

---

## 任務一：搜尋模式合規性檢查 (Mode Compliance)

首先，檢查報告是否符合當前設定的 `search_mode`：

{mode_compliance_rules}

---

## 任務二：推理類型識別與評估 (Reasoning Evaluation)

請分析 Analyst 在報告中使用的主要推理邏輯，並根據以下標準進行嚴格檢視。

若發現推理薄弱，請在回饋中明確指出是哪種類型的失敗。

### 1. 演繹推理 (Deduction) 檢測

*當 Analyst 試圖通過普遍原則推導具體結論時：*

- **檢查大前提**：所依據的普遍原則（如物理定律、經濟學原理、法律條文）是否正確且適用於此情境？
- **檢查小前提**：關於具體情況的事實描述是否準確？
- **有效性判斷**：結論是否必然從前提中得出？有無「肯定後件」等形式謬誤？

### 2. 歸納推理 (Induction) 檢測

*當 Analyst 試圖通過多個案例總結規律時：*

- **樣本評估**：引用的案例數量是否足夠？（例如：不能僅憑 2 個網友留言就推斷「輿論一面倒」）。
- **代表性檢查**：樣本是否具有代表性？有無「倖存者偏差」？
- **局限性標註**：Analyst 是否誠實說明了歸納結論的局限性？

### 3. 溯因推理 (Abduction) 檢測

*當 Analyst 試圖解釋某個現象的原因時：*

- **最佳解釋推論**：Analyst 提出的解釋是否為最合理的？
- **替代解釋 (Alternative Explanations)**：Analyst 是否考慮了至少 3 種可能的解釋？還是直接跳到了最聳動的結論？
- **合理性評估**：是否存在「相關非因果」的謬誤？

---

## 任務三：品質控制檢查表 (Quality Control Checklist)

請逐項執行以下檢查，若有**任何一項**嚴重不合格，請將狀態設為 **REJECT** 或 **WARN**。

### 📋 A. 事實準確性 (Factual Accuracy)

- [ ] **來源支持**：所有關鍵事實陳述（Fact）是否都附帶了來源引用 (Source ID)？
- [ ] **可信度權重**：是否過度放大了低可信度來源的權重？
- [ ] **引用驗證**：引用的數據/日期與上下文是否一致？

### 🧠 B. 邏輯嚴謹性 (Logical Rigor)

- [ ] **結構有效**：推論鏈條是否完整？有無跳躍式推論？
- [ ] **前提可靠**：推論的起點（前提）是否為堅實的事實？
- [ ] **謬誤檢測**：是否包含滑坡謬誤、稻草人謬誤或訴諸權威？
- [ ] **反例考慮**：是否完全忽略了明顯的反面證據？

### 🧩 C. 完整性 (Completeness)

- [ ] **覆蓋率**：是否回答了用戶的所有子問題？
- [ ] **不確定性**：對於未知或模糊的資訊，是否明確標註了「限制」與「不確定性」？
- [ ] **可操作性**：是否提供了有意義的結論或建議？

### 💎 D. 清晰度 (Clarity)

- [ ] **結構清晰**：段落是否分明？
- [ ] **語言簡潔**：是否使用了過多晦澀的術語堆砌？

{monitor_section}

---

## 輸出格式要求

請**嚴格**按照 CriticReviewOutput schema 輸出，包含以下欄位：

```json
{{
  "status": "PASS | WARN | REJECT",
  "critique": "給 Analyst 的具體批評（至少 50 字）",
  "suggestions": ["具體修改建議 1", "建議 2"],
  "mode_compliance": "符合 | 違反",
  "logical_gaps": ["發現的邏輯漏洞 1", "漏洞 2"],
  "source_issues": ["來源問題 1", "問題 2"]
}}
```

### Status 判定標準

- **PASS**: 完美符合，無需修改。可直接進入 Writer 階段。
- **WARN**: 有小瑕疵，需要加註警語或小幅修改，但不需要重跑 Analyst。
- **REJECT**: 邏輯有嚴重漏洞或違反模式設定，必須退回 Analyst 重寫。

---

## 重要提醒

1. 你的輸出必須是**符合 CriticReviewOutput schema 的 JSON**。
2. 即使報告很好，也要在 `critique` 中給出具體評估，不要留空。
3. `critique` 和 `suggestions` 是給 Analyst 看的，要具體且可執行。
4. 將「來源合規性問題」放入 `source_issues` 列表。
5. 將「邏輯推理漏洞」放入 `logical_gaps` 列表。

**CRITICAL JSON 輸出要求**：
- 輸出必須是完整的、有效的 JSON 格式
- 確保所有大括號 {{}} 和方括號 [] 正確配對
- 確保所有字串值用雙引號包圍且正確閉合
- 不要截斷 JSON - 確保結構完整

**必須包含的欄位**（CriticReviewOutput schema）：
- status: "PASS" 或 "WARN" 或 "REJECT"
- critique: 字串（具體批評，至少 50 字）
- suggestions: 字串陣列（具體修改建議）
- mode_compliance: 字串（符合或違反）
- logical_gaps: 字串陣列（邏輯漏洞列表，可為空陣列）
- source_issues: 字串陣列（來源問題列表，可為空陣列）

---

## 待審查的草稿

{draft}

---

現在，請開始審查。
"""
        return prompt

    def _build_mode_compliance_rules(self, mode: str) -> str:
        """
        Build mode-specific compliance rules for Task 1.

        Args:
            mode: Research mode (strict, discovery, monitor)

        Returns:
            Mode-specific compliance rules as markdown string
        """
        if mode == "strict":
            return """### Strict Mode (嚴謹模式)

- 是否引用了 Tier 3-5 (PTT/Dcard/未經證實社群消息) 作為核心證據？ -> 若有，**REJECT**。
- 結論是否過度依賴單一來源？ -> 若是，**WARN**。"""

        elif mode == "discovery":
            return """### Discovery Mode (探索模式)

- 引用社群消息時，是否缺少「未經證實」、「網路傳聞」等顯著標示？ -> 若無，**WARN**。
- 是否將社群傳聞描述為既定事實？ -> 若是，**REJECT**。"""

        elif mode == "monitor":
            return """### Monitor Mode (監測模式)

- 是否同時呈現了官方 (Tier 1-2) 與民間 (Tier 4-5) 的觀點？ -> 若否，**REJECT**。
- 是否明確指出兩者之間的落差？ -> 若否，**WARN**。
- 是否對落差進行風險評級？ -> 若否，**WARN**。
- *(詳細審查標準見下方 Monitor Mode 專用區塊)*"""

        else:
            # Fallback for unknown mode
            return f"""### {mode.capitalize()} Mode

- 檢查報告是否符合 {mode} 模式的一般要求。"""

    def _build_monitor_mode_section(self) -> str:
        """
        Build Monitor Mode specific section (Task 3 extension).

        Returns:
            Monitor Mode specific compliance checks as markdown string
        """
        return """---

## Monitor Mode 專用審查標準

當 `search_mode == "monitor"` 時，額外執行以下檢查：

### 落差分析檢查 (Gap Analysis)

**步驟 1：分類資訊來源**

- 官方組 (Tier 1-2)：政府公告、企業聲明、主流媒體報導
- 民間組 (Tier 4-5)：社群討論、網紅評論、論壇爆料

**步驟 2：檢查落差維度**

| 比對維度 | 說明 |
|---------|------|
| 時間點 | 預估日期/進度差異 |
| 數據 | 財務/營運數字差異 |
| 態度 | 樂觀/悲觀傾向差異 |
| 歸因 | 事件原因解釋差異 |

**步驟 3：評估風險等級合理性**

- 🔴 高風險：官方與民間完全矛盾 + 多個獨立來源
- 🟡 中風險：存在差異但可能是時間差或詮釋不同
- 🟢 低風險：細節差異，不影響核心判斷

### Monitor Mode 額外檢查項目

- [ ] 是否引用了至少 1 個 Tier 1-2 來源？
- [ ] 是否引用了至少 2 個 Tier 4-5 來源？
- [ ] 是否明確列出了官方與民間的觀點對照？
- [ ] 每個落差是否有風險等級標註？
- [ ] 是否提供了具體的監測建議？"""
