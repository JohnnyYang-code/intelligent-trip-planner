"""
Stage 4: Within-Day Route Ordering

Orders POIs within a single travel day and assigns suggested visit times.

Strategy (MVP)
--------------
1. Separate food_dining POIs from sightseeing POIs.
2. Apply nearest-neighbour ordering to sightseeing POIs to minimise
   unnecessary backtracking (Haversine straight-line approximation).
3. Insert meal POIs around the midpoint of the sightseeing sequence so
   they fall naturally near lunch and dinner slots.
4. Accumulate start times from the day's start hour, adding each POI's
   duration plus a transport buffer and estimated travel time.
"""

import logging
from typing import Optional

from app.config.settings import get_settings
from app.integrations.maps.base import BaseMapsProvider, Coordinates
from app.integrations.maps.mock_provider import haversine_km
from app.schemas.common import POICategory
from app.schemas.itinerary import DailyWeather
from app.schemas.poi import POI, ScheduledPOI, ScoredPOI

logger = logging.getLogger(__name__)

_DEFAULT_START_TIME = "09:00"
# Maximum travel time per leg when using Haversine fallback.
# Prevents time overflow when two POIs are geographically far apart.
_MAX_TRAVEL_HOURS_FALLBACK = 1.5


class RouteOptimizer:
    """
    Produces an ordered list of ScheduledPOI for a single travel day.

    When a real MapsProvider is injected, travel time is computed from
    actual driving/transit data.  Without one, Haversine straight-line
    distance is used with a 1.5-hour cap per leg.
    """

    def __init__(self, maps_provider: Optional[BaseMapsProvider] = None) -> None:
        settings = get_settings()
        self._buffer_hours: float = settings.transport_buffer_minutes / 60.0
        self._maps: Optional[BaseMapsProvider] = maps_provider

    def optimize(
        self,
        day_pois: list[ScoredPOI],
        weather: DailyWeather | None = None,   # reserved for future use
        start_time: str = _DEFAULT_START_TIME,
    ) -> list[ScheduledPOI]:
        """
        Order the day's POIs and assign suggested start times.

        Parameters
        ----------
        day_pois    : Unordered list of ScoredPOIs for this day.
        weather     : Optional weather data (not yet used in routing logic).
        start_time  : Day start as "HH:MM" (default "09:00").

        Returns
        -------
        List of ScheduledPOI in visit order with times assigned.
        """
        if not day_pois:
            return []

        # 1. Split into meals and sightseeing POIs.
        meals: list[ScoredPOI] = [
            sp for sp in day_pois if sp.poi.category == POICategory.food_dining
        ]
        sights: list[ScoredPOI] = [
            sp for sp in day_pois if sp.poi.category != POICategory.food_dining
        ]

        # 2. Nearest-neighbour ordering for sightseeing POIs.
        sights_ordered = _nearest_neighbour(sights)

        # 3. Interleave meals: first meal at midpoint, extras at end.
        sequence = _interleave_meals(sights_ordered, meals)

        # 4. Assign visit orders and start times.
        scheduled: list[ScheduledPOI] = []
        current_hour = _parse_time(start_time)

        for order, sp in enumerate(sequence, start=1):
            scheduled.append(
                ScheduledPOI(
                    poi=sp.poi,
                    visit_order=order,
                    suggested_start_time=_format_time(current_hour),
                    suggested_duration_hours=sp.poi.duration_hours,
                    recommendation_reason="",   # filled by LLM in Sprint 4
                )
            )

            # Advance clock: visit duration + transport buffer.
            current_hour += sp.poi.duration_hours + self._buffer_hours

            # Add estimated travel time to the next POI.
            if order < len(sequence):
                next_poi = sequence[order]   # sequence is 0-based; order is 1-based
                current_hour += _travel_hours(sp.poi, next_poi.poi, self._maps)

        logger.debug(
            "RouteOptimizer: ordered %d POIs, day ends ~%s",
            len(scheduled),
            _format_time(current_hour),
        )
        return scheduled


# ── Module-level helpers ───────────────────────────────────────────────────────

def _nearest_neighbour(pois: list[ScoredPOI]) -> list[ScoredPOI]:
    """
    Greedy nearest-neighbour traversal starting from the first element.

    Uses Haversine straight-line distance for ordering (good enough for
    sorting; actual travel times are applied during time assignment).
    """
    if len(pois) <= 1:
        return list(pois)

    remaining = list(pois)
    ordered = [remaining.pop(0)]

    while remaining:
        last_poi = ordered[-1].poi
        closest = min(
            remaining,
            key=lambda sp: haversine_km(
                last_poi.latitude, last_poi.longitude,
                sp.poi.latitude, sp.poi.longitude,
            ),
        )
        ordered.append(closest)
        remaining.remove(closest)

    return ordered


def _interleave_meals(
    sights: list[ScoredPOI],
    meals: list[ScoredPOI],
) -> list[ScoredPOI]:
    """
    Distribute meal POIs across breakfast / lunch / dinner slots.

    Slot assignment by meal count (day starts at 09:00):
      1 meal  → lunch only  (midpoint of sights, ~12:00)
      2 meals → lunch + dinner  (midpoint + end, ~12:00 / ~18:00)
      3 meals → breakfast + lunch + dinner  (start + midpoint + end)

    With typical sight durations (1.5–2.5 h) and transport buffers, this
    places meals inside realistic windows without any time arithmetic.
    """
    if not meals:
        return list(sights)
    if not sights:
        return list(meals)

    mid = max(1, len(sights) // 2)
    before = sights[:mid]
    after  = sights[mid:]

    if len(meals) == 1:
        # Lunch only
        return list(before) + [meals[0]] + list(after)
    if len(meals) == 2:
        # Lunch + dinner
        return list(before) + [meals[0]] + list(after) + [meals[1]]
    # 3+ meals: breakfast + lunch + dinner (upstream cap keeps this ≤ 3)
    return [meals[0]] + list(before) + [meals[1]] + list(after) + list(meals[2:])


def _travel_hours(
    origin: POI,
    destination: POI,
    maps: Optional[BaseMapsProvider] = None,
) -> float:
    """
    Estimate travel time in hours between two POIs.

    If a real MapsProvider is available, uses driving distance from the API.
    Otherwise falls back to Haversine straight-line distance, capped at
    _MAX_TRAVEL_HOURS_FALLBACK to prevent time overflow for distant POIs.
    """
    if maps is not None and maps.is_available():
        try:
            result = maps.get_distance(
                Coordinates(origin.latitude, origin.longitude),
                Coordinates(destination.latitude, destination.longitude),
            )
            return result.duration_minutes / 60.0
        except Exception:
            pass  # fall through to Haversine

    dist_km = haversine_km(
        origin.latitude, origin.longitude,
        destination.latitude, destination.longitude,
    )
    estimated = dist_km / 4.0   # walking speed as conservative fallback
    return min(estimated, _MAX_TRAVEL_HOURS_FALLBACK)


def _parse_time(time_str: str) -> float:
    """Convert 'HH:MM' to decimal hours (e.g. '09:30' → 9.5)."""
    h, m = map(int, time_str.split(":"))
    return h + m / 60.0


def _format_time(hours: float) -> str:
    """Convert decimal hours to 'HH:MM' (e.g. 9.5 → '09:30')."""
    h = int(hours) % 24
    m = round((hours - int(hours)) * 60)
    if m == 60:
        h = (h + 1) % 24
        m = 0
    return f"{h:02d}:{m:02d}"
