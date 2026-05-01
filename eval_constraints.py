"""
Constraint Compliance Evaluation

Sends targeted HTTP requests with specific constraints and verifies that the
pipeline's output respects both hard and soft constraint rules.

Hard constraints tested (expected 0% violation):
  1. avoid_categories  — blocked category must never appear in output POIs
  2. accessibility_required — inaccessible POIs must never appear

Soft/structural rules tested (expected ≥95% compliance):
  3. food_dining cap     — ≤ 3 food_dining POIs per day
  4. diversity guarantee — ≥ 1 non-food POI per day
  5. with_children       — no child_unfriendly POIs (soft penalty; reports rate)

Requires the backend to be running:
  uvicorn main:app --reload

Usage:  python eval_constraints.py [--url URL] [--out FILE]
Output: constraint_results.csv  +  console table
"""

import argparse
import csv
from dataclasses import dataclass, field

import requests

DEFAULT_URL = "http://localhost:8000/api/v1/trips/plan"
DEFAULT_OUT = "constraint_results.csv"
TIMEOUT_S   = 60

# ── Test suite ────────────────────────────────────────────────────────────────

TEST_CASES = [
    # ── avoid_categories ─────────────────────────────────────────────────────
    {
        "id": "avoid_shopping_beijing",
        "label": "Beijing — avoid shopping",
        "payload": {
            "destination": "beijing",
            "duration_days": 3,
            "travel_pace": "moderate",
            "budget_level": "mid_range",
            "interests": {"history_culture": 0.9, "food_dining": 0.5},
            "constraints": {"avoid_categories": ["shopping"]},
        },
        "check": "avoid_shopping",
    },
    {
        "id": "avoid_entertainment_shanghai",
        "label": "Shanghai — avoid entertainment",
        "payload": {
            "destination": "shanghai",
            "duration_days": 2,
            "travel_pace": "intensive",
            "budget_level": "luxury",
            "interests": {"local_life": 0.9, "food_dining": 0.7},
            "constraints": {"avoid_categories": ["entertainment"]},
        },
        "check": "avoid_entertainment",
    },
    {
        "id": "avoid_shopping_chengdu",
        "label": "Chengdu — avoid shopping",
        "payload": {
            "destination": "chengdu",
            "duration_days": 2,
            "travel_pace": "relaxed",
            "budget_level": "budget",
            "interests": {"nature_scenery": 0.9, "food_dining": 0.8},
            "constraints": {"avoid_categories": ["shopping"]},
        },
        "check": "avoid_shopping",
    },
    # ── accessibility_required ────────────────────────────────────────────────
    {
        "id": "accessible_beijing",
        "label": "Beijing — accessibility required",
        "payload": {
            "destination": "beijing",
            "duration_days": 2,
            "travel_pace": "moderate",
            "budget_level": "mid_range",
            "interests": {"history_culture": 0.8, "art_museum": 0.6},
            "constraints": {"accessibility_required": True},
        },
        "check": "accessibility",
    },
    {
        "id": "accessible_shanghai",
        "label": "Shanghai — accessibility required",
        "payload": {
            "destination": "shanghai",
            "duration_days": 2,
            "travel_pace": "moderate",
            "budget_level": "mid_range",
            "interests": {"local_life": 0.8, "history_culture": 0.6},
            "constraints": {"accessibility_required": True},
        },
        "check": "accessibility",
    },
    # ── with_children ─────────────────────────────────────────────────────────
    {
        "id": "children_beijing",
        "label": "Beijing — with children",
        "payload": {
            "destination": "beijing",
            "duration_days": 2,
            "travel_pace": "relaxed",
            "budget_level": "mid_range",
            "interests": {"history_culture": 0.8, "nature_scenery": 0.7},
            "constraints": {"with_children": True},
        },
        "check": "children",
    },
    {
        "id": "children_chengdu",
        "label": "Chengdu — with children",
        "payload": {
            "destination": "chengdu",
            "duration_days": 2,
            "travel_pace": "relaxed",
            "budget_level": "budget",
            "interests": {"nature_scenery": 0.9, "food_dining": 0.6},
            "constraints": {"with_children": True},
        },
        "check": "children",
    },
    # ── General structural rules (no special constraints) ─────────────────────
    {
        "id": "food_cap_food_lover",
        "label": "Beijing — food-heavy interests (cap test)",
        "payload": {
            "destination": "beijing",
            "duration_days": 3,
            "travel_pace": "intensive",
            "budget_level": "mid_range",
            "interests": {"food_dining": 1.0},
        },
        "check": "structural",
    },
    {
        "id": "diversity_food_lover",
        "label": "Shanghai — food-heavy interests (diversity test)",
        "payload": {
            "destination": "shanghai",
            "duration_days": 2,
            "travel_pace": "moderate",
            "budget_level": "mid_range",
            "interests": {"food_dining": 1.0},
        },
        "check": "structural",
    },
]

CSV_FIELDS = [
    "test_id", "label", "check_type",
    "n_days", "n_pois_total",
    "hard_violations", "violation_details",
    "food_cap_ok", "diversity_ok",
    "child_unfriendly_count",
    "inaccessible_count",
    "passed",
]


# ── Check functions ───────────────────────────────────────────────────────────

@dataclass
class CheckResult:
    hard_violations: int = 0
    violation_details: list[str] = field(default_factory=list)
    food_cap_ok: bool = True
    diversity_ok: bool = True
    child_unfriendly_count: int = 0
    inaccessible_count: int = 0
    n_days: int = 0
    n_pois_total: int = 0


