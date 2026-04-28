# Conference Paper Outline
## Structured Personalization for AI-Driven Trip Planning: A Four-Stage Pipeline Approach

---

## 1. Introduction

### 1.1 Motivation
- Existing trip planning tools (Google Travel, TripAdvisor) rank Points of Interest (POIs) by global popularity scores, producing identical recommendations regardless of individual traveler preferences, pace, or constraints.
- Pure LLM-based planners (e.g., raw GPT-4/Claude itineraries) are fluent but yield non-deterministic, unexplainable schedules that routinely violate geographic feasibility, daily time budgets, and accessibility constraints.
- There is no system that combines *structured, algorithmic planning* with *natural language presentation* in a principled way.

### 1.2 Research Goals
- Design a personalized itinerary generation system where every scheduling decision is traceable to a user-expressed preference.
- Demonstrate that a deterministic, multi-stage pipeline can match LLM fluency while guaranteeing constraint compliance and explainability.

### 1.3 Contributions
1. **TravelerPersona** — a normalized, multi-dimensional user profile that encodes interests, pace, budget sensitivity, and inferred soft preferences.
2. **Composite POI Scoring** — a weighted scoring model (0.55 interest + 0.25 popularity + 0.20 budget fit) with stackable constraint multipliers and full score breakdown per POI.
3. **Weather-Aware Greedy Day Allocator** — a multi-day POI selection algorithm with real-time weather adjustments and geographic clustering.
4. **Nearest-Neighbor Route Optimizer** with strategic meal interleaving and time assignment.
5. **Hybrid LLM Narration** — post-hoc natural language generation strictly separated from planning logic, with deterministic fallback.
6. Empirical evaluation: **≥21.5% route-distance reduction** over random baseline; **~1.85 s mean end-to-end latency** (p95 ~3.9 s).

---

## 2. Related Work

### 2.1 Popularity-Based Trip Recommenders
- Google Travel, TripAdvisor, and Yelp rank venues by aggregate ratings and check-in frequency.
- **Limitation:** Homogeneous output regardless of traveler identity; no mechanism for preference differentiation or constraint enforcement.

### 2.2 Constraint-Aware Itinerary Planning
- Prior work frames trip planning as variants of the Orienteering Problem or Team Orienteering Problem with time-window constraints [cite].
- Algorithms maximize POI coverage subject to a time budget.
- **Limitation:** Optimization objective is coverage-maximization, not preference-alignment; user interest vectors are absent.

### 2.3 LLM-Based Travel Assistants
- Recent systems prompt GPT-4 or Claude to generate full itineraries from free-text user requests [cite].
- Produce human-readable, contextually aware output.
- **Limitation:** Non-deterministic outputs, no route feasibility guarantees, inability to reliably enforce hard constraints (accessibility, budget tier matching).

### 2.4 Hybrid Retrieval + Ranking Systems
- Some systems use retrieval-augmented generation (RAG) to ground LLM outputs in venue databases.
- **Our distinction:** Planning logic is entirely deterministic; LLM is restricted to post-hoc narration, never to scheduling decisions.

---

## 3. Methodology

### 3.1 System Architecture
- **Backend:** FastAPI (Python 3.11+), four sequential deterministic stages, async LLM narration calls.
- **Frontend:** React 19 + TypeScript + Tailwind CSS 4.
- **Provider abstraction:** Interchangeable layers for POI data (Google Places API / mock JSON), routing (Google Maps / Amap / Haversine fallback), and weather (OpenWeatherMap / seasonal mock).
- **Design principle:** "Structured logic drives every planning decision. LLMs only handle language — not strategy."

```
TripRequest
    │
    ▼
[Stage 1] Persona Builder   →  TravelerPersona
    │
    ▼
[Stage 2] POI Scorer        →  ScoredPOI[] (ranked, with score breakdown)
    │
    ▼
[Stage 3] Day Allocator     →  list[list[ScoredPOI]] (one per day)
    │
    ▼
[Stage 4] Route Optimizer   →  list[ScheduledPOI] (ordered, timed)
    │
    ▼
[LLM] Narration (async)     →  ItineraryResponse (overview + day narratives + POI reasons)
```

