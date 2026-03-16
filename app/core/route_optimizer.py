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

from app.config.settings import get_settings
from app.integrations.maps.mock_provider import haversine_km
from app.schemas.common import POICategory
from app.schemas.itinerary import DailyWeather
from app.schemas.poi import POI, ScheduledPOI, ScoredPOI

logger = logging.getLogger(__name__)

_DEFAULT_START_TIME = "09:00"


class RouteOptimizer:
    """
    Produces an ordered list of ScheduledPOI for a single travel day.

    ``recommendation_reason`` on each ScheduledPOI is left empty; the LLM
    layer (Sprint 4) fills it in.
    """

    def __init__(self) -> None:
        settings = get_settings()
        self._buffer_hours: float = settings.transport_buffer_minutes / 60.0

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
                current_hour += _travel_hours(sp.poi, next_poi.poi)

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

    Returns the input list reordered to minimise total Haversine distance.
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
    Insert meal POIs into the sightseeing sequence.

    The first meal is inserted at the midpoint of the sightseeing list
    (approximating a lunch break). Any additional meals are appended at
    the end (approximating dinner).
    """
    if not meals:
        return list(sights)

    mid = max(1, len(sights) // 2)
    sequence: list[ScoredPOI] = []
    sequence.extend(sights[:mid])
    sequence.append(meals[0])        # first meal ≈ lunch
    sequence.extend(sights[mid:])
    sequence.extend(meals[1:])       # remaining meals ≈ dinner / extra
    return sequence


def _travel_hours(origin: POI, destination: POI) -> float:
    """Estimate walking travel time in hours between two POIs."""
    dist_km = haversine_km(
        origin.latitude, origin.longitude,
        destination.latitude, destination.longitude,
    )
    walking_speed_kmh = 4.0
    return dist_km / walking_speed_kmh


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
