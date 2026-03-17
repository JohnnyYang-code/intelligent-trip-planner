"""
Trip Planner — Main Pipeline Orchestrator

Four-stage structured planning pipeline followed by LLM text generation.

  Stage 1  PersonaBuilder   TripRequest → TravelerPersona
  Stage 2  POIScorer        POI candidates × Persona → ScoredPOI list
  Stage 3  DayAllocator     ScoredPOIs → day buckets (weather-aware, greedy)
  Stage 4  RouteOptimizer   Day bucket → ordered ScheduledPOI list (per day)
  LLM      Text generation  Narratives, POI reasons, overview (after Stage 4)

The LLM layer narrates the plan produced by Stages 1-4.
It never makes planning decisions.
"""

import asyncio
import logging
from uuid import uuid4

from app.config.settings import get_settings
from app.core.day_allocator import DayAllocator
from app.core.persona_builder import PersonaBuilder
from app.core.poi_scorer import POIScorer
from app.core.route_optimizer import RouteOptimizer
from app.integrations.maps.maps_factory import create_maps_provider
from app.integrations.poi.poi_factory import create_poi_provider
from app.integrations.weather.weather_factory import create_weather_provider
from app.llm.llm_factory import create_llm_provider
from app.schemas.itinerary import DailyWeather, ItineraryResponse
from app.schemas.poi import ScheduledPOI
from app.schemas.trip_request import TripRequest
from app.services.itinerary_builder import ItineraryBuilder

logger = logging.getLogger(__name__)