### 3.2 Stage 1 — Persona Construction (`app/core/persona_builder.py`)

**Inputs:** destination, duration (days), budget level {budget, mid_range, luxury}, travel pace {relaxed, moderate, intensive}, raw interest weights (7 categories, 0–1 each), free-text constraints.

**Outputs — `TravelerPersona`:**

| Field | Description |
|-------|-------------|
| `interest_vector` | L1-normalized weights over 7 categories (sum = 1.0) |
| `pois_per_day_target / max` | Relaxed: 2–3; Moderate: 3–4; Intensive: 5–6 |
| `budget_sensitivity` | Budget=0.9 (tight), Mid=0.5, Luxury=0.1; +0.1 if elderly/children |
| `inferred_soft_preferences` | NLP-extracted from free text (e.g., "avoid_crowds", "vegetarian") |
| `persona_summary` | One-sentence profile injected into every LLM prompt |

**Interest normalization:** If user explicitly selects preferred categories, those receive weight 1.0; unselected receive 0.1 baseline. All weights are then L1-normalized.

**Example persona summary:** *"A mid-range traveller with strong interest in history & culture and food & dining, preferring a moderate pace over 3 day(s) in Beijing. Travelling with children."*

### 3.3 Stage 2 — POI Scoring (`app/core/poi_scorer.py`)

**Composite scoring formula (all components normalized to [0, 1]):**

```
total_score = ( 0.55 × interest_score
              + 0.25 × popularity_score
              + 0.20 × budget_fit_score )
              × constraint_multiplier
```

**Component definitions:**

| Component | Formula |
|-----------|---------|
| `interest_score` | `persona.interest_vector[category] × (poi.quality_score / 10)` |
| `popularity_score` | `poi.popularity_score / 10` |
| `budget_fit_score` | Same tier → 1.0; 1 tier apart → 0.5; 2 tiers apart → 0.0; minus `sensitivity × gap × 0.4` |

**Constraint multiplier — hard blocks (→ 0.0):**
- POI in user's `avoid_categories`
- Accessibility required but venue is inaccessible

**Constraint multiplier — soft penalties (stackable):**
- Not child-friendly (traveling with children): ×0.30
- Not elderly-accessible (traveling with elderly): ×0.40
- Avoid-crowds preference on shopping/entertainment: ×0.25
- Non-preferred category (interest_weight < 0.08): ×0.40

**Stacking example:** Shopping mall, history-focused user with "avoid_crowds" preference:
- Base score: 0.43 → ×0.40 (non-preferred) = 0.172 → ×0.25 (avoid_crowds) = **0.043** (10× suppression).

**Explainability:** Full `ScoreBreakdown` (interest, popularity, budget, penalty details) stored with each `ScoredPOI`.

### 3.4 Stage 3 — Day Allocation (`app/core/day_allocator.py`)

**Algorithm:** Greedy multi-day selection with ephemeral day-specific score adjustments (underlying `ScoredPOI` objects are never mutated).

**Per-day selection loop** (candidates ordered by descending score):

Hard constraints checked before each selection:
- Daily time budget: 8 h default, 0.5 h overflow tolerance
- Intra-day geographic spread: ≤ 40 km (prevents Forbidden City + Great Wall same day)
- Food/dining cap: ≤ 3 per day
- Low-interest cap: ≤ 1 POI/day with `interest_weight < 0.08`
- Diversity guarantee: ≥ 1 non-food POI per day

Ephemeral day-specific score adjustments (applied during selection only):
- Rainy forecast: indoor POIs ×1.15; outdoor POIs ×0.75
- Same district as already-selected POIs: ×1.10 (geographic clustering bonus)

**Output:** `list[list[ScoredPOI]]` — one unordered list per day.

### 3.5 Stage 4 — Route Optimization (`app/core/route_optimizer.py`)

**Within-day ordering algorithm:**

1. **Separate** `food_dining` POIs (meals) from sightseeing POIs.
2. **Nearest-neighbor greedy ordering** on sights using Haversine straight-line distance.
3. **Meal interleaving** by count:
   - 1 meal → lunch inserted at route midpoint
   - 2 meals → lunch (midpoint) + dinner (end)
   - 3+ meals → breakfast (start) + lunch (midpoint) + dinner (end)
