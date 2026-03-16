from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.schemas.poi import ScheduledPOI


class DailyWeather(BaseModel):
    """Weather forecast for a single travel day."""

    date: str                           # "2026-03-20"
    condition: str                      # "Sunny", "Cloudy", "Rainy", "Snowy"
    temp_high_c: float
    temp_low_c: float
    humidity_pct: int = Field(..., ge=0, le=100)
    precipitation_mm: float = 0.0
    wind_speed_kmh: float = 0.0
    uv_index: int = Field(default=3, ge=0, le=11)
    travel_advisory: str = ""           # e.g. "Bring an umbrella"


class DayPlan(BaseModel):
    """The full plan for a single travel day."""

    day_number: int                     # 1-based
    date_label: str                     # e.g. "Day 1"
    theme: str = ""                     # e.g. "Imperial History"

    pois: list[ScheduledPOI]

    weather: Optional[DailyWeather] = None

    # ── LLM-generated content (filled in Sprint 4; empty string for MVP) ─────
    narrative: str = ""
    tips: list[str] = Field(default_factory=list)


class ItineraryResponse(BaseModel):
    """Top-level response returned by POST /api/v1/trips/plan."""

    request_id: str
    destination: str
    duration_days: int

    # ── LLM-generated fields (empty in mock mode) ────────────────────────────
    overview: str = ""

    # Human-readable summary of the persona used for planning
    persona_summary: str

    days: list[DayPlan]

    total_estimated_cost_cny: float
    generated_at: datetime

    # Notes from the planner, e.g. "Skipped X due to budget constraint"
    planning_notes: list[str] = Field(default_factory=list)
