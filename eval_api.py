"""
API Performance Evaluator for POST /api/v1/trips/plan
Usage: python eval_api.py [--url URL] [--n N] [--out FILE]
"""

import argparse
import csv
import random
import time
from datetime import datetime

import requests

# ── Config ────────────────────────────────────────────────────────────────────

DEFAULT_URL = "http://localhost:8000/api/v1/trips/plan"
DEFAULT_N = 30
DEFAULT_OUT = "eval_results.csv"
TIMEOUT_S = 60

# ── Sample pools ──────────────────────────────────────────────────────────────

DESTINATIONS = [
    "beijing", "shanghai", "chengdu", "xi'an", "hangzhou",
    "guilin", "lijiang", "suzhou", "guangzhou", "nanjing",
]

TRAVEL_PACES = ["relaxed", "moderate", "intensive"]
BUDGET_LEVELS = ["budget", "mid_range", "luxury"]
INTEREST_KEYS = [
    "history_culture", "nature_scenery", "food_dining",
    "shopping", "art_museum", "entertainment", "local_life",
]

CSV_FIELDS = [
    "request_id",
    "timestamp",
    "destination",
    "duration_days",
    "budget_level",
    "travel_pace",
    "interests_snapshot",
    "latency_s",
    "status_code",
    "success",
    "poi_count",
    "poi_per_day_avg",
    "pace_in_range",
    "error_message",
]

# Expected POI-per-day range per travel pace.
PACE_TARGETS: dict[str, tuple[int, int]] = {
    "relaxed":   (2, 3),
    "moderate":  (3, 4),
    "intensive": (5, 6),
}

# ── Helpers ───────────────────────────────────────────────────────────────────

def random_interests() -> dict:
    """Generate a random InterestWeights dict with values in [0.0, 1.0]."""
    weights = {k: round(random.uniform(0.0, 1.0), 2) for k in INTEREST_KEYS}
    # Bias toward at least 2–3 strong interests so results are meaningful
    strong = random.sample(INTEREST_KEYS, k=random.randint(2, 4))
    for k in strong:
        weights[k] = round(random.uniform(0.7, 1.0), 2)
    return weights


def random_payload() -> dict:
    return {
        "destination": random.choice(DESTINATIONS),
        "duration_days": random.randint(2, 7),
        "budget_level": random.choice(BUDGET_LEVELS),
        "travel_pace": random.choice(TRAVEL_PACES),
        "interests": random_interests(),
    }


def run_request(url: str, payload: dict) -> dict:
    """Fire one request and return a result row."""
    row = {
        "request_id": "",
        "timestamp": datetime.utcnow().isoformat(timespec="seconds"),
        "destination": payload["destination"],
        "duration_days": payload["duration_days"],
        "budget_level": payload["budget_level"],
        "travel_pace": payload["travel_pace"],
        "interests_snapshot": str(payload["interests"]),
        "latency_s": None,
        "status_code": None,
        "success": False,
        "poi_count": 0,
        "poi_per_day_avg": None,
        "pace_in_range": None,
        "error_message": "",
    }

    t0 = time.perf_counter()
    try:
        resp = requests.post(url, json=payload, timeout=TIMEOUT_S)
        row["latency_s"] = round(time.perf_counter() - t0, 3)
        row["status_code"] = resp.status_code

        if resp.status_code == 200:
            data = resp.json()
            row["success"] = True
            row["request_id"] = data.get("request_id", "")
            days = data.get("days", [])
            day_counts = [len(day.get("pois", [])) for day in days]
            row["poi_count"] = sum(day_counts)
            # Pace control accuracy
            if day_counts:
                row["poi_per_day_avg"] = round(sum(day_counts) / len(day_counts), 2)
                lo, hi = PACE_TARGETS.get(payload["travel_pace"], (0, 99))
                row["pace_in_range"] = all(lo <= c <= hi for c in day_counts)
        else:
            row["error_message"] = resp.text[:200]

    except requests.exceptions.Timeout:
        row["latency_s"] = round(time.perf_counter() - t0, 3)
        row["error_message"] = f"Timeout after {TIMEOUT_S}s"
    except requests.exceptions.ConnectionError as e:
        row["latency_s"] = round(time.perf_counter() - t0, 3)
        row["error_message"] = f"ConnectionError: {e}"

    return row


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Evaluate trip-planner API performance")
    parser.add_argument("--url", default=DEFAULT_URL, help="API endpoint URL")
    parser.add_argument("--n", type=int, default=DEFAULT_N, help="Number of requests (20–50)")
    parser.add_argument("--out", default=DEFAULT_OUT, help="Output CSV file path")
    args = parser.parse_args()

    n = max(20, min(50, args.n))
    print(f"Sending {n} requests to {args.url}")
    print(f"Results → {args.out}\n")

    results = []
    for i in range(1, n + 1):
        payload = random_payload()
        row = run_request(args.url, payload)
        results.append(row)

        status_icon = "✓" if row["success"] else "✗"
        print(
            f"[{i:>2}/{n}] {status_icon} {payload['destination']:<12} "
            f"pace={payload['travel_pace']:<10} "
            f"latency={row['latency_s']:.3f}s  "
            f"pois={row['poi_count']:>2}  "
            f"http={row['status_code']}"
        )

    # ── Write CSV ──────────────────────────────────────────────────────────────
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(results)

    # ── Summary ───────────────────────────────────────────────────────────────
    successes = [r for r in results if r["success"]]
    failures  = [r for r in results if not r["success"]]
    latencies = [r["latency_s"] for r in results if r["latency_s"] is not None]

    print(f"\n{'─'*55}")
    print(f"Total requests : {n}")
    print(f"Success        : {len(successes)}  ({100*len(successes)/n:.1f}%)")
    print(f"Failure        : {len(failures)}")
    if latencies:
        print(f"Latency avg    : {sum(latencies)/len(latencies):.3f}s")
        print(f"Latency min    : {min(latencies):.3f}s")
        print(f"Latency max    : {max(latencies):.3f}s")
        sorted_lat = sorted(latencies)
        p95_idx = int(len(sorted_lat) * 0.95)
        print(f"Latency p95    : {sorted_lat[p95_idx]:.3f}s")

    # Pace control accuracy per pace tier
    pace_rows = [r for r in successes if r.get("pace_in_range") is not None]
    if pace_rows:
        print(f"{'─'*55}")
        print(f"Pace control accuracy (POIs/day within target range):")
        for pace, (lo, hi) in PACE_TARGETS.items():
            tier_rows = [r for r in pace_rows if r["travel_pace"] == pace]
            if not tier_rows:
                continue
            in_range = sum(1 for r in tier_rows if r["pace_in_range"] is True)
            print(
                f"  {pace:<10} target={lo}–{hi}  "
                f"in-range={in_range}/{len(tier_rows)}  "
                f"({100*in_range/len(tier_rows):.1f}%)"
            )

    print(f"CSV saved to   : {args.out}")


if __name__ == "__main__":
    main()
