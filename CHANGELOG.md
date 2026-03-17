# Changelog

All notable changes to this project are documented here.
Releases follow the sprint structure described in README.md.

---

## [Sprint 5] — 2026-03-18

### Fixed

**Time overflow bug (Great Wall showing 03:27)**

- `app/core/route_optimizer.py` — Added `_MAX_TRAVEL_HOURS_FALLBACK = 1.5`.
  `_travel_hours()` now caps Haversine-estimated travel time at 1.5 h per leg,
  preventing distant POIs (e.g. Great Wall, 57 km from city centre) from
  overflowing the day's schedule past midnight.
- `app/core/route_optimizer.py` — `RouteOptimizer.__init__` now accepts an
  optional `maps_provider: BaseMapsProvider`. When a real provider is injected,
  actual driving time is used instead of the Haversine fallback.

**Geographic spread constraint in day allocator**

- `app/core/day_allocator.py` — Added `_MAX_INTRA_DAY_SPREAD_KM = 40.0`.
  `_fill_day()` now ranks candidates by effective score and skips any POI whose
  straight-line distance to an already-selected day POI exceeds 40 km.
  `_exceeds_spread()` helper performs the check using `haversine_km`.
  Effect: attractions more than 40 km apart (e.g. Forbidden City vs Great Wall)
  are automatically placed on separate days.

### Added

**Real external API providers**

- `app/integrations/weather/openweathermap.py` — `OpenWeatherMapProvider`.
  Calls the free OWM 5-day/3-hour forecast endpoint via `httpx`. Picks the
  12:00 slot per day as the daily representative. Maps OWM `weather[0].main`
  codes (Clear, Rain, Snow, …) to internal condition strings. Repeats the last
  available day when the API range is shorter than the trip duration.

- `app/integrations/maps/google_maps.py` — `GoogleMapsProvider`.
  Wraps the `googlemaps` SDK. `get_distance()` calls Distance Matrix API
  (driving mode); `geocode()` calls Geocoding API. Lazy SDK import — safe if
  `googlemaps` package is absent.

- `app/integrations/maps/amap.py` — `AmapProvider`.
  Uses `httpx` to call the Amap Web Service driving route and geocoding APIs.
  Includes `wgs84_to_gcj02()` pure function for coordinate conversion (WGS-84
  mock POI data → GCJ-02 required by Amap). All API calls are async.

- `app/integrations/poi/google_places.py` — `GooglePlacesPOIProvider`.
  Geocodes the destination, then runs one Nearby Search per `POICategory`
  using the `googlemaps` SDK. Maps Google Place types → `POICategory`,
  `price_level` → `BudgetLevel` + `avg_cost_cny`, `rating` → `quality_score`,
  `user_ratings_total` (log-normalised) → `popularity_score`.

**Service layer update**

- `app/services/trip_planner.py` — `TripPlanner.__init__` now instantiates
  `self.maps_provider` via `create_maps_provider(settings)` and injects it
  into `RouteOptimizer(maps_provider=self.maps_provider)`. Health log now
  also reports the active maps provider.

### Design decisions

- **Two-layer geographic fix.** The 40 km spread constraint prevents distant
  POIs from landing on the same day; the 1.5 h travel-time cap is a safety
  net for the remaining Haversine-based time assignment.
- **`_exceeds_spread` uses Haversine only.** The real Maps provider is not
  called here — allocation runs synchronously before route optimization, and
  Haversine is accurate enough for a 40 km threshold check.
- **Amap `get_distance` is sync.** `BaseMapsProvider.get_distance` is declared
  synchronous (used in a tight loop inside `RouteOptimizer`). The Amap
  implementation raises if called from an async event loop; `RouteOptimizer`
  will fall through to the Haversine cap in that case. A future sprint can
  make `get_distance` async.

---

## [Sprint 4] — 2026-03-18

### Added

**LLM abstraction layer** (`app/llm/`)

