"""
Base class for reasoning agents providing common LLM interaction patterns.
"""

import asyncio
from typing import Dict, Any, Optional
from misc.logger.logging_config_helper import get_configured_logger
from core.llm import ask_llm
from core.prompts import find_prompt, fill_prompt


class BaseReasoningAgent:
    """
    Abstract base class for reasoning agents.

    Provides common LLM interaction pattern with retry logic,
    timeout handling, and error management.
    """

    def __init__(
        self,
        handler: Any,
        agent_name: str,
        timeout: int = 60,
        max_retries: int = 3
    ):
        """
        Initialize base reasoning agent.

        Args:
            handler: The request handler with LLM configuration
            agent_name: Name of the agent (for logging)
            timeout: Timeout in seconds for LLM calls
            max_retries: Maximum number of retry attempts for parse errors
        """
        self.handler = handler
        self.agent_name = agent_name
        self.timeout = timeout
        self.max_retries = max_retries
        self.logger = get_configured_logger(f"reasoning.{agent_name}")

    async def ask(
        self,
        prompt_name: str,
        custom_vars: Optional[Dict[str, Any]] = None,
        level: str = "high"
    ) -> Dict[str, Any]:
        """
        Ask LLM using a named prompt template.

        Args:
            prompt_name: Name of the prompt in prompts.xml (e.g., "AnalystAgentPrompt")
            custom_vars: Dictionary of variables to fill in the prompt
            level: LLM quality level ("high" or "low")

        Returns:
            Parsed JSON response from LLM

        Raises:
            TimeoutError: If LLM call exceeds timeout
            ValueError: If prompt not found or max retries exceeded
        """
        # Find prompt template
        prompt_template = find_prompt(prompt_name, site="reasoning")
        if not prompt_template:
            raise ValueError(f"Prompt '{prompt_name}' not found in prompts.xml")

        # Fill prompt with custom variables
        filled_prompt = fill_prompt(prompt_template, custom_vars or {})

        # Retry loop for parse errors
        for attempt in range(self.max_retries):
            try:
                # Call LLM with timeout
                self.logger.info(f"{self.agent_name} calling LLM (attempt {attempt + 1}/{self.max_retries})")

                response = await asyncio.wait_for(
                    ask_llm(
                        filled_prompt,
                        handler=self.handler,
                        level=level
                    ),
                    timeout=self.timeout
                )

                self.logger.info(f"{self.agent_name} received response")
                return response

            except asyncio.TimeoutError:
                self.logger.error(f"{self.agent_name} LLM call timed out after {self.timeout}s")
                raise TimeoutError(f"LLM call timed out after {self.timeout} seconds")

            except (ValueError, KeyError) as e:
                # Parse error - retry
                self.logger.warning(
                    f"{self.agent_name} parse error (attempt {attempt + 1}/{self.max_retries}): {e}"
                )
                if attempt == self.max_retries - 1:
                    # Last attempt failed
                    self.logger.error(f"{self.agent_name} max retries exceeded")
                    raise ValueError(f"Max retries exceeded for {prompt_name}: {e}")

                # Wait before retry (exponential backoff)
                await asyncio.sleep(2 ** attempt)

            except Exception as e:
                # Unexpected error - don't retry
                self.logger.error(f"{self.agent_name} unexpected error: {e}")
                raise

        # Should not reach here
        raise ValueError(f"Failed to get response for {prompt_name}")
