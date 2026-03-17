"""Unit tests for app/core/day_allocator.py"""

import pytest

from app.core.day_allocator import DayAllocator
from app.core.persona_builder import PersonaBuilder
from app.core.poi_scorer import POIScorer
from app.schemas.common import BudgetLevel, POICategory, TravelPace
from app.schemas.itinerary import DailyWeather
from app.schemas.poi import POI
from app.schemas.trip_request import InterestWeights, TripConstraints, TripRequest


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def allocator() -> DayAllocator:
    return DayAllocator()


@pytest.fixture
def builder() -> PersonaBuilder:
    return PersonaBuilder()


@pytest.fixture
def scorer() -> POIScorer:
    return POIScorer()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_poi(**overrides) -> POI:
    defaults = dict(
        id="p001",
        name="Test POI",
        destination="beijing",
        category=POICategory.history_culture,
        latitude=39.9,
        longitude=116.4,
        district="东城区",
        popularity_score=8.0,
        quality_score=8.0,
        avg_cost_cny=50.0,
        budget_tier=BudgetLevel.mid_range,
        duration_hours=2.0,
        indoor=False,
        child_friendly=True,
        accessible=True,
    )
    defaults.update(overrides)
    return POI(**defaults)


def _make_persona(builder: PersonaBuilder, **overrides):
    defaults = dict(
        destination="beijing",
        duration_days=3,
        budget_level=BudgetLevel.mid_range,
        travel_pace=TravelPace.moderate,
        interests=InterestWeights(),
        constraints=TripConstraints(),
    )
    defaults.update(overrides)
    return builder.build(TripRequest(**defaults))


def _make_weather(condition: str = "Sunny") -> DailyWeather:
    return DailyWeather(
        date="2026-03-20",
        condition=condition,
        temp_high_c=20.0,
        temp_low_c=10.0,
        humidity_pct=60,
    )


# ── Allocation count ───────────────────────────────────────────────────────────

class TestAllocationCount:
    def test_result_length_equals_duration_days(self, allocator, builder, scorer):
        pois = [_make_poi(id=f"p{i}", duration_hours=1.5) for i in range(12)]
        persona = _make_persona(builder, duration_days=3)
        scored = scorer.score_all(pois, persona)
        result = allocator.allocate(scored, persona)
        assert len(result) == 3

    def test_each_day_does_not_exceed_max_pois(self, allocator, builder, scorer):
        pois = [_make_poi(id=f"p{i}", duration_hours=1.0) for i in range(20)]
        persona = _make_persona(builder, travel_pace=TravelPace.moderate)
        scored = scorer.score_all(pois, persona)
        result = allocator.allocate(scored, persona)
        for day in result:
            assert len(day) <= persona.pois_per_day_max

    def test_empty_poi_pool_returns_empty_days(self, allocator, builder):
        persona = _make_persona(builder, duration_days=2)
        result = allocator.allocate([], persona)
        assert len(result) == 2
        assert all(day == [] for day in result)

    def test_fewer_pois_than_days_does_not_crash(self, allocator, builder, scorer):
        pois = [_make_poi(id="only_one", duration_hours=2.0)]
        persona = _make_persona(builder, duration_days=3)
        scored = scorer.score_all(pois, persona)
        result = allocator.allocate(scored, persona)
        assert len(result) == 3
        total_allocated = sum(len(day) for day in result)
        assert total_allocated == 1   # single POI ends up on exactly one day

    def test_each_poi_allocated_at_most_once(self, allocator, builder, scorer):
        pois = [_make_poi(id=f"p{i}", duration_hours=1.0) for i in range(10)]
        persona = _make_persona(builder, duration_days=3)
        scored = scorer.score_all(pois, persona)
        result = allocator.allocate(scored, persona)
        all_ids = [sp.poi.id for day in result for sp in day]
        assert len(all_ids) == len(set(all_ids))


# ── Constraint respect ────────────────────────────────────────────────────────

class TestConstraintRespect:
    def test_zero_score_poi_never_allocated(self, allocator, builder, scorer):
        poi_blocked = _make_poi(id="blocked", category=POICategory.shopping)
        poi_normal  = _make_poi(id="normal",  category=POICategory.history_culture)
        persona = _make_persona(
            builder,
            constraints=TripConstraints(avoid_categories=[POICategory.shopping]),
        )
        scored = scorer.score_all([poi_blocked, poi_normal], persona)
        result = allocator.allocate(scored, persona)
        all_ids = [sp.poi.id for day in result for sp in day]
        assert "blocked" not in all_ids
        assert "normal" in all_ids


