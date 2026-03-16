"""Unit tests for app/core/persona_builder.py"""

import pytest

from app.core.persona_builder import PersonaBuilder
from app.schemas.common import BudgetLevel, POICategory, TravelPace
from app.schemas.trip_request import InterestWeights, TripConstraints, TripRequest


@pytest.fixture
def builder() -> PersonaBuilder:
    return PersonaBuilder()


def _make_request(**overrides) -> TripRequest:
    defaults = dict(
        destination="beijing",
        duration_days=3,
        budget_level=BudgetLevel.mid_range,
        travel_pace=TravelPace.moderate,
        interests=InterestWeights(),
        constraints=TripConstraints(),
    )
    defaults.update(overrides)
    return TripRequest(**defaults)


# ── Interest vector normalisation ─────────────────────────────────────────────

class TestInterestNormalisation:
    def test_vector_sums_to_one(self, builder):
        request = _make_request(
            interests=InterestWeights(history_culture=0.9, food_dining=0.6)
        )
        persona = builder.build(request)
        total = sum(persona.interest_vector.values())
        assert abs(total - 1.0) < 1e-6

    def test_all_zero_weights_fall_back_to_equal(self, builder):
        request = _make_request(
            interests=InterestWeights(
                history_culture=0.0,
                nature_scenery=0.0,
                food_dining=0.0,
                shopping=0.0,
                art_museum=0.0,
                entertainment=0.0,
                local_life=0.0,
            )
        )
        persona = builder.build(request)
        values = list(persona.interest_vector.values())
        # All weights should be equal
        assert all(abs(v - values[0]) < 1e-9 for v in values)
        assert abs(sum(values) - 1.0) < 1e-6

    def test_high_interest_category_has_highest_weight(self, builder):
        request = _make_request(
            interests=InterestWeights(
                history_culture=0.9,
                nature_scenery=0.1,
                food_dining=0.1,
                shopping=0.1,
                art_museum=0.1,
                entertainment=0.1,
                local_life=0.1,
            )
        )
        persona = builder.build(request)
        max_key = max(persona.interest_vector, key=persona.interest_vector.__getitem__)
        assert max_key == POICategory.history_culture.value

    def test_vector_keys_match_all_categories(self, builder):
        persona = builder.build(_make_request())
        expected_keys = {c.value for c in POICategory}
        assert set(persona.interest_vector.keys()) == expected_keys


# ── Budget sensitivity ─────────────────────────────────────────────────────────

class TestBudgetSensitivity:
    def test_budget_level_gives_high_sensitivity(self, builder):
        persona = builder.build(_make_request(budget_level=BudgetLevel.budget))
        assert persona.budget_sensitivity == pytest.approx(0.9, abs=0.01)

    def test_mid_range_gives_medium_sensitivity(self, builder):
        persona = builder.build(_make_request(budget_level=BudgetLevel.mid_range))
        assert persona.budget_sensitivity == pytest.approx(0.5, abs=0.01)

    def test_luxury_gives_low_sensitivity(self, builder):
        persona = builder.build(_make_request(budget_level=BudgetLevel.luxury))
        assert persona.budget_sensitivity == pytest.approx(0.1, abs=0.01)

    def test_with_children_increases_sensitivity(self, builder):
        base = builder.build(_make_request(budget_level=BudgetLevel.mid_range))
        with_children = builder.build(
            _make_request(
                budget_level=BudgetLevel.mid_range,
                constraints=TripConstraints(with_children=True),
            )
        )
        assert with_children.budget_sensitivity > base.budget_sensitivity

    def test_sensitivity_never_exceeds_one(self, builder):
        persona = builder.build(
            _make_request(
                budget_level=BudgetLevel.budget,
                constraints=TripConstraints(with_children=True, with_elderly=True),
            )
        )
        assert persona.budget_sensitivity <= 1.0


# ── Daily POI capacity ────────────────────────────────────────────────────────

class TestDailyCapacity:
    def test_relaxed_pace(self, builder):
        persona = builder.build(_make_request(travel_pace=TravelPace.relaxed))
        assert persona.pois_per_day_target == 2
        assert persona.pois_per_day_max == 3

    def test_moderate_pace(self, builder):
        persona = builder.build(_make_request(travel_pace=TravelPace.moderate))
        assert persona.pois_per_day_target == 3
        assert persona.pois_per_day_max == 4

    def test_intensive_pace(self, builder):
        persona = builder.build(_make_request(travel_pace=TravelPace.intensive))
        assert persona.pois_per_day_target == 5
        assert persona.pois_per_day_max == 6

    def test_target_less_than_max(self, builder):
        for pace in TravelPace:
            persona = builder.build(_make_request(travel_pace=pace))
            assert persona.pois_per_day_target < persona.pois_per_day_max


# ── Persona summary ───────────────────────────────────────────────────────────

class TestPersonaSummary:
    def test_summary_is_non_empty(self, builder):
        persona = builder.build(_make_request())
        assert len(persona.persona_summary) > 10

    def test_summary_contains_destination(self, builder):
        persona = builder.build(_make_request(destination="shanghai"))
        assert "shanghai" in persona.persona_summary.lower()

    def test_summary_contains_duration(self, builder):
        persona = builder.build(_make_request(duration_days=5))
        assert "5" in persona.persona_summary

    def test_summary_mentions_children_constraint(self, builder):
        persona = builder.build(
            _make_request(constraints=TripConstraints(with_children=True))
        )
        assert "children" in persona.persona_summary.lower()

    def test_summary_mentions_accessibility(self, builder):
        persona = builder.build(
            _make_request(constraints=TripConstraints(accessibility_required=True))
        )
        assert "accessibility" in persona.persona_summary.lower()


# ── Constraints passthrough ───────────────────────────────────────────────────

class TestConstraintsPassthrough:
    def test_constraints_are_preserved(self, builder):
        constraints = TripConstraints(
            avoid_categories=[POICategory.shopping],
            with_elderly=True,
        )
        persona = builder.build(_make_request(constraints=constraints))
        assert POICategory.shopping in persona.constraints.avoid_categories
        assert persona.constraints.with_elderly is True