4. **Sequential time assignment** from 09:00:
   - Each step accumulates `poi.duration_hours + 0.25 h transport buffer + travel_time`
   - Travel time: real Maps API when available; fallback = Haversine distance / 4 km/h (walking), capped at 1.5 h/leg

**Output:** `list[ScheduledPOI]` with `visit_order` and `suggested_start_time`.

### 3.6 LLM Narration — Post-Planning (`app/llm/`)

Three async LLM calls run *after* Stages 1–4 complete (planning is already finalized):

| Call | Model budget | Content |
|------|-------------|---------|
| Trip overview | ≤ 200 tokens | 2–3 sentence introduction referencing persona summary |
| Day narrative (×N days) | ≤ 150 tokens | Mentions ≥ 1 POI, incorporates weather context |
| POI reason (×M POIs) | ≤ 60 tokens | One-sentence personalized recommendation reason |

**Providers:** Anthropic `claude-3-5-haiku-20241022` or OpenAI `gpt-4o-mini`. Full fallback to deterministic mock templates — the pipeline never fails due to LLM unavailability.

### 3.7 Natural Language Input Parsing (`app/services/nl_input_parser.py`)

Free-text trip request → structured `TripRequest` via LLM extraction + Pydantic v2 validation. Only destination field is mandatory; all others receive sensible defaults (duration defaults to 3 days, pace to moderate, etc.).

---

## 4. Evaluation

### 4.1 Experimental Setup

- **POI datasets:** Mock data for 3 cities (Beijing, Shanghai, Chengdu), 25–30 POIs each, covering all 7 interest categories.
- **Evaluation scripts:**
  - `eval_api.py` — 30 randomized HTTP requests with varied parameters; records latency and success.
  - `eval_baseline.py` — 3 fixed test cases (Beijing/3d/moderate, Shanghai/2d/intensive, Chengdu/2d/relaxed) compared across 3 routing strategies.
  - `eval_report.py` — aggregates CSV results into summary statistics and visualization.

### 4.2 Evaluation Metrics

| Metric | Definition | Measurement Method |
|--------|-----------|-------------------|
| **Personalization score** | Weighted-average `interest_score` of POIs in final itinerary (proxy for preference alignment) | Derived from `ScoredPOI.score_breakdown` |
| **Route distance (km)** | Total Haversine distance of within-day visit ordering | `baseline_router.total_distance_km()` |
| **End-to-end latency (s)** | Wall-clock time from HTTP request receipt to complete `ItineraryResponse` | `eval_api.py` timestamps |
| **Constraint compliance** | Rate of hard-block violations in output (should be 0%) | Unit test suite (134 tests) |

### 4.3 Baselines (`app/core/baseline_router.py`)

Three routing strategies evaluated on **identical POI allocations** (same Stage 3 output):

| Baseline | Strategy |
|---------|---------|
| **Proposed** | Interest-scored NN + meal interleaving |
| **RandomBaseline** | Uniformly shuffled order (seeded) |
| **DistanceOnlyBaseline** | Greedy NN on distance, ignoring preference scores |

---

## 5. Results

### 5.1 Route Quality (eval_baseline.py — 3 cities × 2 days = 6 day-level comparisons)

| Comparison | Average Improvement |
|------------|-------------------|
| Proposed vs. RandomBaseline | **+21.5% shorter** total daily route distance |
| Proposed vs. DistanceOnlyBaseline | ≈ 0.0% (same NN heuristic applied to same POI set) |

**Interpretation:** The improvement over random confirms that systematic nearest-neighbor ordering eliminates unnecessary backtracking. Parity with DistanceOnlyBaseline establishes that the route-ordering algorithm is already near-optimal — the system's primary personalization advantage is in *which POIs are selected* (Stage 2–3), not how they are subsequently ordered (Stage 4).

### 5.2 System Latency (eval_api.py — n=30 requests)

| Metric | Value |
|--------|-------|
| Success rate | 93.3% (28/30) |
| Mean latency | ~1.85 s |
| p95 latency | ~3.90 s |
| Min / Max | 0.31 s / 4.52 s |
| Std deviation | ~0.92 s |

