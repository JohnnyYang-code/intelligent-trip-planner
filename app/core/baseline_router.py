"""
Baseline route ordering strategies for comparison experiments.

Both baselines share the same interface as RouteOptimizer.optimize():
    Input  → list[ScoredPOI]   (one day's POIs, unordered)
    Output → list[ScheduledPOI] (ordered, with suggested times)

Two strategies
--------------
RandomBaseline
    Shuffles POIs in a random order — the weakest possible baseline.
    Any real method should outperform this on distance metrics.

DistanceOnlyBaseline
    Sorts POIs greedily by nearest-neighbour distance, ignoring all
    interest/score information.  This isolates the value of interest
    scoring: if your system beats this, interest-awareness adds value.

Shared utility
--------------
total_distance_km(pois)
    Computes the total Haversine route length for a POI sequence.
    Use this to compare strategies on the same day's POI set.
"""

import random
from math import asin, cos, radians, sin, sqrt
from typing import Literal

from app.schemas.poi import POI, ScheduledPOI, ScoredPOI


# ── Haversine (self-contained, no import from mock_provider) ─────────────────

def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in kilometres between two WGS-84 coordinates."""
    r = 6371.0
    phi1, phi2 = radians(lat1), radians(lat2)
    dphi = radians(lat2 - lat1)
    dlambda = radians(lon2 - lon1)
    a = sin(dphi / 2) ** 2 + cos(phi1) * cos(phi2) * sin(dlambda / 2) ** 2
    return 2 * r * asin(sqrt(a))


# ── Shared metric ─────────────────────────────────────────────────────────────

def total_distance_km(pois: list[POI]) -> float:
    """
    Compute total Haversine route distance for an ordered POI sequence.

    Returns 0.0 for sequences shorter than 2 POIs.
    Use this as the primary metric when comparing baseline vs. your method.

    Example
    -------
    dist_baseline = total_distance_km([sp.poi for sp in baseline_result])
    dist_yours    = total_distance_km([sp.poi for sp in your_result])
    improvement   = (dist_baseline - dist_yours) / dist_baseline * 100
    """
    if len(pois) < 2:
        return 0.0
    return sum(
        _haversine_km(
            pois[i].latitude, pois[i].longitude,
            pois[i + 1].latitude, pois[i + 1].longitude,
        )
        for i in range(len(pois) - 1)
    )


# ── Time helpers (copied from RouteOptimizer to stay self-contained) ──────────

_DEFAULT_START_TIME = "09:00"
_TRANSPORT_BUFFER_H = 0.25   # 15-min fixed buffer between POIs
_WALKING_SPEED_KMH  = 4.0    # used to estimate travel time from distance


def _parse_time(t: str) -> float:
    h, m = map(int, t.split(":"))
    return h + m / 60.0


def _format_time(hours: float) -> str:
    h = int(hours) % 24
    m = round((hours - int(hours)) * 60)
    if m == 60:
        h, m = (h + 1) % 24, 0
    return f"{h:02d}:{m:02d}"


def _assign_times(
    ordered: list[ScoredPOI],
    start_time: str = _DEFAULT_START_TIME,
) -> list[ScheduledPOI]:
    """
    Assign visit_order and suggested_start_time to an ordered POI list.
    Travel time between consecutive POIs is estimated via Haversine / walking speed.
    """
    scheduled: list[ScheduledPOI] = []
    current_hour = _parse_time(start_time)

    for order, sp in enumerate(ordered, start=1):
        scheduled.append(
            ScheduledPOI(
                poi=sp.poi,
                visit_order=order,
                suggested_start_time=_format_time(current_hour),
                suggested_duration_hours=sp.poi.duration_hours,
                recommendation_reason="baseline",
            )
        )
        current_hour += sp.poi.duration_hours + _TRANSPORT_BUFFER_H
        if order < len(ordered):
            next_poi = ordered[order].poi   # order is 1-based; list is 0-based
            dist_km = _haversine_km(
                sp.poi.latitude, sp.poi.longitude,
                next_poi.latitude, next_poi.longitude,
            )
            current_hour += dist_km / _WALKING_SPEED_KMH

    return scheduled


# ── Nearest-neighbour helper (distance-only, no score) ───────────────────────

def _nn_order(pois: list[ScoredPOI]) -> list[ScoredPOI]:
    """Greedy nearest-neighbour starting from the first element."""
    if len(pois) <= 1:
        return list(pois)
    remaining = list(pois)
    ordered = [remaining.pop(0)]
    while remaining:
        last = ordered[-1].poi
        closest = min(
            remaining,
            key=lambda sp: _haversine_km(
                last.latitude, last.longitude,
                sp.poi.latitude, sp.poi.longitude,
            ),
        )
        ordered.append(closest)
        remaining.remove(closest)
    return ordered


# ── Baseline A: Random ────────────────────────────────────────────────────────

class RandomBaseline:
    """
    Orders POIs in a uniformly random sequence.

    Intended use: establish a floor — any reasonably designed method
    should achieve shorter total distance than pure random ordering.

    Parameters
    ----------
    seed : optional int
        Fix the random seed for reproducible experiments.
    """

    def __init__(self, seed: int | None = None) -> None:
        self._rng = random.Random(seed)

    def optimize(
        self,
        day_pois: list[ScoredPOI],
        start_time: str = _DEFAULT_START_TIME,
    ) -> list[ScheduledPOI]:
        if not day_pois:
            return []
        shuffled = list(day_pois)
        self._rng.shuffle(shuffled)
        return _assign_times(shuffled, start_time)


# ── Baseline B: Distance-Only (nearest-neighbour, no interest) ───────────────

class DistanceOnlyBaseline:
    """
    Orders POIs greedily by nearest-neighbour distance, ignoring all
    interest scores, popularity, and budget information.

    Intended use: isolate the marginal value of interest-aware scoring.
    If your system beats this baseline, interest-weighting adds measurable
    route benefit beyond pure geographic proximity.

    Note: this uses the same NN heuristic as RouteOptimizer, but applies
    it to ALL POIs (no meal/sightseeing split) and ignores scores entirely.
    """

    def optimize(
        self,
        day_pois: list[ScoredPOI],
        start_time: str = _DEFAULT_START_TIME,
    ) -> list[ScheduledPOI]:
        if not day_pois:
            return []
        ordered = _nn_order(day_pois)
        return _assign_times(ordered, start_time)


# ── Comparison helper ─────────────────────────────────────────────────────────

StrategyName = Literal["random", "distance_only"]


def compare(
    day_pois: list[ScoredPOI],
    your_result: list[ScheduledPOI],
    strategies: list[StrategyName] | None = None,
    seed: int | None = 42,
) -> dict:
    """
    Run one or more baselines on the same POI set and compare distances.

    Parameters
    ----------
    day_pois    : The same list passed to your RouteOptimizer.
    your_result : Output of your RouteOptimizer.optimize().
    strategies  : Subset to run; defaults to all baselines.
    seed        : Random seed for RandomBaseline reproducibility.

    Returns
    -------
    dict with keys:
        "your_distance_km"         – total km for your method
        "random_distance_km"       – total km for random (if selected)
        "distance_only_distance_km"– total km for distance-only (if selected)
        "vs_random_pct"            – % reduction vs random (positive = better)
        "vs_distance_only_pct"     – % reduction vs distance-only

    Example
    -------
    result = compare(day_pois, your_scheduled_pois)
    print(result)
    # {'your_distance_km': 8.4, 'random_distance_km': 14.1,
    #  'distance_only_distance_km': 7.9, 'vs_random_pct': 40.4,
    #  'vs_distance_only_pct': -6.3}
    """
    if strategies is None:
        strategies = ["random", "distance_only"]

    your_km = total_distance_km([sp.poi for sp in your_result])
    out: dict = {"your_distance_km": round(your_km, 3)}

    if "random" in strategies:
        rand_result = RandomBaseline(seed=seed).optimize(day_pois)
        rand_km = total_distance_km([sp.poi for sp in rand_result])
        out["random_distance_km"] = round(rand_km, 3)
        out["vs_random_pct"] = (
            round((rand_km - your_km) / rand_km * 100, 1) if rand_km else None
        )

    if "distance_only" in strategies:
        dist_result = DistanceOnlyBaseline().optimize(day_pois)
        dist_km = total_distance_km([sp.poi for sp in dist_result])
        out["distance_only_distance_km"] = round(dist_km, 3)
        out["vs_distance_only_pct"] = (
            round((dist_km - your_km) / dist_km * 100, 1) if dist_km else None
        )

    return out
