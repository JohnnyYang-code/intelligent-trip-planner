"""
Latency Comparison: Pipeline-Only (mock LLM) vs Pipeline + Real LLM

Runs the full trip planning pipeline in-process in two modes and measures
end-to-end wall-clock latency per request.

Modes
-----
  no_llm   : Stages 1–4 + deterministic mock templates (LLM_PROVIDER=mock)
  with_llm : Stages 1–4 + real LLM narration (Claude or OpenAI, from .env)

The LLM provider is swapped in-process by clearing the settings lru_cache and
re-instantiating TripPlanner — no server restart required.

Usage
-----
  python eval_latency.py               # auto-detect LLM from .env, n=15
  python eval_latency.py --n 20        # custom sample count
  python eval_latency.py --no-real-llm # mock-only (useful when no API key)

Output
------
  latency_comparison.csv  +  console comparison table
"""

import argparse
import asyncio
import csv
import os
from statistics import mean, stdev

os.environ.setdefault("ENV_FILE", ".env")

from app.config.settings import get_settings
from app.schemas.common import BudgetLevel, TravelPace
from app.schemas.trip_request import InterestWeights, TripRequest

# Fixed sample requests — cycled through for each run.
_SAMPLE_REQUESTS = [
    TripRequest(
        destination="beijing", duration_days=3,
        travel_pace=TravelPace.moderate, budget_level=BudgetLevel.mid_range,
        interests=InterestWeights(history_culture=0.9, food_dining=0.5),
    ),
    TripRequest(
        destination="shanghai", duration_days=2,
        travel_pace=TravelPace.intensive, budget_level=BudgetLevel.luxury,
        interests=InterestWeights(shopping=0.9, food_dining=0.8),
    ),
    TripRequest(
        destination="chengdu", duration_days=2,
        travel_pace=TravelPace.relaxed, budget_level=BudgetLevel.budget,
        interests=InterestWeights(nature_scenery=0.9, food_dining=0.8),
    ),
    TripRequest(
        destination="beijing", duration_days=2,
        travel_pace=TravelPace.relaxed, budget_level=BudgetLevel.mid_range,
        interests=InterestWeights(nature_scenery=0.7, art_museum=0.6),
    ),
    TripRequest(
        destination="shanghai", duration_days=3,
        travel_pace=TravelPace.moderate, budget_level=BudgetLevel.mid_range,
        interests=InterestWeights(local_life=0.8, food_dining=0.7),
    ),
]

# ── Helpers ───────────────────────────────────────────────────────────────────

def _stats(latencies: list[float]) -> dict:
    if not latencies:
        return {"n": 0, "mean": 0.0, "min": 0.0, "max": 0.0, "p95": 0.0, "std": 0.0}
    s = sorted(latencies)
    return {
        "n":    len(s),
        "mean": round(mean(s), 3),
        "min":  round(s[0], 3),
        "max":  round(s[-1], 3),
        "p95":  round(s[int(len(s) * 0.95)], 3),
        "std":  round(stdev(s) if len(s) > 1 else 0.0, 3),
    }


async def _run_batch(planner, n: int) -> list[float]:
    """Run n planning requests (cycling samples) and return per-request latencies."""
    import time
    latencies: list[float] = []
    for i in range(n):
        req = _SAMPLE_REQUESTS[i % len(_SAMPLE_REQUESTS)]
        t0 = time.perf_counter()
        try:
            await planner.plan(req)
            latencies.append(round(time.perf_counter() - t0, 3))
        except Exception as exc:
            print(f"    request {i + 1} failed: {exc}")
    return latencies


# ── Main ──────────────────────────────────────────────────────────────────────

