"""
Writer Agent - Final report formatting for the Actor-Critic system.
"""

from typing import Dict, Any, List
from reasoning.agents.base import BaseReasoningAgent
from reasoning.schemas import WriterComposeOutput, CriticReviewOutput
from reasoning.prompts.writer import WriterPromptBuilder


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
        self.prompt_builder = WriterPromptBuilder()

    async def plan(
        self,
        analyst_draft: str,
        critic_review: CriticReviewOutput,
        user_query: str,
        target_length: int = 2000
    ):
        """
        Generate outline plan for long-form report (Phase 3).

        Args:
            analyst_draft: The Analyst's draft
            critic_review: Critic's feedback
            user_query: Original user query
            target_length: Target word count (default 2000)

        Returns:
            WriterPlanOutput with outline and key arguments
        """
        from reasoning.schemas_enhanced import WriterPlanOutput

        # RSN-8: Use WriterPromptBuilder instead of inline prompt duplication
        prompt = self.prompt_builder.build_plan_prompt(
            analyst_draft=analyst_draft,
            critic_review=critic_review,
            user_query=user_query,
            target_length=target_length
        )

        result, retry_count, fallback_used = await self.call_llm_validated(
            prompt=prompt,
            response_schema=WriterPlanOutput,
            level="high"  # Use high quality for planning
        )

        # Log TypeAgent metrics for analytics
        self.logger.debug(f"TypeAgent metrics (plan): retries={retry_count}, fallback={fallback_used}")

        self.logger.info(f"Plan generated: {len(result.key_arguments)} key arguments, est. {result.estimated_length} words")
        return result

    async def compose(
        self,
        analyst_draft: str,
        critic_review: CriticReviewOutput,
        analyst_citations: List[int],
        mode: str,
        user_query: str,
        plan = None  # Optional WriterPlanOutput from plan() method (Phase 3)
    ) -> WriterComposeOutput:
        """
        Compose final report, optionally using pre-generated plan.

        Args:
            analyst_draft: Draft content from Analyst
            critic_review: Review from Critic with validated schema
            analyst_citations: Whitelist of citation IDs from Analyst (防幻覺機制)
            mode: Research mode (strict, discovery, monitor)
            user_query: Original user query
            plan: Optional WriterPlanOutput from plan() method (Phase 3)

        Returns:
            WriterComposeOutput with validated schema
        """
        # Build suggested confidence level based on Critic status
        suggested_confidence = self.prompt_builder.map_status_to_confidence(critic_review.status)

        if plan:
            # RSN-8: Use WriterPromptBuilder instead of inline prompt duplication
            compose_prompt = self.prompt_builder.build_compose_prompt_with_plan(
                analyst_draft=analyst_draft,
                analyst_citations=analyst_citations,
                plan=plan
            )
        else:
            # Standard mode (existing prompt)
            compose_prompt = self.prompt_builder.build_compose_prompt(
                analyst_draft=analyst_draft,
                critic_review=critic_review,
                analyst_citations=analyst_citations,
                mode=mode,
                user_query=user_query,
                suggested_confidence=suggested_confidence
            )

        # Call LLM with validation
        result, retry_count, fallback_used = await self.call_llm_validated(
            prompt=compose_prompt,
            response_schema=WriterComposeOutput,
            level="high"
        )

        # Log TypeAgent metrics for analytics
        self.logger.debug(f"TypeAgent metrics (compose): retries={retry_count}, fallback={fallback_used}")

        return result

