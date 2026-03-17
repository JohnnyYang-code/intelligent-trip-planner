"""Unit tests for app/core/poi_scorer.py"""

import pytest

from app.core.persona_builder import PersonaBuilder
from app.core.poi_scorer import POIScorer
from app.schemas.common import BudgetLevel, POICategory, TravelPace
from app.schemas.poi import POI
from app.schemas.trip_request import InterestWeights, TripConstraints, TripRequest


@pytest.fixture
def scorer() -> POIScorer:
    return POIScorer()


@pytest.fixture
def builder() -> PersonaBuilder:
    return PersonaBuilder()


def _make_poi(**overrides) -> POI:
    defaults = dict(
        id="test_001",
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


def _make_persona(builder, **overrides) -> object:
    defaults = dict(
        destination="beijing",
        duration_days=3,
        budget_level=BudgetLevel.mid_range,
        travel_pace=TravelPace.moderate,
        interests=InterestWeights(history_culture=0.9, food_dining=0.1),
        constraints=TripConstraints(),
    )
    defaults.update(overrides)
    return builder.build(TripRequest(**defaults))


# ── Score range ───────────────────────────────────────────────────────────────

class TestScoreRange:
    def test_total_score_between_zero_and_one(self, scorer, builder):
        poi = _make_poi()
        persona = _make_persona(builder)
        result = scorer.score_one(poi, persona)
        assert 0.0 <= result.total_score <= 1.0

    def test_all_component_scores_between_zero_and_one(self, scorer, builder):
        poi = _make_poi()
        persona = _make_persona(builder)
        result = scorer.score_one(poi, persona)
        bd = result.score_breakdown
        assert 0.0 <= bd.interest_score <= 1.0
        assert 0.0 <= bd.popularity_score <= 1.0
        assert 0.0 <= bd.budget_score <= 1.0

    def test_score_all_returns_sorted_descending(self, scorer, builder):
        pois = [
            _make_poi(id="a", popularity_score=9.5, quality_score=9.5),
            _make_poi(id="b", popularity_score=5.0, quality_score=5.0),
            _make_poi(id="c", popularity_score=7.0, quality_score=7.0),
        ]
        persona = _make_persona(builder)
        results = scorer.score_all(pois, persona)
        scores = [r.total_score for r in results]
        assert scores == sorted(scores, reverse=True)


# ── Interest matching ─────────────────────────────────────────────────────────

class TestInterestMatching:
    def test_top_interest_category_scores_higher(self, scorer, builder):
        """A POI in the user's top-interest category should outscore one in a low-interest category."""
        poi_history = _make_poi(
            id="h", category=POICategory.history_culture, quality_score=8.0
        )
        poi_shopping = _make_poi(
            id="s", category=POICategory.shopping, quality_score=8.0
        )
        persona = _make_persona(
            builder,
            interests=InterestWeights(
                history_culture=0.9, shopping=0.1,
                nature_scenery=0.0, food_dining=0.0,
                art_museum=0.0, entertainment=0.0, local_life=0.0,
            ),
        )
        score_history = scorer.score_one(poi_history, persona)
        score_shopping = scorer.score_one(poi_shopping, persona)
        assert score_history.total_score > score_shopping.total_score

    def test_higher_quality_increases_interest_score(self, scorer, builder):
        poi_low_q = _make_poi(id="lq", quality_score=4.0)
        poi_high_q = _make_poi(id="hq", quality_score=9.0)
        persona = _make_persona(builder)
        assert (
            scorer.score_one(poi_high_q, persona).score_breakdown.interest_score
            > scorer.score_one(poi_low_q, persona).score_breakdown.interest_score
        )


# ── Budget fit ────────────────────────────────────────────────────────────────

class TestBudgetFit:
    def test_matching_budget_tier_scores_higher_than_mismatched(self, scorer, builder):
        poi_budget = _make_poi(id="b", budget_tier=BudgetLevel.budget)
        poi_luxury = _make_poi(id="l", budget_tier=BudgetLevel.luxury)
        persona = _make_persona(builder, budget_level=BudgetLevel.budget)
        assert (
            scorer.score_one(poi_budget, persona).score_breakdown.budget_score
            > scorer.score_one(poi_luxury, persona).score_breakdown.budget_score
        )

    def test_luxury_traveler_scores_luxury_poi_higher(self, scorer, builder):
        poi_budget = _make_poi(id="b", budget_tier=BudgetLevel.budget)
        poi_luxury = _make_poi(id="l", budget_tier=BudgetLevel.luxury)
        persona = _make_persona(builder, budget_level=BudgetLevel.luxury)
        assert (
            scorer.score_one(poi_luxury, persona).score_breakdown.budget_score
            > scorer.score_one(poi_budget, persona).score_breakdown.budget_score
        )

    def test_budget_score_never_negative(self, scorer, builder):
        poi = _make_poi(budget_tier=BudgetLevel.luxury)
        persona = _make_persona(builder, budget_level=BudgetLevel.budget)
        result = scorer.score_one(poi, persona)
        assert result.score_breakdown.budget_score >= 0.0


# ── Constraint enforcement ────────────────────────────────────────────────────

class TestConstraints:
    def test_avoided_category_gives_zero_score(self, scorer, builder):
        poi = _make_poi(category=POICategory.shopping)
        persona = _make_persona(
            builder,
            constraints=TripConstraints(avoid_categories=[POICategory.shopping]),
        )
        result = scorer.score_one(poi, persona)
        assert result.total_score == 0.0
        assert result.score_breakdown.constraint_multiplier == 0.0

    def test_inaccessible_poi_blocked_when_required(self, scorer, builder):
        poi = _make_poi(accessible=False)
        persona = _make_persona(
            builder,
            constraints=TripConstraints(accessibility_required=True),
        )
        result = scorer.score_one(poi, persona)
        assert result.total_score == 0.0

    def test_accessible_poi_not_blocked(self, scorer, builder):
        poi = _make_poi(accessible=True)
        persona = _make_persona(
            builder,
            constraints=TripConstraints(accessibility_required=True),
        )
        result = scorer.score_one(poi, persona)
        assert result.total_score > 0.0

    def test_not_child_friendly_reduces_score_but_not_zero(self, scorer, builder):
        poi_unfriendly = _make_poi(id="u", child_friendly=False)
        poi_friendly = _make_poi(id="f", child_friendly=True)
        persona = _make_persona(
            builder,
            constraints=TripConstraints(with_children=True),
        )
        score_unfriendly = scorer.score_one(poi_unfriendly, persona)
        score_friendly = scorer.score_one(poi_friendly, persona)
        # Not blocked, just penalised
        assert score_unfriendly.total_score > 0.0
        assert score_unfriendly.total_score < score_friendly.total_score

    def test_non_accessible_reduces_score_with_elderly(self, scorer, builder):
        poi_inaccessible = _make_poi(id="ia", accessible=False)
        poi_accessible = _make_poi(id="a", accessible=True)
        persona = _make_persona(
            builder,
            constraints=TripConstraints(with_elderly=True),
        )
        score_ia = scorer.score_one(poi_inaccessible, persona)
        score_a = scorer.score_one(poi_accessible, persona)
        assert score_ia.total_score > 0.0     # soft penalty, not blocked
        assert score_ia.total_score < score_a.total_score

    def test_no_constraint_violation_gives_multiplier_one(self, scorer, builder):
        poi = _make_poi()
        persona = _make_persona(builder)
        result = scorer.score_one(poi, persona)
        assert result.score_breakdown.constraint_multiplier == pytest.approx(1.0)


# ── score_all integration ─────────────────────────────────────────────────────

class TestScoreAll:
    def test_returns_same_count_as_input(self, scorer, builder):
        pois = [_make_poi(id=f"p{i}") for i in range(5)]
        persona = _make_persona(builder)
        results = scorer.score_all(pois, persona)
        assert len(results) == 5

    def test_empty_input_returns_empty(self, scorer, builder):
        persona = _make_persona(builder)
        results = scorer.score_all([], persona)
        assert results == []

    def test_blocked_poi_appears_at_bottom(self, scorer, builder):
        poi_blocked = _make_poi(id="blocked", category=POICategory.shopping)
        poi_normal = _make_poi(id="normal", category=POICategory.history_culture)
        persona = _make_persona(
            builder,
            constraints=TripConstraints(avoid_categories=[POICategory.shopping]),
        )
        results = scorer.score_all([poi_blocked, poi_normal], persona)
        assert results[-1].poi.id == "blocked"
        assert results[-1].total_score == 0.0


# ── Budget consistency ────────────────────────────────────────────────────────

class TestBudgetConsistency:
    def test_two_tier_gap_gives_zero_budget_score(self, scorer, builder):
        # budget user (sensitivity=0.9) + luxury POI (gap=2) → base=0.0
        luxury_poi = _make_poi(id="luxury", budget_tier=BudgetLevel.luxury)
        persona = _make_persona(builder, budget_level=BudgetLevel.budget)
        result = scorer.score_one(luxury_poi, persona)
        assert result.score_breakdown.budget_score == 0.0

    def test_one_tier_gap_score_below_half(self, scorer, builder):
        # mid_range user (sensitivity=0.5) + luxury POI (gap=1)
        # new: base=0.5 − 0.5×0.4 = 0.30 (below 0.5)
        luxury_poi = _make_poi(id="luxury", budget_tier=BudgetLevel.luxury)
        persona = _make_persona(builder, budget_level=BudgetLevel.mid_range)
        result = scorer.score_one(luxury_poi, persona)
        assert result.score_breakdown.budget_score < 0.5

    def test_matching_tier_gives_max_budget_score(self, scorer, builder):
        mid_poi = _make_poi(id="mid", budget_tier=BudgetLevel.mid_range)
        persona = _make_persona(builder, budget_level=BudgetLevel.mid_range)
        result = scorer.score_one(mid_poi, persona)
        assert result.score_breakdown.budget_score == 1.0

    def test_budget_score_non_negative_for_all_tier_combinations(
        self, scorer, builder
    ):
        for poi_tier in BudgetLevel:
            for user_tier in BudgetLevel:
                poi = _make_poi(id="p", budget_tier=poi_tier)
                persona = _make_persona(builder, budget_level=user_tier)
                result = scorer.score_one(poi, persona)
                assert result.score_breakdown.budget_score >= 0.0


# ── Soft preference hook ───────────────────────────────────────────────────────

class TestSoftPreferenceHook:
    def test_avoid_crowds_penalises_shopping_poi(self, scorer, builder):
        """Shopping POI should score much lower when avoid_crowds is inferred."""
        poi = _make_poi(category=POICategory.shopping, popularity_score=9.0, quality_score=9.0)
        persona = _make_persona(builder)
        persona.inferred_soft_preferences = ["avoid_crowds"]
        result = scorer.score_one(poi, persona)
        # Without the tag the POI would score high via popularity/budget;
        # with the tag the constraint_multiplier is reduced to 0.25.
        assert result.score_breakdown.constraint_multiplier == pytest.approx(0.25)

    def test_avoid_crowds_penalises_entertainment_poi(self, scorer, builder):
        poi = _make_poi(category=POICategory.entertainment)
        persona = _make_persona(builder)
        persona.inferred_soft_preferences = ["avoid_crowds"]
        result = scorer.score_one(poi, persona)
        assert result.score_breakdown.constraint_multiplier == pytest.approx(0.25)

    def test_avoid_crowds_does_not_penalise_preferred_categories(self, scorer, builder):
        """Nature and local_life POIs must be unaffected by avoid_crowds."""
        for cat in (POICategory.nature_scenery, POICategory.local_life,
                    POICategory.history_culture, POICategory.food_dining):
            poi = _make_poi(category=cat)
            persona = _make_persona(builder)
            persona.inferred_soft_preferences = ["avoid_crowds"]
            result = scorer.score_one(poi, persona)
            assert result.score_breakdown.constraint_multiplier == pytest.approx(1.0), (
                f"category {cat} should not be penalised"
            )

    def test_avoid_crowds_shopping_scores_lower_than_without_tag(self, scorer, builder):
        poi = _make_poi(category=POICategory.shopping, popularity_score=9.0, quality_score=9.0)
        persona_no_tag = _make_persona(builder)
        persona_with_tag = _make_persona(builder)
        persona_with_tag.inferred_soft_preferences = ["avoid_crowds"]
        score_no  = scorer.score_one(poi, persona_no_tag).total_score
        score_yes = scorer.score_one(poi, persona_with_tag).total_score
        assert score_yes < score_no

    def test_other_soft_prefs_do_not_affect_multiplier(self, scorer, builder):
        """Tags unrelated to crowds must not change the constraint multiplier."""
        poi = _make_poi(category=POICategory.shopping)
        persona = _make_persona(builder)
        persona.inferred_soft_preferences = ["relaxed_pace", "food_focused"]
        result = scorer.score_one(poi, persona)
        assert result.score_breakdown.constraint_multiplier == pytest.approx(1.0)
