# Changelog

All notable changes to this project are documented here.
Releases follow the sprint structure described in README.md.

---

## [Scheduling refinement: food cap + meal slot distribution] — 2026-03-18

### Changed

**`app/core/day_allocator.py` — per-day food cap**

- Added `_MAX_FOOD_PER_DAY = 3` constant.
- In `_fill_day()`, added a guard that skips any `food_dining` candidate once
  three have already been selected for the current day. This prevents
  restaurant-heavy interest weights from filling every available slot and
  directly ensures category diversity: the remaining slots are claimed by
  whichever non-food category ranks next (e.g. `local_life` when the user
  selects both food and local as preferred categories).

**`app/core/route_optimizer.py` — breakfast / lunch / dinner slot assignment**

- Replaced the `_interleave_meals()` body with slot-aware positioning:

  | Meal count | Positions |
  |---|---|
  | 1 | Lunch (midpoint of sights) |
  | 2 | Lunch (midpoint) + Dinner (end) |
  | 3 | Breakfast (start) + Lunch (midpoint) + Dinner (end) |

  With a 09:00 day start and typical sight durations of 1.5–2.5 h, this
  naturally places meals inside realistic windows (breakfast ~09:00, lunch
  ~12:00, dinner ~18:00) without any explicit time arithmetic. The sequential
  time-assignment loop in `optimize()` is unchanged.

**Tests**

- `tests/test_day_allocator.py` — 2 new cases in `TestFoodCap`:
  10 food-only POIs → at most 3 selected per day; mixed food + local input
  → local_life POIs still appear once the food cap is reached.

- `tests/test_route_optimizer.py` (new file) — 7 cases covering all
  meal-count branches (`_interleave_meals` with 0 / 1 / 2 / 3 meals),
  a no-sights edge case, and preservation of both meal and sight counts.

---

## [Hotfix: Google Places category mislabelling] — 2026-03-18

### Fixed

**`_TYPE_MAP` priority order in `app/integrations/poi/google_places.py`**

- Root cause: `tourist_attraction` was listed at index 2 in `_TYPE_MAP`, before
  `restaurant` (~index 8) and `park` (~index 5). Google Places returns
  `tourist_attraction` in the `types` array of many venues alongside their primary
  type (e.g. `["restaurant", "tourist_attraction", "establishment"]`). The
  first-match logic in `_map_category()` therefore labelled these venues as
  `history_culture` instead of `food_dining` or `nature_scenery`.

  Consequence: when a user selected `preferred_categories = ["food_dining",
  "local_life"]`, the mislabelled restaurants and parks received a near-zero
  interest score (history_culture weight ≈ 0.04 vs. food weight ≈ 0.40). Only
  shopping POIs — correctly labelled — competed effectively, causing them to
  dominate allocated days and the LLM overview text.

- Fix: reordered `_TYPE_MAP` so all specific venue types (`restaurant`, `cafe`,
  `bar`, `food`, `bakery`, `meal_takeaway`, `meal_delivery`, `park`,
  `natural_feature`, `campground`, `shopping_mall`, `store`, `clothing_store`,
  and all entertainment/local-life types) appear before the generic fallbacks
  (`tourist_attraction`, `place_of_worship`, `cemetery`). The `_map_category()`
  function itself is unchanged.

- Added `tests/test_integrations/test_google_places_category_map.py` — 8
  regression tests confirming that types lists combining a specific type with
  `tourist_attraction` resolve to the specific category (e.g.
  `["restaurant", "tourist_attraction"]` → `food_dining`,
  `["park", "tourist_attraction"]` → `nature_scenery`).

---

## [Sprint 5.6] — 2026-03-18

### Added

**Natural language input parsing layer**

- `app/schemas/nl_request.py` — Two new schemas:
  - `NaturalLanguageTripRequest`: API input body with a single `raw_text` field
    (10–1000 characters). This is what the new endpoint accepts.
  - `ParsedTripInput`: Intermediate structure populated by the LLM. All eight
    fields (`destination`, `duration_days`, `start_date`, `end_date`,
    `budget_level`, `travel_pace`, `preferred_categories`,
    `free_text_preferences`) are `Optional`; missing values are filled by the
    service layer, not here.

- `app/llm/prompt_templates.py` — New function `build_parse_trip_prompt(raw_text)`.
  Instructs the LLM to return **only** a valid JSON object with the exact keys
  matching `ParsedTripInput`. Includes inline enum value lists, category keyword
  mapping hints, and an explicit "no prose, no markdown" rule to maximise
  structural reliability across providers.

- `app/llm/base.py` — New abstract method `parse_natural_language_request(raw_text) → dict`
  added to `BaseLLMProvider`. Contract: all keys present, unextracted values
  are `None`, method never raises.

- `app/llm/mock_provider.py` — Concrete implementation of
  `parse_natural_language_request` using regex and keyword tables.
  - English: destination extracted from capitalized word(s) after "in"/"to";
    stops at the first lowercase word or punctuation.
  - Duration: digit numbers and English word numbers (one–ten) matched;
    Chinese "X天" pattern also supported.
  - ISO date pairs (`YYYY-MM-DD`) extracted for duration computation.
  - Budget, pace, categories, and soft preferences each have separate
    English and Chinese keyword tables.

- `app/llm/openai_provider.py` — Concrete implementation using
  `response_format={"type": "json_object"}` and `temperature=0.0` for
  deterministic structured output. Falls back to `MockLLMProvider` on any error.

- `app/llm/claude_provider.py` — Concrete implementation; strips markdown code
  fences that Claude occasionally adds around JSON before parsing. Falls back
  to `MockLLMProvider` on any error.