- `base.py` — `BaseLLMProvider` ABC with four typed async methods:
  `generate_overview`, `generate_day_narrative`, `generate_poi_reason`,
  `infer_soft_preferences`. Typed signatures keep each generation task
  explicit and testable without parsing prompt strings.

- `prompt_templates.py` — Four pure functions (`build_overview_prompt`,
  `build_day_narrative_prompt`, `build_poi_reason_prompt`,
  `build_soft_preference_prompt`) that construct prompt strings for real
  LLM providers. Mock provider bypasses these entirely.

- `mock_provider.py` — Deterministic template-based implementation.
  `infer_soft_preferences` uses lightweight keyword matching to detect
  tags such as `ancient_architecture`, `avoid_crowds`, and `food_focused`
  without any API call. All other methods return fixed template strings.

- `openai_provider.py` — Wraps the OpenAI `AsyncOpenAI` client with lazy
  import (safe if `openai` package is absent). Each method builds a prompt
  via `prompt_templates`, calls `chat.completions.create`, and falls back
  to `MockLLMProvider` on any exception.

- `claude_provider.py` — Same structure as OpenAI provider, using the
  Anthropic `AsyncAnthropic` client and `messages.create`. Identical
  fallback behavior.

- `llm_factory.py` — `create_llm_provider(settings)` returns the
  configured provider. Falls back to mock when a real provider is selected
  but its API key is missing; logs a warning instead of raising.

**Service layer updates**

- `app/services/itinerary_builder.py` — Extended `build()` signature with
  three optional LLM content parameters: `overview: str`, `day_narratives:
  list[str]`, `poi_reasons: dict[str, str]`. When provided, `poi_reasons`
  values are written directly to `ScheduledPOI.recommendation_reason`.

- `app/services/trip_planner.py` — LLM generation inserted after Stage 4:
  1. Soft-preference inference runs immediately after Stage 1 if
     `free_text_preferences` is set; result is written to
     `persona.inferred_soft_preferences`.
  2. Overview, all day narratives, and all POI reasons are generated in
     parallel via `asyncio.gather` after all four planning stages complete.
  3. LLM results are passed to `itinerary_builder.build()`.
  Any individual LLM failure is caught and logged; the itinerary is
  returned with an empty string for that field rather than raising.

### Design decisions

- **LLM runs after all four planning stages.** It never influences POI
  selection, scoring, allocation, or routing — only text content.
- **Parallel generation.** `asyncio.gather` issues overview, all day
  narratives, and all POI reasons concurrently, minimising latency when
  using a real LLM provider.
- **Graceful degradation.** Every real provider method wraps its API call
  in a try/except and falls back to `MockLLMProvider`. The pipeline never
  fails due to LLM unavailability.
- **No LangChain dependency.** All providers are thin SDK wrappers;
  LangChain may be added behind `BaseLLMProvider` in future without
  changing any other module.

---

## [Sprint 3] — 2026-03-18

### Added

**API layer**

- `app/api/v1/health.py` — `GET /api/v1/health`.
  Instantiates all three external providers (POI, Maps, Weather) and
  returns their `provider_name`, `is_available()` status, and configured
  mode (`mock` / real) in a structured JSON response.
  The LLM entry is included as a placeholder (`available: true`) with
  the mode read from `settings.llm_provider`; full LLM availability
  checking is added in Sprint 4.

- `app/api/v1/trips.py` — `POST /api/v1/trips/plan`.
  Accepts a `TripRequest` body, delegates to a module-level `TripPlanner`
  instance (stateless, safe to reuse across requests), and returns an
  `ItineraryResponse`. Unhandled exceptions are caught and re-raised as
  `HTTP 500` with a descriptive message.

**Router update**

- `app/api/router.py` — Replaced the Sprint 1 stub with real route
  registration. Both `health.router` and `trips.router` are included
  under the `/v1` prefix, which combines with `main.py`'s `/api` mount
  to produce the final paths `/api/v1/health` and `/api/v1/trips/plan`.

### No changes to

- `main.py` — Already correctly mounted `api_router` at `/api` from
  Sprint 1; no modification needed.
- All core / service / integration modules — untouched.

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
