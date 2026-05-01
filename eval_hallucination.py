"""
Explanation Consistency / Hallucination Check

Verifies that LLM-generated text fields are grounded in the actual planned
itinerary rather than fabricated content.

Two checks
----------
1. POI reason grounding
   For each POI, `recommendation_reason` should mention the POI's name or its
   English alias.  A reason that doesn't reference the POI at all is a
   candidate hallucination.

   Metric: poi_name_mention_rate  (target ≈ 100%)

2. Day narrative coverage
   Each day's `narrative` should mention at least one of the POIs scheduled
   that day (the LLM prompt explicitly requires ≥1 POI name).

   Metric: narrative_coverage_rate  (target ≈ 100%)

3. Overview destination mention
   The top-level `overview` should mention the destination city.

   Metric: overview_dest_mention_rate  (target ≈ 100%)

Notes
-----
- Requires a real LLM provider (LLM_PROVIDER=claude or openai in .env).
  With LLM_PROVIDER=mock the reasons are deterministic templates and this
  check is not meaningful.
- Requires the backend to be running:
    uvicorn main:app --reload

Usage
-----
  python eval_hallucination.py [--url URL] [--n N] [--out FILE]
  python eval_hallucination.py --n 15
"""

import argparse
import csv

import requests

DEFAULT_URL = "http://localhost:8000/api/v1/trips/plan"
DEFAULT_N   = 15
DEFAULT_OUT = "hallucination_results.csv"
TIMEOUT_S   = 90   # longer timeout for real LLM calls

SAMPLE_PAYLOADS = [
    {
        "destination": "beijing",
        "duration_days": 2,
        "travel_pace": "moderate",
        "budget_level": "mid_range",
        "interests": {"history_culture": 0.9, "food_dining": 0.5},
    },
    {
        "destination": "shanghai",
        "duration_days": 2,
        "travel_pace": "intensive",
        "budget_level": "luxury",
        "interests": {"shopping": 0.9, "food_dining": 0.8, "local_life": 0.6},
    },
    {
        "destination": "chengdu",
        "duration_days": 2,
        "travel_pace": "relaxed",
        "budget_level": "budget",
        "interests": {"nature_scenery": 0.9, "food_dining": 0.8},
    },
    {
        "destination": "beijing",
        "duration_days": 3,
        "travel_pace": "relaxed",
        "budget_level": "mid_range",
        "interests": {"art_museum": 0.8, "history_culture": 0.7},
    },
    {
        "destination": "shanghai",
        "duration_days": 2,
        "travel_pace": "moderate",
        "budget_level": "mid_range",
        "interests": {"local_life": 0.9, "history_culture": 0.6},
    },
]

CSV_FIELDS = [
    "request_id",
    "destination",
    "total_pois",
    "poi_reason_checked",
    "poi_name_mentions",
    "poi_name_mention_rate",
    "total_days",
    "narrative_days_checked",
    "narrative_coverage_hits",
    "narrative_coverage_rate",
    "overview_dest_mention",
    "hallucination_flag",
]

# ── Grounding checks ──────────────────────────────────────────────────────────

def _name_tokens(poi: dict) -> list[str]:
    """Return lowercase name tokens to match against the reason text."""
    tokens = []
    name = poi.get("name", "")
    name_en = poi.get("name_en", "") or ""
    # Full name
    if name:
        tokens.append(name.lower())
    if name_en:
        tokens.append(name_en.lower())
    # First meaningful word of English name (e.g. "Forbidden" from "Forbidden City")
    if name_en:
        words = [w for w in name_en.split() if len(w) > 3]
        tokens.extend(w.lower() for w in words[:2])
    return tokens


def _reason_mentions_poi(reason: str, poi: dict) -> bool:
    if not reason:
        return False
    reason_lower = reason.lower()
    return any(tok in reason_lower for tok in _name_tokens(poi))


def _narrative_mentions_any(narrative: str, poi_names: list[dict]) -> bool:
    if not narrative:
        return False
    narrative_lower = narrative.lower()
    return any(
        any(tok in narrative_lower for tok in _name_tokens(p))
        for p in poi_names
    )


