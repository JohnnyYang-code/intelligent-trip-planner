"""Unit tests for app/core/route_optimizer._interleave_meals()"""

from app.core.route_optimizer import _interleave_meals
from app.schemas.common import BudgetLevel, POICategory
from app.schemas.poi import POI, ScoreBreakdown, ScoredPOI


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_scored(poi_id: str, category: POICategory) -> ScoredPOI:
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
        indoor=True,
    )
    breakdown = ScoreBreakdown(
        interest_score=0.5,
        popularity_score=0.5,
        budget_score=0.5,
        constraint_multiplier=1.0,
    )
    return ScoredPOI(poi=poi, score_breakdown=breakdown, total_score=0.5)


def _sight(i: int) -> ScoredPOI:
    return _make_scored(f"sight{i}", POICategory.local_life)


def _meal(i: int) -> ScoredPOI:
    return _make_scored(f"meal{i}", POICategory.food_dining)


# ── _interleave_meals tests ───────────────────────────────────────────────────

class TestInterleave:
    def test_no_meals_returns_sights_unchanged(self):
        sights = [_sight(0), _sight(1), _sight(2)]
        result = _interleave_meals(sights, [])
        assert [s.poi.id for s in result] == ["sight0", "sight1", "sight2"]

    def test_no_sights_returns_meals(self):
        meals = [_meal(0), _meal(1)]
        result = _interleave_meals([], meals)
        assert [s.poi.id for s in result] == ["meal0", "meal1"]

    def test_one_meal_placed_at_midpoint(self):
        # 4 sights → mid = 2 → [s0, s1, meal0, s2, s3]
        sights = [_sight(i) for i in range(4)]
        result = _interleave_meals(sights, [_meal(0)])
        ids = [s.poi.id for s in result]
        assert ids == ["sight0", "sight1", "meal0", "sight2", "sight3"]

    def test_two_meals_lunch_then_dinner(self):
        # 4 sights → mid = 2 → [s0, s1, meal0, s2, s3, meal1]
        sights = [_sight(i) for i in range(4)]
        result = _interleave_meals(sights, [_meal(0), _meal(1)])
        ids = [s.poi.id for s in result]
        assert ids == ["sight0", "sight1", "meal0", "sight2", "sight3", "meal1"]

    def test_three_meals_breakfast_lunch_dinner(self):
        # 4 sights → mid = 2 → [meal0, s0, s1, meal1, s2, s3, meal2]
        sights = [_sight(i) for i in range(4)]
        result = _interleave_meals(sights, [_meal(i) for i in range(3)])
        ids = [s.poi.id for s in result]
        assert ids == [
            "meal0", "sight0", "sight1", "meal1", "sight2", "sight3", "meal2"
        ]

    def test_meal_count_preserved(self):
        sights = [_sight(i) for i in range(3)]
        for n_meals in range(4):
            meals = [_meal(i) for i in range(n_meals)]
            result = _interleave_meals(sights, meals)
            actual_meals = [s for s in result if s.poi.category == POICategory.food_dining]
            assert len(actual_meals) == n_meals

    def test_sight_count_preserved(self):
        sights = [_sight(i) for i in range(3)]
        meals = [_meal(i) for i in range(2)]
        result = _interleave_meals(sights, meals)
        actual_sights = [s for s in result if s.poi.category != POICategory.food_dining]
        assert len(actual_sights) == 3
