"""
OpenAI LLM Provider

Calls the OpenAI Chat Completions API (gpt-4o-mini by default).
Activated by setting LLM_PROVIDER=openai and OPENAI_API_KEY in .env.

Falls back to mock text on any API error so the planning pipeline
never fails due to LLM unavailability.
"""

import logging

from app.llm.base import BaseLLMProvider
from app.llm.mock_provider import MockLLMProvider
from app.llm import prompt_templates as pt

logger = logging.getLogger(__name__)

_FALLBACK = MockLLMProvider()


class OpenAIProvider(BaseLLMProvider):
    """
    Thin wrapper around the OpenAI Python SDK.

    The ``openai`` package is imported lazily so the application starts
    successfully even if the package is not installed.
    """

    def __init__(self, api_key: str, model: str = "gpt-4o-mini") -> None:
        self._api_key = api_key
        self._model = model
        self._client = None  # initialised on first use

    def _get_client(self):
        if self._client is None:
            try:
                from openai import AsyncOpenAI  # type: ignore
                self._client = AsyncOpenAI(api_key=self._api_key)
            except ImportError:
                logger.error("openai package is not installed.")
                return None
        return self._client

    async def _complete(self, prompt: str, max_tokens: int = 300) -> str | None:
        client = self._get_client()
        if client is None:
            return None
        try:
            response = await client.chat.completions.create(
                model=self._model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=0.7,
            )
            return response.choices[0].message.content.strip()
        except Exception as exc:
            logger.warning("OpenAI request failed: %s — using mock fallback", exc)
            return None

    async def generate_overview(self, destination, duration_days, persona_summary,
                                 day_themes, weather_summary) -> str:
        prompt = pt.build_overview_prompt(
            destination, duration_days, persona_summary, day_themes, weather_summary
        )
        result = await self._complete(prompt, max_tokens=200)
        if result:
            return result
        return await _FALLBACK.generate_overview(
            destination, duration_days, persona_summary, day_themes, weather_summary
        )

    async def generate_day_narrative(self, day_number, theme, poi_names,
                                      weather_condition, travel_advisory) -> str:
        prompt = pt.build_day_narrative_prompt(
            day_number, theme, poi_names, weather_condition, travel_advisory
        )
        result = await self._complete(prompt, max_tokens=150)
        if result:
            return result
        return await _FALLBACK.generate_day_narrative(
            day_number, theme, poi_names, weather_condition, travel_advisory
        )

    async def generate_poi_reason(self, poi_name, category, top_interest) -> str:
        prompt = pt.build_poi_reason_prompt(poi_name, category, top_interest)
        result = await self._complete(prompt, max_tokens=60)
        if result:
            return result
        return await _FALLBACK.generate_poi_reason(poi_name, category, top_interest)

    async def infer_soft_preferences(self, free_text: str) -> list[str]:
        prompt = pt.build_soft_preference_prompt(free_text)
        result = await self._complete(prompt, max_tokens=80)
        if result and result.strip():
            return [tag.strip() for tag in result.split(",") if tag.strip()]
        return await _FALLBACK.infer_soft_preferences(free_text)

    def is_available(self) -> bool:
        return bool(self._api_key)

    @property
    def provider_name(self) -> str:
        return "openai"