# ── Weather behaviour ─────────────────────────────────────────────────────────

class TestWeatherBehaviour:
    def test_indoor_pois_still_allocated_on_rainy_day(
        self, allocator, builder, scorer
    ):
        indoor_poi  = _make_poi(id="indoor",  indoor=True,  duration_hours=2.0)
        outdoor_poi = _make_poi(id="outdoor", indoor=False, duration_hours=2.0)
        persona = _make_persona(builder, duration_days=1)
        scored = scorer.score_all([indoor_poi, outdoor_poi], persona)
        result = allocator.allocate(scored, persona, [_make_weather("Rainy")])
        all_ids = [sp.poi.id for day in result for sp in day]
        assert "indoor" in all_ids   # indoor POI must survive weather adjustment

    def test_scored_poi_total_score_not_mutated_by_weather(
        self, allocator, builder, scorer
    ):
        """ScoredPOI.total_score must be unchanged after allocation."""
        pois = [_make_poi(id=f"p{i}", duration_hours=1.0) for i in range(6)]
        persona = _make_persona(builder, duration_days=2)
        scored = scorer.score_all(pois, persona)
        original_scores = {sp.poi.id: sp.total_score for sp in scored}

        allocator.allocate(scored, persona, [_make_weather("Rainy")] * 2)

        for sp in scored:
            assert sp.total_score == original_scores[sp.poi.id], (
                f"total_score of {sp.poi.id} was mutated during allocation"
            )

    def test_allocation_works_without_weather(self, allocator, builder, scorer):
        pois = [_make_poi(id=f"p{i}", duration_hours=1.5) for i in range(9)]
        persona = _make_persona(builder, duration_days=3)
        scored = scorer.score_all(pois, persona)
        result = allocator.allocate(scored, persona, weather_list=None)
        assert len(result) == 3


# ── Time budget ───────────────────────────────────────────────────────────────

class TestTimeBudget:
    def test_daily_duration_within_budget(self, allocator, builder, scorer):
        # Each POI takes 3h; daily budget is 8h, so ≤ 2-3 POIs per day.
        pois = [_make_poi(id=f"p{i}", duration_hours=3.0) for i in range(12)]
        persona = _make_persona(builder, duration_days=3)
        scored = scorer.score_all(pois, persona)
        result = allocator.allocate(scored, persona)
        for day in result:
            total_h = sum(sp.poi.duration_hours for sp in day)
            # The allocator allows up to budget + 0.5h overrun.
            assert total_h <= 8.5, f"Day exceeds time budget: {total_h}h"


# ── Food cap ──────────────────────────────────────────────────────────────────

class TestFoodCap:
    def test_food_dining_capped_at_three_per_day(self, allocator, builder, scorer):
        # 10 food POIs with short duration — without the cap all would fill a day.
        pois = [
            _make_poi(id=f"f{i}", category=POICategory.food_dining, duration_hours=1.0)
            for i in range(10)
        ]
        persona = _make_persona(
            builder,
            duration_days=1,
            interests=InterestWeights(food_dining=1.0),
        )
        scored = scorer.score_all(pois, persona)
        result = allocator.allocate(scored, persona)
        food_count = sum(
            1 for sp in result[0] if sp.poi.category == POICategory.food_dining
        )
        assert food_count <= 3

    def test_non_food_fills_remaining_slots_when_food_capped(
        self, allocator, builder, scorer
    ):
        # 5 food + 5 local_life POIs; food should be capped, local_life should appear.
        food_pois = [
            _make_poi(id=f"f{i}", category=POICategory.food_dining, duration_hours=1.0)
            for i in range(5)
        ]
        local_pois = [
            _make_poi(id=f"l{i}", category=POICategory.local_life, duration_hours=1.0)
            for i in range(5)
        ]
        persona = _make_persona(
            builder,
            duration_days=1,
            interests=InterestWeights(food_dining=0.5, local_life=0.5),
        )
        scored = scorer.score_all(food_pois + local_pois, persona)
        result = allocator.allocate(scored, persona)
        categories = {sp.poi.category for sp in result[0]}
        assert POICategory.local_life in categories
