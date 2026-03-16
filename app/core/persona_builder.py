import logging

from app.schemas.common import BudgetLevel, POICategory, TravelPace
from app.schemas.persona import TravelerPersona
from app.schemas.trip_request import InterestWeights, TripRequest

logger = logging.getLogger(__name__)

# Maps travel pace to (target_pois_per_day, max_pois_per_day).
_PACE_CAPACITY: dict[TravelPace, tuple[int, int]] = {
    TravelPace.relaxed:   (2, 3),
    TravelPace.moderate:  (3, 4),
    TravelPace.intensive: (5, 6),
}

# Base budget sensitivity per level.
_BASE_SENSITIVITY: dict[BudgetLevel, float] = {
    BudgetLevel.budget:    0.9,
    BudgetLevel.mid_range: 0.5,
    BudgetLevel.luxury:    0.1,
}

# Category labels used in the persona summary string.
_CATEGORY_LABELS: dict[str, str] = {
    POICategory.history_culture: "history & culture",
    POICategory.nature_scenery:  "nature & scenery",
    POICategory.food_dining:     "food & dining",
    POICategory.shopping:        "shopping",
    POICategory.art_museum:      "art & museums",
    POICategory.entertainment:   "entertainment",
    POICategory.local_life:      "local life",
}


class PersonaBuilder:
    """
    Converts a TripRequest into a TravelerPersona.

    All logic is pure Python — no external calls, no side effects.
    The resulting persona is the single source of truth for all downstream
    planning modules (scorer, allocator, route optimiser, LLM prompts).
    """

    def build(self, request: TripRequest) -> TravelerPersona:
        interest_vector = self._normalise_interests(request.interests)
        budget_sensitivity = self._budget_sensitivity(request)
        target, maximum = _PACE_CAPACITY[request.travel_pace]
        summary = self._build_summary(request, interest_vector)

        logger.debug("Built persona for '%s': %s", request.destination, summary)

        return TravelerPersona(
            destination=request.destination,
            duration_days=request.duration_days,
            budget_level=request.budget_level,
            travel_pace=request.travel_pace,
            interest_vector=interest_vector,
            budget_sensitivity=budget_sensitivity,
            pois_per_day_target=target,
            pois_per_day_max=maximum,
            inferred_soft_preferences=[],  # populated by LLM in Sprint 4
            constraints=request.constraints,
            persona_summary=summary,
        )

    # ── Private helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _normalise_interests(weights: InterestWeights) -> dict[str, float]:
        """
        L1-normalise the raw interest weights so they sum to 1.0.

        If all weights are zero (user left defaults at 0), fall back to
        equal weights across all categories so scoring still works.
        """
        raw: dict[str, float] = weights.model_dump()
        total = sum(raw.values())

        if total == 0.0:
            equal = 1.0 / len(raw)
            return {k: equal for k in raw}

        return {k: v / total for k, v in raw.items()}

    @staticmethod
    def _budget_sensitivity(request: TripRequest) -> float:
        """
        Derive budget sensitivity from budget_level, adjusted for constraints.

        Travelling with elderly or children typically means tighter budgets
        and lower tolerance for out-of-range pricing.
        """
        sensitivity = _BASE_SENSITIVITY[request.budget_level]

        if request.constraints.with_elderly or request.constraints.with_children:
            sensitivity = min(1.0, sensitivity + 0.1)

        return round(sensitivity, 2)

    @staticmethod
    def _build_summary(
        request: TripRequest,
        interest_vector: dict[str, float],
    ) -> str:
        """
        Build a human-readable one-sentence persona summary.

        This string is injected into every LLM prompt to give the model
        context about the traveller without repeating the full schema.
        """
        # Pick the top-2 interest categories.
        sorted_interests = sorted(interest_vector.items(), key=lambda x: x[1], reverse=True)
        top_labels = [_CATEGORY_LABELS.get(k, k) for k, _ in sorted_interests[:2]]
        interest_str = " and ".join(top_labels)

        budget_str = {
            BudgetLevel.budget:    "budget-conscious",
            BudgetLevel.mid_range: "mid-range budget",
            BudgetLevel.luxury:    "luxury budget",
        }[request.budget_level]

        pace_str = {
            TravelPace.relaxed:   "relaxed pace",
            TravelPace.moderate:  "moderate pace",
            TravelPace.intensive: "intensive pace",
        }[request.travel_pace]

        extras: list[str] = []
        if request.constraints.with_children:
            extras.append("travelling with children")
        if request.constraints.with_elderly:
            extras.append("travelling with elderly")
        if request.constraints.accessibility_required:
            extras.append("requires wheelchair accessibility")

        base = (
            f"A {budget_str} traveller with strong interest in {interest_str}, "
            f"preferring a {pace_str} over {request.duration_days} day(s) in {request.destination}."
        )

        if extras:
            base += " " + "; ".join(extras).capitalize() + "."

        return base
