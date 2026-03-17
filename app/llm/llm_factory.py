"""
LLM Factory

Selects and returns the appropriate LLM provider based on settings.
Falls back to MockLLMProvider when a real provider is chosen but has
no API key configured.
"""

import logging

from app.config.settings import Settings
from app.llm.base import BaseLLMProvider
from app.llm.mock_provider import MockLLMProvider

logger = logging.getLogger(__name__)


def create_llm_provider(settings: Settings) -> BaseLLMProvider:
    """
    Return the LLM provider configured in settings.

    Fallback chain:
      openai  → OpenAIProvider (if key present) else MockLLMProvider
      claude  → ClaudeProvider (if key present) else MockLLMProvider
      mock    → MockLLMProvider (always)
    """
    provider = settings.llm_provider

    if provider == "openai":
        if settings.openai_api_key:
            from app.llm.openai_provider import OpenAIProvider
            logger.info("LLM: using OpenAI (%s)", settings.openai_model)
            return OpenAIProvider(
                api_key=settings.openai_api_key,
                model=settings.openai_model,
            )
        logger.warning("LLM_PROVIDER=openai but OPENAI_API_KEY is not set — falling back to mock")

    elif provider == "claude":
        if settings.anthropic_api_key:
            from app.llm.claude_provider import ClaudeProvider
            logger.info("LLM: using Claude (%s)", settings.claude_model)
            return ClaudeProvider(
                api_key=settings.anthropic_api_key,
                model=settings.claude_model,
            )
        logger.warning("LLM_PROVIDER=claude but ANTHROPIC_API_KEY is not set — falling back to mock")

    logger.info("LLM: using mock provider")
    return MockLLMProvider()
