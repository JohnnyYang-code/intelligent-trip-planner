"""
Natural Language Trip Request Schemas — Sprint 5.6

Two models:
  NaturalLanguageTripRequest  API input  (raw free text only)
  ParsedTripInput             Intermediate structure extracted by LLM
                              (all fields optional; defaults applied by NLInputParser)
"""

from typing import Optional

from pydantic import BaseModel, Field

from app.schemas.common import BudgetLevel, POICategory, TravelPace


class NaturalLanguageTripRequest(BaseModel):
    """API body for POST /api/v1/trips/plan-from-text."""

    raw_text: str = Field(
        ...,
        min_length=10,
        max_length=1000,
        description=(
            "Free-form trip description in English or Chinese. "
            "e.g. 'I'd like to spend three days in Brisbane focusing on food.'"
        ),
    )


class ParsedTripInput(BaseModel):
    """
    Structured fields extracted from raw_text by the LLM.

    Every field is Optional because the LLM may not be able to extract it.
    Safe defaults are applied by NLInputParser, not here.
    """

    destination: Optional[str] = None
    duration_days: Optional[int] = Field(default=None, ge=1, le=14)
    start_date: Optional[str] = None    # ISO 8601, e.g. "2026-03-20"
    end_date: Optional[str] = None      # ISO 8601, e.g. "2026-03-23"
    budget_level: Optional[BudgetLevel] = None
    travel_pace: Optional[TravelPace] = None
    preferred_categories: Optional[list[POICategory]] = None
    free_text_preferences: Optional[str] = None
