"""
Anthropic Claude LLM Provider

Calls the Anthropic Messages API (claude-3-5-haiku by default).
Activated by setting LLM_PROVIDER=claude and ANTHROPIC_API_KEY in .env.

Falls back to mock text on any API error so the planning pipeline
never fails due to LLM unavailability.
"""

import logging

from app.llm.base import BaseLLMProvider
from app.llm.mock_provider import MockLLMProvider
from app.llm import prompt_templates as pt

logger = logging.getLogger(__name__)

_FALLBACK = MockLLMProvider()


class ClaudeProvider(BaseLLMProvider):
    """
    Thin wrapper around the Anthropic Python SDK.

    The ``anthropic`` package is imported lazily so the application starts
    successfully even if the package is not installed.
    """

    def __init__(self, api_key: str, model: str = "claude-3-5-haiku-20241022") -> None:
        self._api_key = api_key
        self._model = model
        self._client = None  # initialised on first use

    def _get_client(self):
        if self._client is None:
            try:
                import anthropic  # type: ignore
                self._client = anthropic.AsyncAnthropic(api_key=self._api_key)
            except ImportError:
                logger.error("anthropic package is not installed.")
                return None
        return self._client

    async def _complete(self, prompt: str, max_tokens: int = 300) -> str | None:
        client = self._get_client()
        if client is None:
            return None
        try:
            response = await client.messages.create(
                model=self._model,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text.strip()
        except Exception as exc:
            logger.warning("Claude request failed: %s — using mock fallback", exc)
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

    async def parse_natural_language_request(self, raw_text: str) -> dict:
        """
        Ask Claude to return a strict JSON object with no extra prose.
        Strips markdown code fences that Claude occasionally adds.
        Falls back to MockLLMProvider on any error.
        """
        import json
        import re

        client = self._get_client()
        if client is None:
            return await _FALLBACK.parse_natural_language_request(raw_text)
        prompt = pt.build_parse_trip_prompt(raw_text)
        try:
            response = await client.messages.create(
                model=self._model,
                max_tokens=350,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = response.content[0].text.strip()
            # Strip markdown fences (```json ... ```) Claude sometimes adds
            raw = re.sub(r"^```[a-z]*\n?", "", raw)
            raw = re.sub(r"\n?```$", "", raw)
            return json.loads(raw)
        except Exception as exc:
            logger.warning("Claude NL parse failed: %s — using mock fallback", exc)
            return await _FALLBACK.parse_natural_language_request(raw_text)

    def is_available(self) -> bool:
        return bool(self._api_key)

    @property
    def provider_name(self) -> str:
        return "claude"
