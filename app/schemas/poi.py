from typing import Optional

from pydantic import BaseModel, Field

from app.schemas.common import BudgetLevel, POICategory


class POI(BaseModel):
    """A single point of interest."""

    id: str
    name: str
    name_en: Optional[str] = None
    destination: str                        # normalised city key, e.g. "beijing"

    category: POICategory

    # ── Geography ─────────────────────────────────────────────────────────────
    latitude: float
    longitude: float
    district: str                           # used for geographic clustering

    # ── Quality attributes (0–10 scale) ──────────────────────────────────────
    popularity_score: float = Field(..., ge=0.0, le=10.0)
    quality_score: float = Field(..., ge=0.0, le=10.0)

    # ── Budget ────────────────────────────────────────────────────────────────
    avg_cost_cny: float = Field(..., ge=0.0)
    budget_tier: BudgetLevel

    # ── Logistics ─────────────────────────────────────────────────────────────
    duration_hours: float = Field(..., gt=0.0)   # recommended visit duration
    opening_hours: Optional[str] = None

    # ── Classification flags ──────────────────────────────────────────────────
    indoor: bool = False                    # True → preferred on rainy days
    child_friendly: bool = True
    accessible: bool = True                 # wheelchair accessible

    # ── Descriptive content (used in LLM prompts) ────────────────────────────
    tags: list[str] = Field(default_factory=list)
    description: str = ""
    highlights: list[str] = Field(default_factory=list)


class ScoreBreakdown(BaseModel):
    """Per-component breakdown of a POI's composite score."""

    interest_score: float       # weighted interest match (0–1)
    popularity_score: float     # normalised popularity (0–1)
    budget_score: float         # budget fitness (0–1)
    constraint_multiplier: float  # 0.0 if violated, 1.0 if fine


class ScoredPOI(BaseModel):
    """POI after scoring — used by DayAllocator."""

    poi: POI
    total_score: float
    score_breakdown: ScoreBreakdown


class ScheduledPOI(BaseModel):
    """POI placed into a specific day slot with a suggested time."""

    poi: POI
    visit_order: int
    suggested_start_time: str           # e.g. "09:00"
    suggested_duration_hours: float
    recommendation_reason: str = ""     # filled in by LLM (Sprint 4)
