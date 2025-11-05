# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

"""
OpenAI wrapper for LLM functionality.

WARNING: This code is under development and may undergo changes in future releases.
Backwards compatibility is not guaranteed at this time.
"""

import os
import json
import re
import logging
import asyncio
from typing import Dict, Any, List, Optional

from openai import AsyncOpenAI
from core.config import CONFIG
import threading
from misc.logger.logging_config_helper import get_configured_logger
from misc.logger.logger import LogLevel

from llm_providers.llm_provider import LLMProvider

logger = get_configured_logger("llm")


class ConfigurationError(RuntimeError):
    """
    Raised when configuration is missing or invalid.
    """
    pass


class OpenAIProvider(LLMProvider):
    """Implementation of LLMProvider for OpenAI API."""

    _client_lock = threading.Lock()
    _client = None

    @classmethod
    def get_api_key(cls) -> str:
        """
        Retrieve the OpenAI API key from environment or raise an error.
        """
        provider_config = CONFIG.llm_endpoints["openai"]
        api_key = provider_config.api_key
        return api_key

    @classmethod
    def get_client(cls) -> AsyncOpenAI:
        """
        Configure and return an asynchronous OpenAI client.
        """
        with cls._client_lock:
            if cls._client is None:
                api_key = cls.get_api_key()
                cls._client = AsyncOpenAI(api_key=api_key)
        return cls._client

    @classmethod
    def _build_messages(cls, prompt: str, schema: Dict[str, Any]) -> List[Dict[str, str]]:
        """
        Construct the system and user message sequence enforcing a JSON schema.
        """
        # Create a more explicit system message with the exact field names
        schema_fields = ", ".join([f'"{k}"' for k in schema.keys()])
        return [
            {
                "role": "system",
                "content": (
                    f"You are an AI that only responds with valid JSON. "
                    f"CRITICAL: Your response MUST contain EXACTLY these fields: {schema_fields}. "
                    f"Do not add, remove, or rename any fields. "
                    f"Schema: {json.dumps(schema)}"
                )
            },
            {"role": "user", "content": prompt}
        ]

    @classmethod
    def clean_response(cls, content: str) -> Dict[str, Any]:
        """
        Strip markdown fences and extract the first JSON object.
        """
        cleaned = re.sub(r"```(?:json)?\s*", "", content).strip()
        match = re.search(r"(\{.*\})", cleaned, re.S)
        if not match:
            logger.error("Failed to parse JSON from content: %r", content)
            return {}
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError as e:
            logger.error("JSON decode error: %s", e)
            return {}

    async def get_completion(
        self,
        prompt: str,
        schema: Dict[str, Any],
        model: Optional[str] = None,
        temperature: float = 0.1,
        max_completion_tokens: int = 2048,
        timeout: float = 60.0,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Send an async chat completion request and return parsed JSON output.
        """
        if model is None:
            provider_config = CONFIG.llm_endpoints["openai"]
            model = provider_config.models.high

        client = self.get_client()
        messages = self._build_messages(prompt, schema)

        try:
            # Use JSON mode to enforce structured output
            response = await asyncio.wait_for(
                client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_completion_tokens=max_completion_tokens,
                    response_format={"type": "json_object"},
                    **kwargs
                ),
                timeout
            )
        except asyncio.TimeoutError:
            logger.error("Completion request timed out after %s seconds", timeout)
            return {}
        except Exception as e:
            logger.error("Error calling OpenAI API: %s", e)
            return {}

        # Try parsing the response multiple ways
        content = getattr(response.choices[0].message, "content", "")
        result = self.clean_response(content)
        if not result:
            # As a last resort, try full content directly
            try:
                result = json.loads(content)
            except Exception:
                logger.error("Failed to parse OpenAI response as JSON: %r", content)
                return {}
        return result


# Create a singleton instance
provider = OpenAIProvider()
