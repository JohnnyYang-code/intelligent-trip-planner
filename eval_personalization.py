"""
Personalization Score Evaluation

Compares interest alignment of the full pipeline's POI selection against a
PopularityBaseline that picks top-N POIs purely by raw popularity score.

Metric — interest_alignment:
    Mean of score_breakdown.interest_score across all selected POIs.
    Higher = selected POIs better match the traveler's stated interests.

Usage:  python eval_personalization.py
Output: personalization_results.csv  +  console table
"""

import asyncio
import csv
import os
from statistics import mean

os.environ.setdefault("ENV_FILE", ".env")

from app.config.settings import get_settings
from app.core.baseline_router import PopularityBaseline
from app.core.day_allocator import DayAllocator
from app.core.persona_builder import PersonaBuilder
from app.core.poi_scorer import POIScorer
from app.integrations.maps.maps_factory import create_maps_provider
from app.integrations.poi.poi_factory import create_poi_provider
from app.integrations.weather.weather_factory import create_weather_provider
from app.schemas.common import BudgetLevel, POICategory, TravelPace
from app.schemas.poi import ScoredPOI
from app.schemas.trip_request import InterestWeights, TripConstraints, TripRequest

# ── Test cases ────────────────────────────────────────────────────────────────

TEST_CASES = [
    {
        "label": "Beijing / 3d / moderate / history+food",
        "request": TripRequest(
            destination="beijing",
            duration_days=3,
            travel_pace=TravelPace.moderate,
            budget_level=BudgetLevel.mid_range,
            interests=InterestWeights(history_culture=0.9, art_museum=0.7, food_dining=0.5),
        ),
    },
    {
        "label": "Shanghai / 2d / intensive / shopping+local",
        "request": TripRequest(
            destination="shanghai",
            duration_days=2,
            travel_pace=TravelPace.intensive,
            budget_level=BudgetLevel.luxury,
            interests=InterestWeights(shopping=0.9, food_dining=0.8, local_life=0.6),
        ),
    },
    {
        "label": "Chengdu / 2d / relaxed / nature+food",
        "request": TripRequest(
            destination="chengdu",
            duration_days=2,
            travel_pace=TravelPace.relaxed,
            budget_level=BudgetLevel.budget,
            interests=InterestWeights(nature_scenery=0.9, food_dining=0.8, local_life=0.7),
        ),
    },
    {
        "label": "Beijing / 2d / relaxed / children+no_shopping",
        "request": TripRequest(
            destination="beijing",
            duration_days=2,
            travel_pace=TravelPace.relaxed,
            budget_level=BudgetLevel.mid_range,
            interests=InterestWeights(history_culture=0.8, nature_scenery=0.7, food_dining=0.5),
            constraints=TripConstraints(
                with_children=True,
                avoid_categories=[POICategory.shopping],
            ),
        ),
    },
]

CSV_FIELDS = [
    "test_case",
    "n_selected",
    "your_interest_alignment",
    "popularity_interest_alignment",
    "your_total_score_avg",
    "popularity_total_score_avg",
    "interest_improvement_pct",
]

# ── Pipeline helpers ──────────────────────────────────────────────────────────

async def run_stages_1_to_3(request: TripRequest):
    """Return (persona, all_scored_pois, days_allocated)."""
    settings = get_settings()
    poi_provider     = create_poi_provider(settings)
    maps_provider    = create_maps_provider(settings)
    weather_provider = create_weather_provider(settings)

    persona     = PersonaBuilder().build(request)
    pois        = await poi_provider.search_pois(request.destination)
    weather     = await weather_provider.get_forecast(request.destination, request.duration_days)
    scored_pois = POIScorer().score_all(pois, persona)
    days_scored = DayAllocator().allocate(scored_pois, persona, weather)

    return persona, scored_pois, days_scored


# ── Metrics ───────────────────────────────────────────────────────────────────

def interest_alignment(scored_pois: list[ScoredPOI]) -> float:
    """Mean interest_score component across a set of POIs."""
    if not scored_pois:
        return 0.0
    return mean(sp.score_breakdown.interest_score for sp in scored_pois)


def total_score_avg(scored_pois: list[ScoredPOI]) -> float:
    if not scored_pois:
        return 0.0
    return mean(sp.total_score for sp in scored_pois)


def improvement_pct(your_val: float, baseline_val: float) -> float:
    if baseline_val == 0:
        return 0.0
    return (your_val - baseline_val) / baseline_val * 100


# ── Main ──────────────────────────────────────────────────────────────────────

async def main():
    pop_baseline = PopularityBaseline()
    rows = []

    for tc in TEST_CASES:
        print(f"\nRunning: {tc['label']} ...")
        persona, all_scored, days_scored = await run_stages_1_to_3(tc["request"])

        # Your system: POIs actually allocated across all days
        your_selected = [sp for day in days_scored for sp in day]
        n = len(your_selected)

        # Popularity baseline: top-N by raw popularity_score
        pop_selected = pop_baseline.select(all_scored, n)

        your_ia  = interest_alignment(your_selected)
        pop_ia   = interest_alignment(pop_selected)
        your_ts  = total_score_avg(your_selected)
        pop_ts   = total_score_avg(pop_selected)
        ia_delta = improvement_pct(your_ia, pop_ia)

        # Print selected POI names for inspection
        print(f"  Your ({n} POIs): " +
              ", ".join(sp.poi.name_en or sp.poi.name for sp in your_selected[:5]) +
              ("..." if n > 5 else ""))
        print(f"  Pop  ({n} POIs): " +
              ", ".join(sp.poi.name_en or sp.poi.name for sp in pop_selected[:5]) +
              ("..." if n > 5 else ""))

        rows.append({
            "test_case":                   tc["label"],
            "n_selected":                  n,
            "your_interest_alignment":     round(your_ia, 4),
            "popularity_interest_alignment": round(pop_ia, 4),
            "your_total_score_avg":        round(your_ts, 4),
            "popularity_total_score_avg":  round(pop_ts, 4),
            "interest_improvement_pct":    round(ia_delta, 1),
        })

    # ── Console table ─────────────────────────────────────────────────────────
    W = 95
    print(f"\n{'─' * W}")
    print(
        f"{'Test Case':<44} {'N':>3}  "
        f"{'Yours IA':>9}  {'Pop IA':>9}  "
        f"{'Yours TS':>9}  {'Pop TS':>9}  "
        f"{'IA +%':>7}"
    )
    print(f"{'─' * W}")
    for r in rows:
        print(
            f"{r['test_case']:<44} {r['n_selected']:>3}  "
            f"{r['your_interest_alignment']:>9.4f}  "
            f"{r['popularity_interest_alignment']:>9.4f}  "
            f"{r['your_total_score_avg']:>9.4f}  "
            f"{r['popularity_total_score_avg']:>9.4f}  "
            f"{r['interest_improvement_pct']:>+6.1f}%"
        )

    deltas = [r["interest_improvement_pct"] for r in rows]
    print(f"{'─' * W}")
    print(
        f"Average interest alignment improvement vs PopularityBaseline: "
        f"{mean(deltas):+.1f}%"
    )
    print(f"{'─' * W}")

    # ── Write CSV ─────────────────────────────────────────────────────────────
    out = "personalization_results.csv"
    with open(out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"CSV saved → {out}")


if __name__ == "__main__":
    asyncio.run(main())
