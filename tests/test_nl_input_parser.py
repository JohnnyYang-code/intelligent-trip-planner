"""
Unit tests for app/services/nl_input_parser.py — Sprint 5.6

All tests use injected AsyncMock LLM dicts (no API keys required).
A separate section exercises the real MockLLMProvider regex engine.

Test classes:
  TestHappyPath            — well-formed parsed dicts produce correct TripRequest
  TestDefaults             — missing fields are filled with safe defaults
  TestErrorHandling        — invalid / missing data raises HTTPException 422
  TestMockProviderIntegration — end-to-end with MockLLMProvider regex engine
"""

import pytest
from unittest.mock import AsyncMock

from fastapi import HTTPException

from app.llm.mock_provider import MockLLMProvider
from app.schemas.common import BudgetLevel, POICategory, TravelPace
from app.schemas.trip_request import TripRequest
from app.services.nl_input_parser import NLInputParser


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parser_with_fixed_dict(parsed_dict: dict) -> NLInputParser:
    """Return a parser whose LLM always returns a fixed dict."""
    mock_llm = AsyncMock()
    mock_llm.parse_natural_language_request = AsyncMock(return_value=parsed_dict)
    return NLInputParser(llm=mock_llm)


def _full_dict(**overrides) -> dict:
    """Base dict with all keys present (simulates a real LLM response)."""
    base = {
        "destination": "Brisbane",
        "duration_days": 3,
        "start_date": None,
        "end_date": None,
        "budget_level": None,
        "travel_pace": None,
        "preferred_categories": None,
        "free_text_preferences": None,
    }
    base.update(overrides)
    return base


@pytest.fixture
def mock_parser() -> NLInputParser:
    """Parser backed by the real MockLLMProvider (regex/keyword engine)."""
    return NLInputParser(llm=MockLLMProvider())


# ── Happy path ────────────────────────────────────────────────────────────────

class TestHappyPath:
    @pytest.mark.asyncio
    async def test_returns_trip_request_type(self):
        p = _parser_with_fixed_dict(_full_dict())
        result = await p.parse("Three days in Brisbane.")
        assert isinstance(result, TripRequest)

    @pytest.mark.asyncio
    async def test_destination_lowercased(self):
        p = _parser_with_fixed_dict(_full_dict(destination="Brisbane"))
        result = await p.parse("Three days in Brisbane.")
        assert result.destination == "brisbane"

    @pytest.mark.asyncio
    async def test_explicit_duration_used(self):
        p = _parser_with_fixed_dict(_full_dict(duration_days=5))
        result = await p.parse("Five days in Brisbane.")
        assert result.duration_days == 5

    @pytest.mark.asyncio
    async def test_duration_computed_from_dates(self):
        p = _parser_with_fixed_dict(_full_dict(
            duration_days=None,
            start_date="2026-03-20",
            end_date="2026-03-23",
        ))
        result = await p.parse("Trip from March 20 to 23 in Brisbane.")
        assert result.duration_days == 3

    @pytest.mark.asyncio
    async def test_budget_level_passed_through(self):
        p = _parser_with_fixed_dict(_full_dict(budget_level="luxury"))
        result = await p.parse("Luxury trip to Brisbane.")
        assert result.budget_level == BudgetLevel.luxury

    @pytest.mark.asyncio
    async def test_travel_pace_passed_through(self):
        p = _parser_with_fixed_dict(_full_dict(travel_pace="relaxed"))
        result = await p.parse("Relaxed trip to Brisbane.")
        assert result.travel_pace == TravelPace.relaxed

    @pytest.mark.asyncio
    async def test_preferred_categories_passed_through(self):
        p = _parser_with_fixed_dict(_full_dict(
            preferred_categories=["food_dining", "art_museum"]
        ))
        result = await p.parse("Brisbane focusing on food and art.")
        assert POICategory.food_dining in result.preferred_categories
        assert POICategory.art_museum in result.preferred_categories

    @pytest.mark.asyncio
    async def test_free_text_preferences_passed_through(self):
        p = _parser_with_fixed_dict(_full_dict(
            free_text_preferences="I hate crowded places."
        ))
        result = await p.parse("Three days in Brisbane. I hate crowded places.")
        assert result.free_text_preferences == "I hate crowded places."


# ── Defaults ─────────────────────────────────────────────────────────────────

