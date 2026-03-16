"""
Trip Planner — Main Pipeline Orchestrator

This module wires together the four-stage planning pipeline and all external
providers into a single ``plan()`` entry point.

Four-stage pipeline
-------------------
  Stage 1  PersonaBuilder   TripRequest → TravelerPersona
  Stage 2  POIScorer        POI candidates × Persona → ScoredPOI list
  Stage 3  DayAllocator     ScoredPOIs → day buckets (weather-aware, greedy)
  Stage 4  RouteOptimizer   Day bucket → ordered ScheduledPOI list (per day)

The LLM layer (Sprint 4) will be inserted *after* Stage 4; for now all
narrative fields remain empty strings.
"""

import logging
from uuid import uuid4

from app.config.settings import get_settings
from app.core.day_allocator import DayAllocator
from app.core.persona_builder import PersonaBuilder
from app.core.poi_scorer import POIScorer
from app.core.route_optimizer import RouteOptimizer
from app.integrations.poi.poi_factory import create_poi_provider
from app.integrations.weather.weather_factory import create_weather_provider
from app.schemas.itinerary import ItineraryResponse
from app.schemas.trip_request import TripRequest
from app.services.itinerary_builder import ItineraryBuilder

logger = logging.getLogger(__name__)


class TripPlanner:
    """
    Orchestrates the full trip-planning pipeline.

    All dependencies are injected via the constructor so they can be
    swapped easily in tests or when real API keys become available.
    """

    def __init__(self) -> None:
        settings = get_settings()

        # Core planning stages (pure Python, no I/O)
        self.persona_builder = PersonaBuilder()
        self.poi_scorer = POIScorer()
        self.day_allocator = DayAllocator()
        self.route_optimizer = RouteOptimizer()
        self.itinerary_builder = ItineraryBuilder()

        # External data providers (mock by default; swap via .env)
        self.poi_provider = create_poi_provider(settings)
        self.weather_provider = create_weather_provider(settings)

        logger.info(
            "TripPlanner initialised (poi=%s, weather=%s)",
            self.poi_provider.provider_name,
            self.weather_provider.provider_name,
        )

    async def plan(self, request: TripRequest) -> ItineraryResponse:
        """
        Execute the full four-stage planning pipeline.

        Parameters
        ----------
        request : Validated TripRequest from the API layer.

        Returns
        -------
        ItineraryResponse with all days scheduled and times assigned.
        LLM-generated narrative fields are empty in Sprint 2.
        """
        logger.info(
            "Planning trip: destination=%s, days=%d, pace=%s, budget=%s",
            request.destination,
            request.duration_days,
            request.travel_pace.value,
            request.budget_level.value,
        )

        # ── Stage 1: Traveler Persona Construction ────────────────────────────
        persona = self.persona_builder.build(request)
        logger.debug("Stage 1 complete: %s", persona.persona_summary)

        # ── External data retrieval (all mock in Sprint 2) ────────────────────
        pois = await self.poi_provider.search_pois(request.destination)
        weather = await self.weather_provider.get_forecast(
            request.destination, request.duration_days
        )
        logger.debug(
            "Data fetched: %d POIs, %d weather days", len(pois), len(weather)
        )

        # ── Stage 2: Personalized POI Scoring (weather-independent) ──────────
        scored_pois = self.poi_scorer.score_all(pois, persona)
        logger.debug(
            "Stage 2 complete: scored %d POIs, top=%.3f",
            len(scored_pois),
            scored_pois[0].total_score if scored_pois else 0.0,
        )

        # ── Stage 3: Day Allocation (day-specific weather applied here) ───────
        days_scored = self.day_allocator.allocate(scored_pois, persona, weather)
        logger.debug(
            "Stage 3 complete: %d days allocated",
            len(days_scored),
        )

        # ── Stage 4: Within-Day Route Ordering ───────────────────────────────
        days_scheduled = [
            self.route_optimizer.optimize(
                day_pois,
                weather=weather[i] if i < len(weather) else None,
            )
            for i, day_pois in enumerate(days_scored)
        ]
        logger.debug("Stage 4 complete: routes optimized for all days")

        # ── Assembly ─────────────────────────────────────────────────────────
        # LLM narrative generation will be inserted here in Sprint 4.
        itinerary = self.itinerary_builder.build(
            request_id=str(uuid4()),
            request=request,
            persona=persona,
            days_scheduled=days_scheduled,
            weather_list=weather,
        )

        logger.info(
            "Trip plan complete: %d days, %d total POIs, ¥%.0f estimated",
            itinerary.duration_days,
            sum(len(d.pois) for d in itinerary.days),
            itinerary.total_estimated_cost_cny,
        )
        return itinerary
