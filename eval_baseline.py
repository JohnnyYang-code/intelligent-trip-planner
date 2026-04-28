"""
Baseline Comparison Script
Runs the real planning pipeline (Stages 1–3) then compares three route ordering
strategies on the same allocated POI sets:
  - Your method    : RouteOptimizer (interest-scored + nearest-neighbour + meal split)
  - Random         : RandomBaseline (shuffled)
  - Distance-only  : DistanceOnlyBaseline (nearest-neighbour, ignores scores)

Usage: python eval_baseline.py
Output: baseline_comparison.csv  +  console table
"""

import asyncio
import csv
import sys
from statistics import mean

# ── Bootstrap Django-style settings before any app imports ────────────────────
import os
os.environ.setdefault("ENV_FILE", ".env")

from app.config.settings import get_settings
from app.core.baseline_router import (
    DistanceOnlyBaseline,
    RandomBaseline,
    total_distance_km,
)
from app.core.day_allocator import DayAllocator
from app.core.persona_builder import PersonaBuilder
from app.core.poi_scorer import POIScorer
from app.core.route_optimizer import RouteOptimizer
from app.integrations.maps.maps_factory import create_maps_provider
from app.integrations.poi.poi_factory import create_poi_provider
from app.integrations.weather.weather_factory import create_weather_provider
from app.schemas.trip_request import InterestWeights, TripRequest
from app.schemas.common import BudgetLevel, TravelPace

# ── Test cases ────────────────────────────────────────────────────────────────

TEST_CASES = [
    {
        "label": "Beijing / 3d / moderate",
        "request": TripRequest(
            destination="beijing",
            duration_days=3,
            travel_pace=TravelPace.moderate,
            budget_level=BudgetLevel.mid_range,
            interests=InterestWeights(history_culture=0.9, art_museum=0.7, food_dining=0.5),
        ),
    },
    {
        "label": "Shanghai / 2d / intensive",
        "request": TripRequest(
            destination="shanghai",
            duration_days=2,
            travel_pace=TravelPace.intensive,
            budget_level=BudgetLevel.luxury,
            interests=InterestWeights(shopping=0.9, food_dining=0.8, local_life=0.6),
        ),
    },
    {
        "label": "Chengdu / 2d / relaxed",
        "request": TripRequest(
            destination="chengdu",
            duration_days=2,
            travel_pace=TravelPace.relaxed,
            budget_level=BudgetLevel.budget,
            interests=InterestWeights(nature_scenery=0.9, food_dining=0.8, local_life=0.7),
        ),
    },
]

CSV_FIELDS = [
    "test_case", "day",
    "poi_count",
    "your_km", "random_km", "distance_only_km",
    "vs_random_pct", "vs_distance_only_pct",
]


async def run_stages_1_to_3(request: TripRequest):
    """Run pipeline stages 1–3 and return per-day ScoredPOI lists."""
    settings = get_settings()
    poi_provider     = create_poi_provider(settings)
    maps_provider    = create_maps_provider(settings)
    weather_provider = create_weather_provider(settings)

    persona     = PersonaBuilder().build(request)
    pois        = await poi_provider.search_pois(request.destination)
    weather     = await weather_provider.get_forecast(request.destination, request.duration_days)
    scored_pois = POIScorer().score_all(pois, persona)
    days_scored = DayAllocator().allocate(scored_pois, persona, weather)

    return days_scored, maps_provider, weather


def compare_strategies(day_pois, maps_provider, weather_day, seed=42):
    """Return distance (km) for all three strategies on one day's POI list."""
    your_result   = RouteOptimizer(maps_provider=maps_provider).optimize(day_pois, weather=weather_day)
    random_result = RandomBaseline(seed=seed).optimize(day_pois)
    dist_result   = DistanceOnlyBaseline().optimize(day_pois)

    your_km  = total_distance_km([sp.poi for sp in your_result])
    rand_km  = total_distance_km([sp.poi for sp in random_result])
    dist_km  = total_distance_km([sp.poi for sp in dist_result])

    return your_km, rand_km, dist_km


def pct(baseline_km, your_km):
    """Positive = your method is shorter (better). Negative = baseline is shorter."""
    if baseline_km == 0:
        return None
    return round((baseline_km - your_km) / baseline_km * 100, 1)


async def main():
    all_rows = []

    for tc in TEST_CASES:
        print(f"\nRunning: {tc['label']} ...")
        days_scored, maps_provider, weather = await run_stages_1_to_3(tc["request"])

        for i, day_pois in enumerate(days_scored):
            if not day_pois:
                continue
            weather_day = weather[i] if i < len(weather) else None
            your_km, rand_km, dist_km = compare_strategies(day_pois, maps_provider, weather_day)

            row = {
                "test_case":           tc["label"],
                "day":                 i + 1,
                "poi_count":           len(day_pois),
                "your_km":             round(your_km, 3),
                "random_km":           round(rand_km, 3),
                "distance_only_km":    round(dist_km, 3),
                "vs_random_pct":       pct(rand_km, your_km),
                "vs_distance_only_pct": pct(dist_km, your_km),
            }
            all_rows.append(row)

    # ── Print table ───────────────────────────────────────────────────────────
    print(f"\n{'─'*80}")
    print(f"{'Test Case':<30} {'Day':>3}  {'POIs':>4}  "
          f"{'Yours':>7}  {'Random':>7}  {'DistOnly':>8}  "
          f"{'vs Rnd':>7}  {'vs Dist':>7}")
    print(f"{'─'*80}")
    for r in all_rows:
        vs_r = f"{r['vs_random_pct']:+.1f}%" if r["vs_random_pct"] is not None else "  n/a"
        vs_d = f"{r['vs_distance_only_pct']:+.1f}%" if r["vs_distance_only_pct"] is not None else "  n/a"
        print(
            f"{r['test_case']:<30} {r['day']:>3}  {r['poi_count']:>4}  "
            f"{r['your_km']:>6.2f}km  {r['random_km']:>6.2f}km  "
            f"{r['distance_only_km']:>7.2f}km  "
            f"{vs_r:>7}  {vs_d:>7}"
        )

    # ── Aggregate summary ─────────────────────────────────────────────────────
    vs_rand_vals = [r["vs_random_pct"] for r in all_rows if r["vs_random_pct"] is not None]
    vs_dist_vals = [r["vs_distance_only_pct"] for r in all_rows if r["vs_distance_only_pct"] is not None]
    print(f"{'─'*80}")
    print(f"Average vs Random       : {mean(vs_rand_vals):+.1f}%  "
          f"({'shorter' if mean(vs_rand_vals) > 0 else 'longer'} route)")
    print(f"Average vs Distance-only: {mean(vs_dist_vals):+.1f}%  "
          f"({'shorter' if mean(vs_dist_vals) > 0 else 'longer'} route)")
    print(f"{'─'*80}")

    # ── Write CSV ─────────────────────────────────────────────────────────────
    out = "baseline_comparison.csv"
    with open(out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(all_rows)
    print(f"CSV saved → {out}")


if __name__ == "__main__":
    asyncio.run(main())