class TestDefaults:
    @pytest.mark.asyncio
    async def test_missing_duration_defaults_to_3(self):
        p = _parser_with_fixed_dict(_full_dict(duration_days=None))
        result = await p.parse("Trip to Brisbane.")
        assert result.duration_days == 3

    @pytest.mark.asyncio
    async def test_missing_budget_defaults_to_mid_range(self):
        p = _parser_with_fixed_dict(_full_dict(budget_level=None))
        result = await p.parse("Trip to Brisbane.")
        assert result.budget_level == BudgetLevel.mid_range

    @pytest.mark.asyncio
    async def test_missing_pace_defaults_to_moderate(self):
        p = _parser_with_fixed_dict(_full_dict(travel_pace=None))
        result = await p.parse("Trip to Brisbane.")
        assert result.travel_pace == TravelPace.moderate

    @pytest.mark.asyncio
    async def test_missing_categories_is_none(self):
        p = _parser_with_fixed_dict(_full_dict(preferred_categories=None))
        result = await p.parse("Trip to Brisbane.")
        assert result.preferred_categories is None

    @pytest.mark.asyncio
    async def test_missing_free_text_is_none(self):
        p = _parser_with_fixed_dict(_full_dict(free_text_preferences=None))
        result = await p.parse("Trip to Brisbane.")
        assert result.free_text_preferences is None

    @pytest.mark.asyncio
    async def test_constraints_all_default_false(self):
        p = _parser_with_fixed_dict(_full_dict())
        result = await p.parse("Trip to Brisbane.")
        assert result.constraints.with_children is False
        assert result.constraints.with_elderly is False
        assert result.constraints.accessibility_required is False
        assert result.constraints.avoid_categories == []

    @pytest.mark.asyncio
    async def test_interests_always_set(self):
        """interests must always be a populated InterestWeights, never None."""
        p = _parser_with_fixed_dict(_full_dict())
        result = await p.parse("Trip to Brisbane.")
        assert result.interests is not None
        assert result.interests.food_dining >= 0.0

    @pytest.mark.asyncio
    async def test_duration_from_dates_when_duration_missing(self):
        p = _parser_with_fixed_dict(_full_dict(
            duration_days=None,
            start_date="2026-04-01",
            end_date="2026-04-08",
        ))
        result = await p.parse("Sydney April 1 to 8.")
        assert result.duration_days == 7

    @pytest.mark.asyncio
    async def test_duration_out_of_range_falls_back_to_3(self):
        p = _parser_with_fixed_dict(_full_dict(
            duration_days=None,
            start_date="2026-01-01",
            end_date="2026-06-30",   # 180 days — exceeds 14
        ))
        result = await p.parse("Long trip to Brisbane.")
        assert result.duration_days == 3

    @pytest.mark.asyncio
    async def test_explicit_duration_takes_priority_over_dates(self):
        # LLM returned both; explicit duration_days wins
        p = _parser_with_fixed_dict(_full_dict(
            duration_days=5,
            start_date="2026-03-20",
            end_date="2026-03-23",   # would give 3, but explicit wins
        ))
        result = await p.parse("Five days in Brisbane from March 20.")
        assert result.duration_days == 5


# ── Error handling ────────────────────────────────────────────────────────────

