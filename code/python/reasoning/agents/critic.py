"""
Critic Agent - Quality review and compliance checking for the Actor-Critic system.
"""

from typing import Dict, Any
from reasoning.agents.base import BaseReasoningAgent


class CriticAgent(BaseReasoningAgent):
    """
    Critic Agent responsible for reviewing drafts and ensuring quality.

    The Critic evaluates drafts for logical consistency, source compliance,
    and mode-specific requirements (strict/discovery/monitor).
    """

    def __init__(self, handler: Any, timeout: int = 30):
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
    ) -> Dict[str, Any]:
        """
        Review draft for quality and compliance.

        Args:
            draft: Draft content to review
            query: Original user query
            mode: Research mode (strict, discovery, monitor)

        Returns:
            Dictionary with keys:
                - status: "PASS", "WARN", or "REJECT"
                - critique: Detailed review of the draft
                - suggestions: List of specific improvement suggestions
                - mode_compliance: "符合" (compliant) or "違反" (violation)
                - logical_gaps: List of identified logical gaps or inconsistencies
        """
        # INFRASTRUCTURE ONLY - Return stub response
        # TODO: Implement with CriticAgentPrompt when adding detailed prompts

        # Stub logic: Pass on first review, reject if draft is too short
        if len(draft) < 50:
            return {
                "status": "REJECT",
                "critique": "[STUB] Draft is too short and lacks sufficient detail.",
                "suggestions": [
                    "Add more context from sources",
                    "Expand analysis section"
                ],
                "mode_compliance": "違反",
                "logical_gaps": [
                    "Missing key evidence from sources"
                ]
            }
        else:
            return {
                "status": "PASS",
                "critique": "[STUB] Draft meets basic quality standards.",
                "suggestions": [
                    "Consider adding more specific examples"
                ],
                "mode_compliance": "符合",
                "logical_gaps": []
            }