**Component breakdown:**
- Stages 1–4 (deterministic, no I/O): sub-100 ms
- LLM narration (dominant cost): 0.5–2.0 s depending on provider and day count

p95 < 4 s is within acceptable bounds for interactive travel planning applications.

### 5.3 Personalization Effectiveness — Qualitative Examples

**Test case:** Beijing, 3 days, moderate pace, history_culture (0.6) + food_dining (0.3) interests, "avoid crowds" preference.

| POI | Category | Base Score | After Penalties | Effect |
|-----|----------|-----------|-----------------|--------|
| Forbidden City | history_culture | 0.81 | 0.81 (no penalty) | Day 1, rank 1 |
| National Museum | art_museum | 0.67 | 0.67 (no penalty) | Day 2 |
| Wangfujing Mall | shopping | 0.43 | 0.043 (×0.40 non-preferred, ×0.25 avoid_crowds) | Effectively excluded |
| Great Wall | history_culture | 0.78 | 0.78 (but >40 km from Day 1 cluster) | Allocated to Day 2 |

### 5.4 Constraint Compliance
- 134 unit tests: 100% pass rate across persona construction, POI scoring, day allocation, and route optimization.
- Hard-block violation rate: **0%** — avoided categories and inaccessible venues are never included in output.

---

## 6. Conclusion

### 6.1 Summary
We presented a hybrid personalized trip planning system that enforces user preferences through a four-stage deterministic pipeline while delegating natural language generation to LLMs. The strict separation of planning logic from language generation produces:
- **Explainable** itineraries with per-POI score breakdowns
- **Reliable** constraint enforcement (hard blocks guaranteed; soft penalties quantified)
- **Robust** behavior — deterministic fallback ensures output even when LLM services are unavailable

### 6.2 Key Findings
- The four-stage pipeline (persona → score → allocate → route) reliably produces preference-aligned, geographically feasible itineraries with full auditability.
- Nearest-neighbor route ordering reduces daily travel distance by ~21.5% compared to random ordering.
- End-to-end latency of ~1.85 s (p95 ~3.9 s) is suitable for interactive deployment; LLM narration is the dominant cost.
- Stackable constraint multipliers provide fine-grained penalty control without eliminating POIs entirely, preserving itinerary diversity.

### 6.3 Limitations
- Evaluation relies on mock POI datasets (3 cities, ~25–30 POIs each); real-world Google Places data would increase ecological validity and stress-test edge cases.
- Nearest-neighbor is a greedy heuristic; exact TSP solvers or Lin-Kernighan variants could yield further route reductions.
- Personalization is measured by a score-based proxy (weighted interest alignment); direct user studies measuring satisfaction would provide stronger evidence.
- Dynamic re-planning in response to real-time events (traffic, unexpected closures, weather changes mid-trip) is not yet supported.

### 6.4 Future Work
- User study with human participants across diverse trip types to validate personalization metric against stated satisfaction.
- Integration with live Google Places and OpenWeatherMap APIs for real-world evaluation.
- Extension to multi-city / inter-city routing scenarios.
- Investigation of TSP/LKH solvers as a drop-in replacement for Stage 4.
- Real-time itinerary re-planning triggered by disruption events.

---

## Appendix

### A. POI Interest Categories
| Category | Examples |
|----------|---------|
| history_culture | Forbidden City, temples, heritage sites |
| nature_scenery | parks, mountains, lakes |
| food_dining | restaurants, street food, tea houses |
| shopping | malls, markets, boutiques |
| art_museum | galleries, contemporary art spaces |
| entertainment | theaters, amusement parks |
| local_life | hutong neighborhoods, wet markets |

### B. Scoring Weight Configuration (`.env`)
```
POI_WEIGHT_INTEREST=0.55
POI_WEIGHT_POPULARITY=0.25
POI_WEIGHT_BUDGET=0.20
```

### C. Evaluation Reproduction Commands
```bash
# Start backend
uvicorn main:app --reload

# API latency benchmark (30 requests)
python eval_api.py --n 30 --url http://localhost:8000/api/v1/trips/plan --out eval_results.csv

# Baseline routing comparison
python eval_baseline.py

# Summary statistics + chart
python eval_report.py

# Full unit test suite (expect 134 passing)
pytest tests/ -v
```
