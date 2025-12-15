"""
Clarification Agent - Ambiguity resolution (stub for future implementation).
"""

from typing import Dict, Any
from reasoning.agents.base import BaseReasoningAgent


class ClarificationAgent(BaseReasoningAgent):
    """
    Clarification Agent for handling ambiguous queries (stub).

    This agent will be fully implemented when the frontend
    clarification flow is ready to handle user interactions.
    """

    def __init__(self, handler: Any, timeout: int = 30):
        """
        Initialize Clarification Agent.

        Args:
            handler: Request handler with LLM configuration
            timeout: Timeout in seconds for LLM calls
        """
        super().__init__(
            handler=handler,
            agent_name="clarification",
            timeout=timeout,
            max_retries=3
        )

    async def generate_options(
        self,
        query: str,
        ambiguity_type: str
    ) -> Dict[str, Any]:
        """
        Generate clarification options for ambiguous queries.

        Args:
            query: User's ambiguous query
            ambiguity_type: Type of ambiguity (temporal, factual, scope)

        Returns:
            Dictionary with keys:
                - clarification_options: List of clarification options (empty in stub)
                - ambiguity_type: Type of ambiguity detected
        """
        # STUB - Frontend flow not ready yet
        # TODO: Implement when frontend can handle clarification interactions
        # TODO: Implement with ClarificationAgentPrompt when adding detailed prompts

        return {
            "clarification_options": [],
            "ambiguity_type": ambiguity_type
        }
