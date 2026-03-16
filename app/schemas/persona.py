from pydantic import BaseModel, Field

from app.schemas.common import BudgetLevel, TravelPace
from app.schemas.trip_request import TripConstraints


class TravelerPersona(BaseModel):
    """
    Structured traveler profile derived from TripRequest by PersonaBuilder.
    This is the central input for all downstream planning modules.
    """

    # ── Trip basics ──────────────────────────────────────────────────────────
    destination: str
    duration_days: int
    budget_level: BudgetLevel
    travel_pace: TravelPace

    # ── Normalised interest vector ────────────────────────────────────────────
    # Keys match POICategory values. Values are L1-normalised (sum ≈ 1.0).
    interest_vector: dict[str, float]

    # ── Derived scalars ───────────────────────────────────────────────────────
    # budget=0.9  mid_range=0.5  luxury=0.1
    # Higher sensitivity → budget-mismatch penalises score more strongly.
    budget_sensitivity: float = Field(..., ge=0.0, le=1.0)

    # Daily POI capacity derived from travel_pace.
    pois_per_day_target: int   # aim for this many per day
    pois_per_day_max: int       # hard upper limit

    # ── LLM-inferred soft preferences (populated in Sprint 4) ─────────────────
    # e.g. ["prefer_less_crowded", "like_architecture"]
    inferred_soft_preferences: list[str] = Field(default_factory=list)

    # ── Hard constraints (passed through from TripRequest) ────────────────────
    constraints: TripConstraints

    # ── Human-readable summary injected into every LLM prompt ────────────────
    persona_summary: str = ""
