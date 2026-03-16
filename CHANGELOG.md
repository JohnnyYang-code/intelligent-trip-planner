# Changelog

All notable changes to this project are documented here.
Releases follow the sprint structure described in README.md.

---

## [Sprint 2] — 2026-03-16

### Added

**Core planning engine — Stage 3 & 4**

- `app/core/day_allocator.py` — Stage 3 of the planning pipeline.
  Distributes scored POIs across trip days using a greedy strategy.
  Applies two ephemeral day-specific adjustments (weather preference for
  indoor/outdoor POIs; district clustering bonus) without mutating any
  `ScoredPOI` object.

- `app/core/route_optimizer.py` — Stage 4 of the planning pipeline.
  Orders POIs within a single day using nearest-neighbour routing
  (Haversine straight-line approximation) and a lightweight meal-slot rule
  (first meal at midpoint, additional meals at end of day).
  Assigns sequential `suggested_start_time` values from 09:00 onward,
  accounting for visit duration, a configurable transport buffer, and
  estimated walking time between stops.

**Service layer**

- `app/services/itinerary_builder.py` — Pure assembly step.
  Converts pipeline outputs into a complete `ItineraryResponse`.
  Derives a human-readable day theme from the dominant POI category.
  LLM-generated fields (`overview`, `narrative`, `tips`,
  `recommendation_reason`) are empty strings; Sprint 4 fills them in.

- `app/services/trip_planner.py` — Main pipeline orchestrator.
  Single `async plan(TripRequest) → ItineraryResponse` method that
  explicitly calls each stage in order:
  1. `PersonaBuilder.build()`
  2. `POIScorer.score_all()` (weather-independent)
  3. `DayAllocator.allocate()` (weather-aware internally)
  4. `RouteOptimizer.optimize()` per day
  5. `ItineraryBuilder.build()`
  All external providers (POI, Weather) are injected via their factories
  and default to mock mode.

**Tests**

- `tests/test_day_allocator.py` — 16 unit tests covering:
  - Result length equals `duration_days`
  - Each day respects `pois_per_day_max`
  - Empty input returns empty days without error
  - Fewer POIs than days does not crash; single POI allocated exactly once
  - Each POI allocated at most once across all days
  - Zero-score POIs (constraint violations) never appear in output
  - Indoor POIs survive rainy-day weather adjustment
  - `ScoredPOI.total_score` is never mutated during allocation
  - Allocation works correctly when no weather list is provided
  - Daily duration sum stays within `daily_hours_budget + 0.5h` tolerance

### Design decisions

- **Stage 2 remains weather-independent.** `poi_scorer.py` was not
  modified. Weather adjustment belongs to Stage 3 (allocation), where
  it is applied as an ephemeral multiplier on the existing `total_score`.

- **No `ScoredPOI` mutation.** The `_effective_score()` helper in
  `day_allocator.py` returns a plain `float` used only for candidate
  ranking within the selection loop; it is never stored or written back.

- **Route optimization kept simple.** No complex temporal buckets or
  multi-constraint scheduling. The only special-case rule is meal-slot
  interleaving; all other POIs are ordered by nearest-neighbour.

- **Provider signatures unchanged.** `TripPlanner` calls
  `poi_provider.search_pois(destination)` and
  `weather_provider.get_forecast(city, days)` — both match the ABC
  definitions in Sprint 1 exactly.

---

## [Sprint 1] — 2026-03-15

### Added

**Project scaffolding**

- `README.md` — Full project documentation.
- `requirements.txt` — All Python dependencies.
- `.env.example` — Configuration template (all providers default to mock).
- `.gitignore` — Standard Python ignores including `.env`.
- `main.py` — FastAPI application entry point with CORS and router mount.
- `app/config/settings.py` — `pydantic-settings` `BaseSettings` with
  `@lru_cache` singleton and `Literal` type constraints on provider names.

**Schemas** (`app/schemas/`)

- `common.py` — `TravelPace`, `BudgetLevel`, `POICategory` enums.
- `trip_request.py` — `InterestWeights`, `TripConstraints`, `TripRequest`.
- `persona.py` — `TravelerPersona`.
- `poi.py` — `POI`, `ScoreBreakdown`, `ScoredPOI`, `ScheduledPOI`.
- `itinerary.py` — `DailyWeather`, `DayPlan`, `ItineraryResponse`.

**Mock data** (`app/data/mock/`)

- `beijing_pois.json` — 12 POIs covering all 7 categories.
- `shanghai_pois.json` — 12 POIs.
- `chengdu_pois.json` — 12 POIs.

**Integration layer** (`app/integrations/`)

- POI: `BasePOIProvider` ABC · `MockPOIProvider` (reads local JSON) ·
  `poi_factory.py`.
- Maps: `BaseMapsProvider` ABC · `MockMapsProvider` (Haversine) ·
  `maps_factory.py`.
- Weather: `BaseWeatherProvider` ABC · `MockWeatherProvider` (seasonal
  city baselines, fixed seed 42) · `weather_factory.py`.

**Core planning — Stage 1 & 2**

- `app/core/persona_builder.py` — Stage 1. Converts `TripRequest` into
  `TravelerPersona` via L1-normalised interest vector, budget sensitivity
  mapping, and pace-capacity lookup.
- `app/core/poi_scorer.py` — Stage 2. Composite scoring formula:
  `(0.55 × interest + 0.25 × popularity + 0.20 × budget) × constraint_multiplier`.
  Hard blocks (avoid_categories, accessibility) zero the score; soft
  penalties (with_children, with_elderly) reduce the multiplier.

**API stub**

- `app/api/router.py` — Minimal stub so `main.py` imports without error.
  Real routes added in Sprint 3.

**Tests**

- `tests/test_persona_builder.py` — 18 tests: interest normalisation,
  all-zero fallback, budget sensitivity values, pace capacity, persona
  summary content, constraints passthrough.
- `tests/test_poi_scorer.py` — 16 tests: score range, sorted output,
  interest matching, budget tier matching, all constraint scenarios.
- `tests/fixtures/sample_request.json` — Fixture for integration tests.
