"""
Stage 3: Day Allocation

Distributes scored POIs across trip days using a greedy strategy with two
lightweight day-specific adjustments applied for selection decisions only:

  - Weather adjustment : bad-weather days favour indoor POIs.
  - District bonus     : prefer POIs geographically close to those already
                         chosen for the same day.

ScoredPOI objects are never mutated; the adjustments exist only as ephemeral
float values computed during the selection loop.
"""

import logging
from collections import Counter

from app.config.settings import get_settings
from app.schemas.itinerary import DailyWeather
from app.schemas.persona import TravelerPersona
from app.schemas.poi import ScoredPOI

logger = logging.getLogger(__name__)

# Weather conditions considered bad for outdoor sightseeing.
_BAD_WEATHER: frozenset[str] = frozenset({"Rainy", "Foggy", "Snowy"})

# Multipliers applied to the base score when computing effective score.
_INDOOR_WEATHER_BONUS: float = 1.15    # indoor POI on a bad-weather day
_OUTDOOR_WEATHER_PENALTY: float = 0.75  # outdoor POI on a bad-weather day
_DISTRICT_BONUS: float = 1.10           # same district as today's dominant area


class DayAllocator:
    """
    Distributes scored POIs across the trip's days.

    Algorithm
    ---------
    1. Drop POIs whose total_score == 0.0 (hard constraint violations).
    2. For each day d (0 .. duration_days - 1):
       a. Look up today's weather if available.
       b. Compute a temporary *effective score* for each remaining candidate:
              effective = base_score × weather_adj × district_adj
          These values are local to the selection loop and never stored.
       c. Greedily pick the highest-effective-score candidate, repeating
          until pois_per_day_max or daily_hours_budget is exhausted.
       d. Remove selected POIs from the shared candidate pool.
    3. Return list[list[ScoredPOI]] — one inner list per day.
    """

    def __init__(self) -> None:
        self._daily_hours_budget: float = get_settings().daily_hours_budget

    def allocate(
        self,
        scored_pois: list[ScoredPOI],
        persona: TravelerPersona,
        weather_list: list[DailyWeather] | None = None,
    ) -> list[list[ScoredPOI]]:
        """
        Return a list of length ``persona.duration_days``.

        Each element is the (unordered) list of ScoredPOIs for that day.
        ``route_optimizer`` is responsible for determining the within-day
        sequence and computing visit times.
        """
        candidates: list[ScoredPOI] = [sp for sp in scored_pois if sp.total_score > 0.0]
        skipped = len(scored_pois) - len(candidates)
        if skipped:
            logger.info("DayAllocator: filtered out %d zero-score POIs", skipped)

        result: list[list[ScoredPOI]] = []

        for day_idx in range(persona.duration_days):
            weather: DailyWeather | None = (
                weather_list[day_idx]
                if weather_list and day_idx < len(weather_list)
                else None
            )

            day_selection, candidates = self._fill_day(
                candidates=candidates,
                max_pois=persona.pois_per_day_max,
                hours_budget=self._daily_hours_budget,
                weather=weather,
            )
            result.append(day_selection)

            logger.debug(
                "Day %d: %d POIs selected (%.1fh), weather=%s",
                day_idx + 1,
                len(day_selection),
                sum(sp.poi.duration_hours for sp in day_selection),
                weather.condition if weather else "N/A",
            )

        return result

    # ── Private helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _fill_day(
        candidates: list[ScoredPOI],
        max_pois: int,
        hours_budget: float,
        weather: DailyWeather | None,
    ) -> tuple[list[ScoredPOI], list[ScoredPOI]]:
        """
        Select POIs for one day without mutating any ScoredPOI.

        Returns
        -------
        (day_selection, remaining_candidates)
        """
        remaining: list[ScoredPOI] = list(candidates)
        selected: list[ScoredPOI] = []
        hours_used: float = 0.0

        while remaining and len(selected) < max_pois:
            if hours_used >= hours_budget:
                break

            dominant_district = _dominant_district(selected)

            best = max(remaining, key=lambda sp: _effective_score(
                sp, weather, dominant_district
            ))

            # Respect time budget; allow a small (0.5 h) overrun so that
            # a short final POI is not unfairly excluded.
            if hours_used + best.poi.duration_hours > hours_budget + 0.5:
                break

            selected.append(best)
            hours_used += best.poi.duration_hours
            remaining = [r for r in remaining if r.poi.id != best.poi.id]

        return selected, remaining


# ── Module-level helpers ───────────────────────────────────────────────────────

def _effective_score(
    sp: ScoredPOI,
    weather: DailyWeather | None,
    dominant_district: str | None,
) -> float:
    """
    Compute a temporary effective score for allocation decisions only.

    This value is never stored; ScoredPOI.total_score is left unchanged.
    """
    score = sp.total_score

    if weather and weather.condition in _BAD_WEATHER:
        score *= _INDOOR_WEATHER_BONUS if sp.poi.indoor else _OUTDOOR_WEATHER_PENALTY

    if dominant_district and sp.poi.district == dominant_district:
        score *= _DISTRICT_BONUS

    return score


def _dominant_district(pois: list[ScoredPOI]) -> str | None:
    """Return the most frequent district among selected POIs, or None."""
    if not pois:
        return None
    counter = Counter(sp.poi.district for sp in pois)
    return counter.most_common(1)[0][0]
