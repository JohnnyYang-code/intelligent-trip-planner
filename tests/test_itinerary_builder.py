"""
Tests for app/services/itinerary_builder._day_theme()
and app/llm/prompt_templates.build_overview_prompt() theme deduplication.
"""

from app.llm.prompt_templates import build_overview_prompt
from app.schemas.common import BudgetLevel, POICategory
from app.schemas.poi import POI, ScheduledPOI
from app.services.itinerary_builder import _day_theme


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_scheduled(poi_id: str, category: POICategory) -> ScheduledPOI:
    poi = POI(
        id=poi_id,
        name=poi_id,
        destination="brisbane",
        category=category,
        latitude=-27.47,
        longitude=153.02,
        district="CBD",
        popularity_score=7.0,
        quality_score=7.0,
        avg_cost_cny=100.0,
        budget_tier=BudgetLevel.mid_range,
        duration_hours=1.5,
        indoor=False,
    )
    return ScheduledPOI(
        poi=poi,
        visit_order=1,
        suggested_start_time="09:00",
        suggested_duration_hours=1.5,
        recommendation_reason="",
    )


def _food(i: int) -> ScheduledPOI:
    return _make_scheduled(f"food{i}", POICategory.food_dining)


def _local(i: int) -> ScheduledPOI:
    return _make_scheduled(f"local{i}", POICategory.local_life)


def _history(i: int) -> ScheduledPOI:
    return _make_scheduled(f"hist{i}", POICategory.history_culture)


# ── _day_theme tests ──────────────────────────────────────────────────────────

class TestDayTheme:
    def test_empty_day_returns_free_day(self):
        assert _day_theme([]) == "Free Day"

    def test_single_category_returns_plain_label(self):
        assert _day_theme([_food(0), _food(1), _food(2)]) == "Food & Dining"

    def test_dominant_too_strong_no_blend(self):
        # 4 food + 1 local: runner-up (1) < dominant (4) // 2 = 2 → no blend
        pois = [_food(i) for i in range(4)] + [_local(0)]
        assert _day_theme(pois) == "Food & Dining"

    def test_close_runner_up_produces_blended_label(self):
        # 2 food + 1 local: runner-up (1) >= dominant (2) // 2 = 1 → blend
        pois = [_food(0), _food(1), _local(0)]
        theme = _day_theme(pois)
        assert "Food & Dining" in theme
        assert "Local Life" in theme

    def test_equal_counts_produces_blended_label(self):
        # 2 food + 2 local
        pois = [_food(0), _food(1), _local(0), _local(1)]
        theme = _day_theme(pois)
        assert "Food & Dining" in theme
        assert "Local Life" in theme

    def test_three_food_one_local_blends(self):
        # 3 food + 1 local: runner-up (1) >= 3 // 2 = 1 → blend
        pois = [_food(i) for i in range(3)] + [_local(0)]
        theme = _day_theme(pois)
        assert "Food & Dining" in theme
        assert "Local Life" in theme

    def test_separator_is_middle_dot(self):
        pois = [_food(0), _food(1), _local(0)]
        assert "·" in _day_theme(pois)

    def test_single_poi_returns_its_category(self):
        assert _day_theme([_history(0)]) == "History & Culture"


# ── Overview prompt theme deduplication tests ─────────────────────────────────

class TestOverviewThemeDedup:
    def test_repeated_themes_deduplicated(self):
        prompt = build_overview_prompt(
            destination="Brisbane",
            duration_days=3,
            persona_summary="Foodie traveller",
            day_themes=["Food & Dining", "Food & Dining", "Food & Dining"],
            weather_summary="sunny",
        )
        # "Food & Dining" should appear only once in the themes line
        themes_line = [l for l in prompt.splitlines() if l.startswith("Daily themes:")][0]
        assert themes_line.count("Food & Dining") == 1

    def test_distinct_themes_all_preserved(self):
        themes = ["Food & Dining · Local Life", "Nature & Scenery", "History & Culture"]
        prompt = build_overview_prompt(
            destination="Brisbane",
            duration_days=3,
            persona_summary="Explorer",
            day_themes=themes,
            weather_summary="sunny",
        )
        for theme in themes:
            assert theme in prompt

    def test_empty_themes_uses_fallback(self):
        prompt = build_overview_prompt(
            destination="Brisbane",
            duration_days=1,
            persona_summary="Explorer",
            day_themes=[],
            weather_summary="sunny",
        )
        assert "mixed activities" in prompt