class TestErrorHandling:
    @pytest.mark.asyncio
    async def test_missing_destination_raises_422(self):
        p = _parser_with_fixed_dict(_full_dict(destination=None))
        with pytest.raises(HTTPException) as exc_info:
            await p.parse("Somewhere for three days.")
        assert exc_info.value.status_code == 422
        assert "destination" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_empty_destination_string_raises_422(self):
        p = _parser_with_fixed_dict(_full_dict(destination=""))
        with pytest.raises(HTTPException) as exc_info:
            await p.parse("Somewhere for three days.")
        assert exc_info.value.status_code == 422

    @pytest.mark.asyncio
    async def test_invalid_budget_enum_raises_422(self):
        p = _parser_with_fixed_dict(_full_dict(budget_level="super_cheap"))
        with pytest.raises(HTTPException) as exc_info:
            await p.parse("Cheap trip to Brisbane.")
        assert exc_info.value.status_code == 422

    @pytest.mark.asyncio
    async def test_invalid_travel_pace_raises_422(self):
        p = _parser_with_fixed_dict(_full_dict(travel_pace="turbo"))
        with pytest.raises(HTTPException) as exc_info:
            await p.parse("Turbo trip to Brisbane.")
        assert exc_info.value.status_code == 422

    @pytest.mark.asyncio
    async def test_invalid_category_raises_422(self):
        p = _parser_with_fixed_dict(_full_dict(preferred_categories=["skydiving"]))
        with pytest.raises(HTTPException) as exc_info:
            await p.parse("Trip with skydiving.")
        assert exc_info.value.status_code == 422

    @pytest.mark.asyncio
    async def test_llm_exception_raises_422(self):
        mock_llm = AsyncMock()
        mock_llm.parse_natural_language_request = AsyncMock(
            side_effect=RuntimeError("LLM crashed")
        )
        p = NLInputParser(llm=mock_llm)
        with pytest.raises(HTTPException) as exc_info:
            await p.parse("Trip to Brisbane.")
        assert exc_info.value.status_code == 422

    @pytest.mark.asyncio
    async def test_malformed_date_falls_back_to_default_duration(self):
        p = _parser_with_fixed_dict(_full_dict(
            duration_days=None,
            start_date="not-a-date",
            end_date="2026-03-23",
        ))
        result = await p.parse("Trip from bad date to March 23 in Brisbane.")
        assert result.duration_days == 3


# ── MockLLMProvider integration ───────────────────────────────────────────────

class TestMockProviderIntegration:
    """
    End-to-end tests through the real MockLLMProvider regex engine.
    These verify common English natural language patterns are handled.
    """

    @pytest.mark.asyncio
    async def test_food_keyword_sets_food_dining_category(self, mock_parser):
        result = await mock_parser.parse(
            "I'd like to spend three days in Brisbane focusing mainly on food."
        )
        assert result.preferred_categories is not None
        assert POICategory.food_dining in result.preferred_categories

    @pytest.mark.asyncio
    async def test_history_keyword_sets_history_culture_category(self, mock_parser):
        result = await mock_parser.parse(
            "Five days in Kyoto exploring history and heritage sites."
        )
        assert result.preferred_categories is not None
        assert POICategory.history_culture in result.preferred_categories

    @pytest.mark.asyncio
    async def test_luxury_keyword_sets_luxury_budget(self, mock_parser):
        result = await mock_parser.parse(
            "Three days in Paris, luxury travel, the best hotels."
        )
        assert result.budget_level == BudgetLevel.luxury

    @pytest.mark.asyncio
    async def test_budget_keyword_sets_budget_level(self, mock_parser):
        result = await mock_parser.parse(
            "A cheap, affordable five-day trip to Bangkok."
        )
        assert result.budget_level == BudgetLevel.budget

    @pytest.mark.asyncio
    async def test_relaxed_keyword_sets_relaxed_pace(self, mock_parser):
        result = await mock_parser.parse(
            "A leisurely four days in Kyoto, no rush."
        )
        assert result.travel_pace == TravelPace.relaxed

    @pytest.mark.asyncio
    async def test_intensive_keyword_sets_intensive_pace(self, mock_parser):
        result = await mock_parser.parse(
            "An intensive packed week in Tokyo, fit in as much as possible."
        )
        assert result.travel_pace == TravelPace.intensive

    @pytest.mark.asyncio
    async def test_iso_dates_compute_correct_duration(self, mock_parser):
        result = await mock_parser.parse(
            "Going to Singapore from 2026-04-01 to 2026-04-05."
        )
        assert result.duration_days == 4

    @pytest.mark.asyncio
    async def test_word_number_duration_parsed(self, mock_parser):
        result = await mock_parser.parse(
            "I want to spend three days in Brisbane."
        )
        assert result.duration_days == 3

    @pytest.mark.asyncio
    async def test_digit_duration_parsed(self, mock_parser):
        result = await mock_parser.parse(
            "A 5-day trip to Melbourne focusing on art and museums."
        )
        assert result.duration_days == 5

    @pytest.mark.asyncio
    async def test_missing_destination_raises_422(self, mock_parser):
        with pytest.raises(HTTPException) as exc_info:
            await mock_parser.parse(
                "I want to travel somewhere for a few days."
            )
        assert exc_info.value.status_code == 422

    @pytest.mark.asyncio
    async def test_result_is_trip_request(self, mock_parser):
        result = await mock_parser.parse(
            "Three days in Brisbane focusing on food."
        )
        assert isinstance(result, TripRequest)
