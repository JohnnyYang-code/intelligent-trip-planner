import logging

from app.config.settings import get_settings
from app.schemas.common import BudgetLevel, POICategory
from app.schemas.persona import TravelerPersona
from app.schemas.poi import POI, ScoreBreakdown, ScoredPOI

logger = logging.getLogger(__name__)

# Categories that feel inherently crowded / commercial.
# When a traveller has the "avoid_crowds" soft preference inferred from their
# free-text input, POIs in these categories receive a strong soft penalty so
# that unselected shopping and entertainment venues don't sneak in via high
# popularity or budget-fit scores alone.
_CROWD_SENSITIVE_CATEGORIES: frozenset[POICategory] = frozenset({
    POICategory.shopping,
    POICategory.entertainment,
})
_AVOID_CROWDS_MULTIPLIER: float = 0.25   # 75% score reduction

# Budget tier ordering used to compute tier gap for scoring.
_BUDGET_ORDER: dict[BudgetLevel, int] = {
    BudgetLevel.budget:    0,
    BudgetLevel.mid_range: 1,
    BudgetLevel.luxury:    2,
}


class POIScorer:
    """
    Scores each POI against a TravelerPersona using a weighted formula.

    Formula
    -------
    total_score = (
        w_interest   × interest_score(poi, persona)
      + w_popularity × popularity_score(poi)
      + w_budget     × budget_fit_score(poi, persona)
    ) × constraint_multiplier(poi, persona)

    Default weights (overridable via settings):
        w_interest   = 0.55
        w_popularity = 0.25
        w_budget     = 0.20

    All component scores are in [0, 1].
    The constraint_multiplier is 0.0 if a hard constraint is violated,
    which effectively removes the POI from consideration.
    """

    def __init__(self) -> None:
        s = get_settings()
        self._w_interest = s.score_weight_interest
        self._w_popularity = s.score_weight_popularity
        self._w_budget = s.score_weight_budget

    def score_all(
        self,
        pois: list[POI],
        persona: TravelerPersona,
    ) -> list[ScoredPOI]:
        """
        Score every POI in the list and return them sorted by total_score descending.
        POIs with a zero constraint_multiplier (violated constraints) are included
        in the list with total_score = 0.0 so callers can inspect them if needed.
        """
        scored = [self.score_one(poi, persona) for poi in pois]
        scored.sort(key=lambda s: s.total_score, reverse=True)
        logger.debug(
            "Scored %d POIs. Top score: %.3f (%s)",
            len(scored),
            scored[0].total_score if scored else 0,
            scored[0].poi.name if scored else "-",
        )
        return scored

    def score_one(self, poi: POI, persona: TravelerPersona) -> ScoredPOI:
        """Compute the composite score for a single POI."""
        interest = self._interest_score(poi, persona)
        popularity = self._popularity_score(poi)
        budget = self._budget_fit_score(poi, persona)
        multiplier = self._constraint_multiplier(poi, persona)

        total = (
            self._w_interest * interest
            + self._w_popularity * popularity
            + self._w_budget * budget
        ) * multiplier

        return ScoredPOI(
            poi=poi,
            total_score=round(total, 4),
            score_breakdown=ScoreBreakdown(
                interest_score=round(interest, 4),
                popularity_score=round(popularity, 4),
                budget_score=round(budget, 4),
                constraint_multiplier=round(multiplier, 4),
            ),
        )

    # ── Scoring components ────────────────────────────────────────────────────

    @staticmethod
    def _interest_score(poi: POI, persona: TravelerPersona) -> float:
        """
        interest_score = persona_weight_for_category × (poi.quality_score / 10)

        Combines the traveller's interest in the category with the POI's
        intrinsic quality. A high-quality POI in a low-interest category
        still scores lower than a moderate-quality POI in a top-interest one.
        """
        category_weight = persona.interest_vector.get(poi.category.value, 0.0)
        quality_normalised = poi.quality_score / 10.0
        return category_weight * quality_normalised

    @staticmethod
    def _popularity_score(poi: POI) -> float:
        """Normalise the raw 0–10 popularity score to [0, 1]."""
        return poi.popularity_score / 10.0

    @staticmethod
    def _budget_fit_score(poi: POI, persona: TravelerPersona) -> float:
        """
        Measures how well the POI's price tier matches the traveller's budget.

        Same tier:      base = 1.0
        One tier apart: base = 0.5
        Two tiers apart: base = 0.0  (hard zero — two-tier mismatch is a
                                       strong signal of incompatibility)

        The base is then further reduced by (sensitivity × gap × 0.4).
        A mid_range traveller seeing a luxury POI (gap=1, sensitivity=0.5)
        gets a budget_score of 0.30 instead of the old 0.45, making the
        budget component a more meaningful discriminator.
        """
        poi_tier_rank = _BUDGET_ORDER[poi.budget_tier]
        traveler_tier_rank = _BUDGET_ORDER[persona.budget_level]
        gap = abs(poi_tier_rank - traveler_tier_rank)

        base_map = {0: 1.0, 1: 0.5, 2: 0.0}
        base = base_map[gap]

        penalty = persona.budget_sensitivity * gap * 0.4
        score = base - penalty
        return max(0.0, min(1.0, score))

    @staticmethod
    def _constraint_multiplier(poi: POI, persona: TravelerPersona) -> float:
        """
        Returns 0.0 if any hard constraint is violated; otherwise 1.0.

        Soft penalties (child-unfriendly when with children, etc.) reduce
        the multiplier but do not zero it out completely, allowing those
        POIs to appear at the bottom of ranked results.
        """
        constraints = persona.constraints

        # Hard block: explicitly avoided category.
        if poi.category in constraints.avoid_categories:
            return 0.0

        # Hard block: accessibility required but POI is not accessible.
        if constraints.accessibility_required and not poi.accessible:
            return 0.0

        multiplier = 1.0

        # Soft penalty: not child-friendly when travelling with children.
        if constraints.with_children and not poi.child_friendly:
            multiplier *= 0.3

        # Soft penalty: not accessible when travelling with elderly.
        if constraints.with_elderly and not poi.accessible:
            multiplier *= 0.4

        # Soft penalty: avoid_crowds preference suppresses shopping and
        # entertainment POIs, which tend to be busy commercial venues.
        # The tag is inferred from free-text such as "less crowded" or
        # "avoid tourist traps" before Stage 2 scoring runs.
        if (
            "avoid_crowds" in persona.inferred_soft_preferences
            and poi.category in _CROWD_SENSITIVE_CATEGORIES
        ):
            multiplier *= _AVOID_CROWDS_MULTIPLIER

        return multiplier