async def main():
    parser = argparse.ArgumentParser(description="Latency: with-LLM vs no-LLM")
    parser.add_argument("--n", type=int, default=15,
                        help="Requests per mode (5–30, default 15)")
    parser.add_argument("--no-real-llm", action="store_true",
                        help="Only run mock-LLM mode (skip real LLM calls)")
    args = parser.parse_args()
    n = max(5, min(30, args.n))

    # Detect real LLM provider from original .env BEFORE modifying env
    _init_settings = get_settings()
    if _init_settings.anthropic_api_key:
        real_provider = "claude"
    elif _init_settings.openai_api_key:
        real_provider = "openai"
    else:
        real_provider = None

    results: dict[str, list[float]] = {}

    # ── Mode 1: Mock LLM ──────────────────────────────────────────────────────
    from app.services.trip_planner import TripPlanner

    print(f"[1/2] Mock LLM (deterministic templates)  —  {n} requests ...")
    get_settings.cache_clear()
    os.environ["LLM_PROVIDER"] = "mock"
    planner_mock = TripPlanner()
    mock_lat = await _run_batch(planner_mock, n)
    results["no_llm"] = mock_lat
    ms = _stats(mock_lat)
    print(f"      mean={ms['mean']:.3f}s  p95={ms['p95']:.3f}s  n={ms['n']}")

    # ── Mode 2: Real LLM ──────────────────────────────────────────────────────
    real_lat: list[float] = []
    if args.no_real_llm:
        print("[2/2] Skipped (--no-real-llm flag set)")
    elif real_provider is None:
        print("[2/2] Skipped — no ANTHROPIC_API_KEY or OPENAI_API_KEY found in .env")
    else:
        print(f"[2/2] Real LLM ({real_provider})  —  {n} requests ...")
        get_settings.cache_clear()
        os.environ["LLM_PROVIDER"] = real_provider
        planner_real = TripPlanner()
        real_lat = await _run_batch(planner_real, n)
        results["with_llm"] = real_lat
        rs = _stats(real_lat)
        print(f"      mean={rs['mean']:.3f}s  p95={rs['p95']:.3f}s  n={rs['n']}")

    # ── Comparison table ──────────────────────────────────────────────────────
    ms = _stats(results.get("no_llm", []))
    rs = _stats(results.get("with_llm", []))

    print(f"\n{'─' * 58}")
    print(f"  Latency Breakdown: Pipeline-Only vs Pipeline + LLM")
    print(f"{'─' * 58}")
    print(f"{'Metric':<10}  {'No LLM':>10}  {'With LLM':>10}  {'Overhead':>10}")
    print(f"{'─' * 58}")
    for key in ("mean", "p95", "min", "max", "std"):
        m_val = ms.get(key, 0.0)
        r_val = rs.get(key, 0.0)
        m_str = f"{m_val:.3f}s"
        r_str = f"{r_val:.3f}s" if rs["n"] else "n/a"
        ov_str = f"+{r_val - m_val:.3f}s" if rs["n"] else "n/a"
        print(f"{key.upper():<10}  {m_str:>10}  {r_str:>10}  {ov_str:>10}")
    print(f"{'─' * 58}")
    if rs["n"]:
        overhead = rs["mean"] - ms["mean"]
        pct = overhead / ms["mean"] * 100 if ms["mean"] else 0.0
        print(f"  LLM mean overhead: +{overhead:.3f}s  ({pct:+.1f}% of pipeline-only time)")
    print(f"{'─' * 58}")

    # ── Write CSV ─────────────────────────────────────────────────────────────
    out = "latency_comparison.csv"
    max_len = max((len(v) for v in results.values()), default=0)
    no_llm_lat  = results.get("no_llm",   [])
    with_llm_lat = results.get("with_llm", [])
    with open(out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["index", "no_llm_s", "with_llm_s"])
        writer.writeheader()
        for i in range(max_len):
            writer.writerow({
                "index":       i + 1,
                "no_llm_s":   no_llm_lat[i]   if i < len(no_llm_lat)   else "",
                "with_llm_s": with_llm_lat[i] if i < len(with_llm_lat) else "",
            })
    print(f"CSV saved → {out}")


if __name__ == "__main__":
    asyncio.run(main())
