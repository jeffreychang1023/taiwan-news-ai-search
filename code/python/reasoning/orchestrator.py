"""
Deep Research Orchestrator - Coordinates the Actor-Critic reasoning loop.
"""

from typing import Dict, Any, List, Optional
from misc.logger.logging_config_helper import get_configured_logger
from core.config import CONFIG
from reasoning.agents.analyst import AnalystAgent
from reasoning.agents.critic import CriticAgent
from reasoning.agents.writer import WriterAgent
from reasoning.filters.source_tier import SourceTierFilter, NoValidSourcesError
from reasoning.utils.iteration_logger import IterationLogger


logger = get_configured_logger("reasoning.orchestrator")


class DeepResearchOrchestrator:
    """
    Orchestrator for the Actor-Critic reasoning system.

    Coordinates the iterative loop between Analyst (Actor) and Critic,
    then uses Writer to format the final report.
    """

    def __init__(self, handler: Any):
        """
        Initialize orchestrator with reasoning agents.

        Args:
            handler: Request handler with LLM configuration
        """
        self.handler = handler
        self.logger = get_configured_logger("reasoning.orchestrator")

        # Initialize agents
        analyst_timeout = CONFIG.reasoning_params.get("analyst_timeout", 60)
        critic_timeout = CONFIG.reasoning_params.get("critic_timeout", 30)
        writer_timeout = CONFIG.reasoning_params.get("writer_timeout", 45)

        self.analyst = AnalystAgent(handler, timeout=analyst_timeout)
        self.critic = CriticAgent(handler, timeout=critic_timeout)
        self.writer = WriterAgent(handler, timeout=writer_timeout)

        # Initialize source tier filter
        self.source_filter = SourceTierFilter(CONFIG.reasoning_source_tiers)

    async def run_research(
        self,
        query: str,
        mode: str,
        items: List[Dict[str, Any]],
        temporal_context: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Execute deep research using Actor-Critic loop.

        Args:
            query: User's research question
            mode: Research mode (strict, discovery, monitor)
            items: Retrieved items from search (pre-filtered by temporal range)
            temporal_context: Optional temporal information

        Returns:
            List of NLWeb Item dicts compatible with create_assistant_result().
            Each dict contains: @type, url, name, site, siteUrl, score, description

        Raises:
            NoValidSourcesError: If strict mode filters out all sources
        """
        # Initialize iteration logger
        query_id = getattr(self.handler, 'query_id', f'reasoning_{hash(query)}')
        iteration_logger = IterationLogger(query_id)

        self.logger.info(f"Starting deep research: query='{query}', mode={mode}, items={len(items)}")

        try:
            # Phase 1: Filter and enrich context by source tier
            current_context = self.source_filter.filter_and_enrich(items, mode)
            self.logger.info(f"Filtered context: {len(current_context)} sources (from {len(items)})")

            # Phase 2: Actor-Critic Loop
            max_iterations = CONFIG.reasoning_params.get("max_iterations", 3)
            iteration = 0
            draft = None
            review = None

            while iteration < max_iterations:
                self.logger.info(f"Starting iteration {iteration + 1}/{max_iterations}")

                # Analyst: Research or revise
                if review and review.get("status") == "REJECT":
                    # Revise based on critique
                    self.logger.info("Analyst revising draft based on critique")
                    response = await self.analyst.revise(draft, review, current_context)
                    iteration_logger.log_agent_output(
                        iteration=iteration + 1,
                        agent_name="analyst_revise",
                        input_prompt=f"Draft: {draft[:100]}...\nReview: {review}",
                        output_response=response
                    )
                else:
                    # Initial research
                    self.logger.info("Analyst conducting research")
                    response = await self.analyst.research(
                        query=query,
                        context=current_context,
                        mode=mode,
                        temporal_context=temporal_context
                    )
                    iteration_logger.log_agent_output(
                        iteration=iteration + 1,
                        agent_name="analyst_research",
                        input_prompt=f"Query: {query}\nMode: {mode}",
                        output_response=response
                    )

                # Gap detection (stub for now)
                if response.get("status") == "SEARCH_REQUIRED":
                    self.logger.warning("Analyst requested additional search (not implemented)")
                    # TODO: Implement gap search
                    continue

                draft = response.get("draft", "")

                # Critic: Review draft
                self.logger.info("Critic reviewing draft")
                review = await self.critic.review(draft, query, mode)
                iteration_logger.log_agent_output(
                    iteration=iteration + 1,
                    agent_name="critic",
                    input_prompt=f"Draft: {draft[:100]}...",
                    output_response=review
                )

                # Check convergence
                review_status = review.get("status", "")
                if review_status in ["PASS", "WARN"]:
                    self.logger.info(f"Convergence achieved: {review_status}")
                    break

                iteration += 1

            # Check if we have a valid draft
            if not draft:
                self.logger.error("No draft generated after iterations")
                return self._format_error_result(query, "Failed to generate draft")

            # Phase 3: Writer formats final report (⚠️ pass context parameter)
            self.logger.info("Writer composing final report")
            final_report = await self.writer.compose(draft, review, current_context, mode)
            iteration_logger.log_agent_output(
                iteration=iteration + 1,
                agent_name="writer",
                input_prompt=f"Draft: {draft[:100]}...",
                output_response=final_report
            )

            # Log session summary
            iteration_logger.log_summary(
                total_iterations=iteration + 1,
                final_status=review.get("status", "COMPLETED"),
                mode=mode,
                metadata={
                    "sources_analyzed": len(current_context),
                    "sources_filtered": len(items) - len(current_context)
                }
            )

            # Phase 4: Format as NLWeb result (⚠️ pass context for source extraction)
            result = self._format_result(query, mode, final_report, iteration + 1, current_context)
            self.logger.info(f"Research completed: {iteration + 1} iterations")
            return result

        except NoValidSourcesError as e:
            self.logger.error(f"No valid sources after filtering: {e}")
            return self._format_error_result(
                query,
                f"No valid sources available in {mode} mode. Try using 'discovery' mode for broader source coverage."
            )

        except Exception as e:
            self.logger.error(f"Unexpected error in orchestrator: {e}", exc_info=True)
            return self._format_error_result(query, f"Research error: {str(e)}")

    def _format_result(
        self,
        query: str,
        mode: str,
        final_report: Dict[str, Any],
        iterations: int,
        context: List[Any]
    ) -> List[Dict[str, Any]]:
        """
        Format final report as NLWeb Item.

        Args:
            query: User's query
            mode: Research mode
            final_report: Final report from writer
            iterations: Number of iterations completed
            context: Source items used

        Returns:
            List with single NLWeb Item dict

        ⚠️ CRITICAL: Must match schema expected by create_assistant_result()
        """
        return [{
            "@type": "Item",
            "url": f"https://deep-research.internal/{mode}/{query[:50]}",
            "name": f"深度研究報告：{query}",
            "site": "Deep Research Module",
            "siteUrl": "https://deep-research.internal",
            "score": 95,
            "description": final_report.get("final_report", ""),
            "schema_object": {
                "@type": "ResearchReport",
                "mode": mode,
                "iterations": iterations,
                "sources_used": final_report.get("sources_used", []),
                "confidence": final_report.get("confidence_level", "Medium"),
                "total_sources_analyzed": len(context)
            }
        }]

    def _format_error_result(
        self,
        query: str,
        error_message: str
    ) -> List[Dict[str, Any]]:
        """
        Format error as NLWeb Item.

        Args:
            query: User's query
            error_message: Error description

        Returns:
            List with single NLWeb Item dict containing error message
        """
        return [{
            "@type": "Item",
            "url": "https://deep-research.internal/error",
            "name": f"Research Error: {query}",
            "site": "Deep Research Module",
            "siteUrl": "https://deep-research.internal",
            "score": 0,
            "description": f"## Error\n\n{error_message}",
            "schema_object": {
                "@type": "ErrorReport",
                "error": error_message
            }
        }]