def _check_response(data: dict) -> dict:
    destination = data.get("destination", "")
    days = data.get("days", [])
    overview = data.get("overview", "")

    poi_reason_checked   = 0
    poi_name_mentions    = 0
    narrative_days_checked  = 0
    narrative_coverage_hits = 0
    total_pois = 0

    for day in days:
        pois = day.get("pois", [])
        narrative = day.get("narrative", "")
        total_pois += len(pois)

        # Check each POI's recommendation_reason
        for sp in pois:
            poi = sp.get("poi", sp)
            reason = sp.get("recommendation_reason", "")
            if reason:   # skip if empty (mock mode / not generated)
                poi_reason_checked += 1
                if _reason_mentions_poi(reason, poi):
                    poi_name_mentions += 1

        # Check day narrative coverage
        if narrative and pois:
            narrative_days_checked += 1
            if _narrative_mentions_any(narrative, [sp.get("poi", sp) for sp in pois]):
                narrative_coverage_hits += 1

    poi_rate = (
        poi_name_mentions / poi_reason_checked
        if poi_reason_checked else None
    )
    narrative_rate = (
        narrative_coverage_hits / narrative_days_checked
        if narrative_days_checked else None
    )
    overview_dest = (
        destination.lower() in overview.lower()
        if overview and destination else None
    )

    hallucination_flag = (
        (poi_rate is not None and poi_rate < 0.8)
        or (narrative_rate is not None and narrative_rate < 0.8)
        or (overview_dest is False)
    )

    return {
        "total_pois":              total_pois,
        "poi_reason_checked":      poi_reason_checked,
        "poi_name_mentions":       poi_name_mentions,
        "poi_name_mention_rate":   round(poi_rate, 3) if poi_rate is not None else "n/a",
        "total_days":              len(days),
        "narrative_days_checked":  narrative_days_checked,
        "narrative_coverage_hits": narrative_coverage_hits,
        "narrative_coverage_rate": round(narrative_rate, 3) if narrative_rate is not None else "n/a",
        "overview_dest_mention":   overview_dest if overview_dest is not None else "n/a",
        "hallucination_flag":      hallucination_flag,
    }


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="LLM hallucination / grounding check")
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--n",   type=int, default=DEFAULT_N,
                        help="Number of requests (1–30, default 15)")
    parser.add_argument("--out", default=DEFAULT_OUT)
    args = parser.parse_args()
    n = max(1, min(30, args.n))

    print(f"Sending {n} requests to {args.url}")
    print("Note: run with LLM_PROVIDER=claude or openai for meaningful results.\n")

    rows = []
    agg = {
        "poi_rates":       [],
        "narrative_rates": [],
        "overview_hits":   0,
        "overview_total":  0,
        "hallucinations":  0,
    }

    for i in range(n):
        payload = SAMPLE_PAYLOADS[i % len(SAMPLE_PAYLOADS)]
        try:
            resp = requests.post(args.url, json=payload, timeout=TIMEOUT_S)
            if resp.status_code != 200:
                print(f"  [{i+1:>2}/{n}] ✗ HTTP {resp.status_code}")
                continue
            data = resp.json()
        except Exception as exc:
            print(f"  [{i+1:>2}/{n}] ✗ {exc}")
            continue

        cr = _check_response(data)
        flag = "⚠" if cr["hallucination_flag"] else "✓"
        print(
            f"  [{i+1:>2}/{n}] {flag} {payload['destination']:<10} "
            f"pois={cr['total_pois']}  "
            f"poi_mention={cr['poi_name_mention_rate']}  "
            f"narrative_cov={cr['narrative_coverage_rate']}  "
            f"overview_dest={cr['overview_dest_mention']}"
        )

        if isinstance(cr["poi_name_mention_rate"], float):
            agg["poi_rates"].append(cr["poi_name_mention_rate"])
        if isinstance(cr["narrative_coverage_rate"], float):
            agg["narrative_rates"].append(cr["narrative_coverage_rate"])
        if cr["overview_dest_mention"] is True:
            agg["overview_hits"] += 1
        if cr["overview_dest_mention"] is not None and cr["overview_dest_mention"] != "n/a":
            agg["overview_total"] += 1
        if cr["hallucination_flag"]:
            agg["hallucinations"] += 1

        rows.append({
            "request_id":             data.get("request_id", ""),
            "destination":            payload["destination"],
            **{k: cr[k] for k in [
                "total_pois", "poi_reason_checked", "poi_name_mentions",
                "poi_name_mention_rate", "total_days", "narrative_days_checked",
                "narrative_coverage_hits", "narrative_coverage_rate",
                "overview_dest_mention", "hallucination_flag",
            ]},
        })

    # ── Summary ───────────────────────────────────────────────────────────────
    print(f"\n{'═' * 58}")
    print(f"  LLM Grounding / Hallucination Summary  ({len(rows)} requests)")
    print(f"{'═' * 58}")

    if agg["poi_rates"]:
        avg_poi = sum(agg["poi_rates"]) / len(agg["poi_rates"])
        print(f"  POI name mention rate  : {avg_poi:.1%}  "
              f"({len(agg['poi_rates'])} responses with reasons)")
    else:
        print(f"  POI name mention rate  : n/a  (no recommendation_reason found — "
              f"is LLM_PROVIDER set to a real provider?)")

    if agg["narrative_rates"]:
        avg_nar = sum(agg["narrative_rates"]) / len(agg["narrative_rates"])
        print(f"  Narrative coverage rate: {avg_nar:.1%}  "
              f"({len(agg['narrative_rates'])} days with narratives)")
    else:
        print(f"  Narrative coverage rate: n/a  (no narratives found)")

    if agg["overview_total"]:
        print(
            f"  Overview dest mention  : "
            f"{agg['overview_hits']}/{agg['overview_total']}  "
            f"({100*agg['overview_hits']/agg['overview_total']:.1f}%)"
        )

    print(f"  Hallucination flags    : {agg['hallucinations']}/{len(rows)}")
    print(f"{'═' * 58}")

    with open(args.out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"CSV saved → {args.out}")


if __name__ == "__main__":
    main()
