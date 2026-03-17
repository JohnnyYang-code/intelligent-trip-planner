from typing import Optional

from pydantic import BaseModel, Field

from app.schemas.common import BudgetLevel, POICategory, TravelPace


class InterestWeights(BaseModel):
    """
    Raw interest scores provided by the user.
    Values are 0.0–1.0 and will be L1-normalised inside PersonaBuilder.
    """

    history_culture: float = Field(default=0.5, ge=0.0, le=1.0)
    nature_scenery: float = Field(default=0.5, ge=0.0, le=1.0)
    food_dining: float = Field(default=0.5, ge=0.0, le=1.0)
    shopping: float = Field(default=0.3, ge=0.0, le=1.0)
    art_museum: float = Field(default=0.4, ge=0.0, le=1.0)
    entertainment: float = Field(default=0.4, ge=0.0, le=1.0)
    local_life: float = Field(default=0.5, ge=0.0, le=1.0)


class TripConstraints(BaseModel):
    """Hard constraints applied during POI filtering and scoring."""

    avoid_categories: list[POICategory] = Field(default_factory=list)
    accessibility_required: bool = False   # must be wheelchair-accessible
    with_children: bool = False
    with_elderly: bool = False
    max_walking_km_per_day: float = Field(default=5.0, ge=0.5, le=20.0)


class TripRequest(BaseModel):
    """Top-level user request passed to the planning pipeline."""

    destination: str = Field(..., description="City name, e.g. 'beijing' or '北京'")
    duration_days: int = Field(..., ge=1, le=14, description="Number of travel days")
    budget_level: BudgetLevel = BudgetLevel.mid_range
    travel_pace: TravelPace = TravelPace.moderate

    interests: InterestWeights = Field(default_factory=InterestWeights)

    # Simplified category-based preference input (Sprint 5.5).
    # When provided, this takes priority over `interests` and is automatically
    # converted to an interest vector inside PersonaBuilder.
    # Fewer selections = more focused profile; more = broader profile.
    preferred_categories: Optional[list[POICategory]] = Field(
        default=None,
        min_length=1,
        max_length=7,
        description=(
            "1–7 favourite POI categories. "
            "Fewer selections = more focused profile; more selections = broader profile. "
            "When set, takes priority over interests."
        ),
    )

    # Free-text field parsed by the LLM (Sprint 4).
    # Ignored by the structured pipeline; stored for future use.
    free_text_preferences: Optional[str] = Field(
        default=None,
        description="e.g. 'I love ancient architecture but hate crowds' or '我喜欢古建筑'",
    )

    constraints: TripConstraints = Field(default_factory=TripConstraints)