- `app/services/nl_input_parser.py` — `NLInputParser` service class.
  Four-step parse pipeline:
  1. Call `llm.parse_natural_language_request(raw_text)` → raw dict
  2. Validate dict into `ParsedTripInput` via Pydantic (raises `HTTP 422` on
     invalid enum values or structure errors)
  3. Require `destination` (only mandatory field; raises `HTTP 422` if absent)
  4. Apply defaults and map to `TripRequest`:
     - `duration_days`: explicit → compute from dates → default `3`
     - `budget_level`: default `mid_range`
     - `travel_pace`: default `moderate`
     - `interests`: always `InterestWeights()` defaults (overridden by
       `PersonaBuilder` when `preferred_categories` is set)
     - `constraints`: always `TripConstraints()` all-False defaults

- `app/api/v1/trips.py` — New endpoint `POST /api/v1/trips/plan-from-text`.
  Accepts `NaturalLanguageTripRequest`, delegates to `NLInputParser.parse()`,
  then calls the existing `TripPlanner.plan()` with the resulting `TripRequest`.
  A module-level `_nl_parser` singleton is created alongside the existing
  `_planner` singleton. The existing `POST /trips/plan` endpoint is untouched.

- `tests/test_nl_input_parser.py` — 36 new unit tests in four classes:
  - `TestHappyPath` (8): destination lowercased, explicit duration, date-derived
    duration, budget/pace/categories/free_text passed through, correct return type.
  - `TestDefaults` (10): each missing field gets its correct default; date range
    out of bounds falls back to 3; explicit duration wins over date range.
  - `TestErrorHandling` (7): missing destination → 422, empty destination → 422,
    invalid enum values → 422, LLM exception → 422, malformed date → default 3.
  - `TestMockProviderIntegration` (11): end-to-end through real `MockLLMProvider`
    regex engine; covers food/history/luxury/budget/relaxed/intensive keywords,
    ISO date pairs, word-number and digit durations, no-destination 422.

### Design decisions

- **Two-schema separation.** `NaturalLanguageTripRequest` (raw text only) and
  `ParsedTripInput` (LLM output, all optional) are deliberately kept apart.
  `TripRequest` is never modified. The parser is the only bridge between them.
- **LLM responsibility is strictly bounded.** The LLM extracts fields; it does
  not choose POIs, allocate days, order routes, or write the final itinerary.
  All planning logic remains in the four-stage structured pipeline.
- **Safe defaults in the service layer, not in the schema.** `ParsedTripInput`
  fields are all `Optional` with no defaults; defaults live in `NLInputParser`.
  This makes the boundary explicit and testable.
- **Backward compatibility preserved.** `POST /trips/plan` and all existing
  schemas are untouched. Clients using structured input are unaffected.
- **Mock provider supports Chinese (lightweight).** Destination, duration,
  budget, pace, categories, and soft preferences each have Chinese keyword
  tables. For a thesis prototype this is sufficient; real LLM providers handle
  Chinese natively.

---

## [Sprint 5.5] — 2026-03-18

### Added

**Preference input enhancement**

- `app/schemas/trip_request.py` — New optional field `preferred_categories: list[POICategory]`
  (1–7 items). Fewer selections produce a more focused traveler profile; selecting all 7 is
  equivalent to "no strong preference". When provided, this field takes priority over the
  legacy `interests: InterestWeights` field (which is fully preserved for backward
  compatibility).

- `app/core/persona_builder.py` — New module-level helper `_categories_to_weights()`.
  Assigns weight `1.0` to selected categories and `0.1` as a small baseline to unselected
  ones, then feeds the result into the existing `_normalise_interests()` L1 normalisation.
  Resulting interest_vector weights:
  - 1 selected ≈ 63% each selected, 6% each unselected
  - 2 selected ≈ 40% each selected, 4% each unselected
  - 7 selected ≈ 14% each (uniform — no preference)

**Bilingual soft-preference inference**

- `app/llm/mock_provider.py` — Added `_detect_language(text)`: lightweight language
  detection based on CJK Unicode character ratio (threshold 15%). Returns `"zh"`,
  `"en"`, or `"unknown"`. No external library required.

- `app/llm/mock_provider.py` — Refactored `infer_soft_preferences` into two separate
  helpers `_infer_zh()` and `_infer_en()`, each with 8 parallel preference tags.
  Chinese keywords cover: 古建筑/历史/文化, 不想排队/少排队, 本地/当地/地道,
  小吃/美食/餐厅, 自然/公园/户外, 博物馆/艺术/画廊, 轻松/悠闲/不要太赶, 拍照/摄影/打卡.
  Text of unknown language returns `[]` without forcing a parse.

**Tests**

- `tests/test_persona_builder.py` — 7 new test cases in `TestPreferredCategories`:
  selected categories dominate unselected, three-category selection, all-7 uniform weights,
  `preferred_categories` overrides `interests`, fallback to `interests` when omitted,
  interest vector still sums to 1.0, `_categories_to_weights` raw output check.

### Design decisions

- **No schema changes to `TravelerPersona`.** The new input flows through
  `_categories_to_weights → _normalise_interests` and produces the same `interest_vector`
  type as before. All downstream stages (scorer, allocator, route optimizer) are untouched.
- **`interests` preserved.** Existing API clients that send raw float weights continue to
  work unchanged. When both `preferred_categories` and `interests` are present,
  `preferred_categories` wins.
- **Language detection is rule-based, not ML-based.** Suitable for a thesis prototype;
  avoids adding any dependency for a simple bilingual use case.

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