def _check_response(tc: dict, data: dict) -> CheckResult:
    r = CheckResult()
    days = data.get("days", [])
    r.n_days = len(days)
    payload = tc["payload"]
    check_type = tc["check"]
    avoid_cats = set(payload.get("constraints", {}).get("avoid_categories", []))
    accessibility_req = payload.get("constraints", {}).get("accessibility_required", False)
    with_children = payload.get("constraints", {}).get("with_children", False)

    for day in days:
        pois = day.get("pois", [])
        r.n_pois_total += len(pois)
        food_count = 0
        non_food_count = 0

        for sp in pois:
            poi = sp.get("poi", sp)  # ScheduledPOI wraps POI
            cat = poi.get("category", "")

            # Hard check: avoided category
            if check_type in ("avoid_shopping", "avoid_entertainment"):
                avoided = avoid_cats
                if cat in avoided:
                    r.hard_violations += 1
                    r.violation_details.append(
                        f"Day {day.get('day_number')}: {poi.get('name_en') or poi.get('name')} "
                        f"(category={cat}) violates avoid_categories={avoided}"
                    )

            # Hard check: accessibility
            if accessibility_req and not poi.get("accessible", True):
                r.hard_violations += 1
                r.inaccessible_count += 1
                r.violation_details.append(
                    f"Day {day.get('day_number')}: {poi.get('name_en') or poi.get('name')} "
                    f"is not accessible but accessibility_required=True"
                )

            # Soft check: child unfriendly
            if with_children and not poi.get("child_friendly", True):
                r.child_unfriendly_count += 1

            # Structural checks
            if cat == "food_dining":
                food_count += 1
            else:
                non_food_count += 1

        if food_count > 3:
            r.food_cap_ok = False
        if non_food_count == 0 and r.n_pois_total > 0:
            r.diversity_ok = False

    return r


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Constraint compliance evaluation")
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--out", default=DEFAULT_OUT)
    args = parser.parse_args()

    rows = []
    totals = {
        "hard_violations": 0,
        "food_cap_fails":  0,
        "diversity_fails": 0,
        "child_unfriendly": 0,
        "inaccessible":    0,
        "passed": 0,
    }

    print(f"Running {len(TEST_CASES)} constraint tests against {args.url}\n")

    for tc in TEST_CASES:
        try:
            resp = requests.post(args.url, json=tc["payload"], timeout=TIMEOUT_S)
            if resp.status_code != 200:
                print(f"  ✗ [{tc['id']}] HTTP {resp.status_code}: {resp.text[:120]}")
                continue
            data = resp.json()
        except Exception as exc:
            print(f"  ✗ [{tc['id']}] Request failed: {exc}")
            continue

        cr = _check_response(tc, data)
        passed = (
            cr.hard_violations == 0
            and cr.food_cap_ok
            and cr.diversity_ok
        )

        icon = "✓" if passed else "✗"
        print(
            f"  {icon} [{tc['id']}]  days={cr.n_days}  pois={cr.n_pois_total}  "
            f"hard_violations={cr.hard_violations}  "
            f"food_cap={'ok' if cr.food_cap_ok else 'FAIL'}  "
            f"diversity={'ok' if cr.diversity_ok else 'FAIL'}  "
            f"child_unfriendly={cr.child_unfriendly_count}"
        )
        if cr.violation_details:
            for detail in cr.violation_details:
                print(f"      !! {detail}")

        totals["hard_violations"]  += cr.hard_violations
        totals["food_cap_fails"]   += 0 if cr.food_cap_ok else 1
        totals["diversity_fails"]  += 0 if cr.diversity_ok else 1
        totals["child_unfriendly"] += cr.child_unfriendly_count
        totals["inaccessible"]     += cr.inaccessible_count
        if passed:
            totals["passed"] += 1

        rows.append({
            "test_id":               tc["id"],
            "label":                 tc["label"],
            "check_type":            tc["check"],
            "n_days":                cr.n_days,
            "n_pois_total":          cr.n_pois_total,
            "hard_violations":       cr.hard_violations,
            "violation_details":     "; ".join(cr.violation_details) or "none",
            "food_cap_ok":           cr.food_cap_ok,
            "diversity_ok":          cr.diversity_ok,
            "child_unfriendly_count": cr.child_unfriendly_count,
            "inaccessible_count":    cr.inaccessible_count,
            "passed":                passed,
        })

    # ── Summary ───────────────────────────────────────────────────────────────
    n = len(rows)
    print(f"\n{'═' * 55}")
    print(f"  Constraint Compliance Summary  ({n} tests)")
    print(f"{'═' * 55}")
    print(f"  Passed (all checks) : {totals['passed']}/{n}  ({100*totals['passed']/n:.1f}%)")
    print(f"  Hard violations     : {totals['hard_violations']}  (expected 0)")
    print(f"  Food cap fails      : {totals['food_cap_fails']}   (expected 0)")
    print(f"  Diversity fails     : {totals['diversity_fails']}   (expected 0)")
    print(f"  Child-unfriendly POIs (soft): {totals['child_unfriendly']}")
    print(f"  Inaccessible POIs (hard):     {totals['inaccessible']}")
    print(f"{'═' * 55}")

    with open(args.out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"CSV saved → {args.out}")


if __name__ == "__main__":
    main()