class TripPlanner:
    """Orchestrates the full trip-planning pipeline."""

    def __init__(self) -> None:
        settings = get_settings()

        self.persona_builder = PersonaBuilder()
        self.poi_scorer = POIScorer()
        self.day_allocator = DayAllocator()
        self.itinerary_builder = ItineraryBuilder()

        self.poi_provider = create_poi_provider(settings)
        self.maps_provider = create_maps_provider(settings)
        self.weather_provider = create_weather_provider(settings)
        self.llm = create_llm_provider(settings)

        self.route_optimizer = RouteOptimizer(maps_provider=self.maps_provider)

        logger.info(
            "TripPlanner initialised (poi=%s, maps=%s, weather=%s, llm=%s)",
            self.poi_provider.provider_name,
            self.maps_provider.provider_name,
            self.weather_provider.provider_name,
            self.llm.provider_name,
        )

    async def plan(self, request: TripRequest) -> ItineraryResponse:
        """Execute the full pipeline and return a structured itinerary."""
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

        # ── LLM: Soft-preference inference (before scoring, updates persona) ──
        if request.free_text_preferences and request.free_text_preferences.strip():
            soft_prefs = await self.llm.infer_soft_preferences(
                request.free_text_preferences
            )
            persona.inferred_soft_preferences = soft_prefs
            logger.debug("Inferred soft preferences: %s", soft_prefs)

        # ── External data retrieval ───────────────────────────────────────────
        pois = await self.poi_provider.search_pois(request.destination)
        weather = await self.weather_provider.get_forecast(
            request.destination, request.duration_days
        )
        logger.debug("Fetched %d POIs, %d weather days", len(pois), len(weather))

        # ── Stage 2: Personalized POI Scoring (weather-independent) ──────────
        scored_pois = self.poi_scorer.score_all(pois, persona)
        logger.debug(
            "Stage 2 complete: %d POIs scored, top=%.3f",
            len(scored_pois),
            scored_pois[0].total_score if scored_pois else 0.0,
        )

        # ── Stage 3: Day Allocation ───────────────────────────────────────────
        days_scored = self.day_allocator.allocate(scored_pois, persona, weather)
        logger.debug("Stage 3 complete: %d days allocated", len(days_scored))

        # ── Stage 4: Within-Day Route Ordering ───────────────────────────────
        days_scheduled = [
            self.route_optimizer.optimize(
                day_pois,
                weather=weather[i] if i < len(weather) else None,
            )
            for i, day_pois in enumerate(days_scored)
        ]
        logger.debug("Stage 4 complete: routes optimized")

        # ── LLM: Text generation (runs after all planning is done) ────────────
        day_themes = [_day_theme_from_scheduled(day) for day in days_scheduled]
        weather_summary = _weather_summary(weather)
        top_interest = _top_interest(persona)

        overview, day_narratives, poi_reasons = await asyncio.gather(
            self._gen_overview(request, persona, day_themes, weather_summary),
            self._gen_day_narratives(days_scheduled, day_themes, weather),
            self._gen_poi_reasons(days_scheduled, top_interest),
        )

        logger.debug("LLM generation complete")

        # ── Assembly ─────────────────────────────────────────────────────────
        itinerary = self.itinerary_builder.build(
            request_id=str(uuid4()),
            request=request,
            persona=persona,
            days_scheduled=days_scheduled,
            weather_list=weather,
            overview=overview,
            day_narratives=day_narratives,
            poi_reasons=poi_reasons,
        )

        logger.info(
            "Trip plan complete: %d days, %d POIs, ¥%.0f estimated",
            itinerary.duration_days,
            sum(len(d.pois) for d in itinerary.days),
            itinerary.total_estimated_cost_cny,
        )
        return itinerary

    # ── LLM generation helpers ────────────────────────────────────────────────

    async def _gen_overview(self, request, persona, day_themes, weather_summary) -> str:
        try:
            return await self.llm.generate_overview(
                destination=request.destination,
                duration_days=request.duration_days,
                persona_summary=persona.persona_summary,
                day_themes=day_themes,
                weather_summary=weather_summary,
            )
        except Exception as exc:
            logger.warning("Overview generation failed: %s", exc)
            return ""

    async def _gen_day_narratives(
        self,
        days_scheduled: list[list[ScheduledPOI]],
        day_themes: list[str],
        weather: list[DailyWeather],
    ) -> list[str]:
        async def one_day(i: int, day_pois: list[ScheduledPOI]) -> str:
            theme = day_themes[i] if i < len(day_themes) else "Mixed"
            w = weather[i] if i < len(weather) else None
            poi_names = [sp.poi.name for sp in day_pois]
            try:
                return await self.llm.generate_day_narrative(
                    day_number=i + 1,
                    theme=theme,
                    poi_names=poi_names,
                    weather_condition=w.condition if w else "Sunny",
                    travel_advisory=w.travel_advisory if w else "",
                )
            except Exception as exc:
                logger.warning("Day %d narrative failed: %s", i + 1, exc)
                return ""

        return list(await asyncio.gather(
            *[one_day(i, day) for i, day in enumerate(days_scheduled)]
        ))

    async def _gen_poi_reasons(
        self,
        days_scheduled: list[list[ScheduledPOI]],
        top_interest: str,
    ) -> dict[str, str]:
        all_pois = [sp for day in days_scheduled for sp in day]

        async def one_poi(sp: ScheduledPOI) -> tuple[str, str]:
            try:
                reason = await self.llm.generate_poi_reason(
                    poi_name=sp.poi.name,
                    category=sp.poi.category.value,
                    top_interest=top_interest,
                )
                return sp.poi.id, reason
            except Exception as exc:
                logger.warning("POI reason for %s failed: %s", sp.poi.name, exc)
                return sp.poi.id, ""

        pairs = await asyncio.gather(*[one_poi(sp) for sp in all_pois])
        return dict(pairs)


# ── Module-level helpers ───────────────────────────────────────────────────────

def _day_theme_from_scheduled(day_pois: list[ScheduledPOI]) -> str:
    from collections import Counter
    from app.schemas.common import POICategory
    _THEMES = {
        POICategory.history_culture: "History & Culture",
        POICategory.nature_scenery:  "Nature & Scenery",
        POICategory.food_dining:     "Food & Dining",
        POICategory.shopping:        "Shopping",
        POICategory.art_museum:      "Art & Museums",
        POICategory.entertainment:   "Entertainment",
        POICategory.local_life:      "Local Life",
    }
    if not day_pois:
        return "Free Day"
    counter = Counter(sp.poi.category for sp in day_pois)
    return _THEMES.get(counter.most_common(1)[0][0], "Mixed")


def _weather_summary(weather: list[DailyWeather]) -> str:
    if not weather:
        return "pleasant conditions"
    conditions = [w.condition for w in weather]
    dominant = max(set(conditions), key=conditions.count)
    return f"mostly {dominant.lower()} conditions"


def _top_interest(persona) -> str:
    if not persona.interest_vector:
        return "general sightseeing"
    return max(persona.interest_vector, key=persona.interest_vector.__getitem__)
