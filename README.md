# Intelligent Trip Planning Assistant

A hybrid intelligent travel planning backend that generates personalized multi-day itineraries.
Built as a university-level Python backend prototype.

---

## Project Overview

Most trip planning tools either require too much manual configuration or produce generic AI-generated itineraries that ignore real user preferences.

This project takes a different approach: **structured personalization logic drives every planning decision**, and an LLM is used only to improve the language and explanation of the output.

The result is a system that is both explainable and user-friendly — not a black-box chatbot.

---

## Core Design Idea

```
Optional: Natural Language Input (Sprint 5.6)
    ↓
LLM Input Parsing     ← extracts structured fields from free text
    ↓
User Input (structured TripRequest)
    ↓
PersonaBuilder        ← builds traveler profile from preferences
    ↓
POI Retrieval         ← fetches candidates from data source
    ↓
POI Filtering         ← applies hard constraints (avoid categories, accessibility)
    ↓
POI Scoring           ← ranks by interest match × quality + popularity + budget fit
    ↓
Day Allocation        ← greedy assignment across days with geographic clustering
    ↓
Route Optimization    ← nearest-neighbor ordering + time-of-day rules per day
    ↓
Weather Injection     ← fetches forecast, adjusts weights for bad-weather days
    ↓
LLM Text Generation   ← narrates each day, explains recommendations, writes overview
    ↓
ItineraryResponse     ← structured JSON with full plan + natural language
```

**The LLM does not plan the trip. It either parses user input or narrates the result — never both at once.**

The structured pipeline decides:
- which POIs to include
- how many per day
- in what order
- with what time estimates

The LLM is responsible for:
- **parsing natural language input** into structured fields (Sprint 5.6 — input layer only)
- generating natural day-by-day narrative text
- writing one-sentence recommendation reasons
- inferring soft preferences from free-text input (optional)
- producing the overall trip overview

---

## Implementation Status

The project is built in six sprints. Each sprint is self-contained and leaves the codebase in a runnable state.

| Sprint | Scope | Status |
|--------|-------|--------|
| Sprint 1 | Schemas · Mock providers (POI / Maps / Weather) · `persona_builder` · `poi_scorer` · unit tests | ✅ Complete |
| Sprint 2 | `day_allocator` · `route_optimizer` · `itinerary_builder` · `trip_planner` · allocator tests | ✅ Complete |
| Sprint 3 | API layer (`health.py`, `trips.py`) · full `router.py` · curl end-to-end test | ✅ Complete |
| Sprint 4 | LLM layer (`base`, mock, OpenAI/Claude providers, prompt templates) · narrative generation | ✅ Complete |
| Sprint 5 | Real external API implementations (Google Places, Maps, Amap, OpenWeatherMap) · geographic spread constraint · travel-time cap | ✅ Complete |
| Sprint 5.5 | Preference input enhancement: `preferred_categories` · bilingual soft-preference inference (中/EN) | ✅ Complete |
| Sprint 5.6 | LLM-based natural language input parsing · `POST /api/v1/trips/plan-from-text` · `NLInputParser` service · 36 new tests | ✅ Complete |
| Hotfix | `_TYPE_MAP` reorder in `google_places.py` — specific venue types now win over `tourist_attraction` · 8 regression tests | ✅ Complete |
| Scheduling fix | `day_allocator`: food cap (max 3/day) · `route_optimizer`: breakfast/lunch/dinner slot distribution · 9 new tests | ✅ Complete |
| Quality refinement | Cost realism · budget consistency · diversity guarantee · meal timing · blended day themes | ✅ Complete |
| Frontend polish | Time blocks (Morning/Afternoon/Evening) · formatted budget tier · contextual hint chips on POI cards | ✅ Complete |
| Preference alignment | `avoid_crowds` soft pref → 0.25× multiplier on shopping/entertainment · low-interest category cap (≤ 1/day) | ✅ Complete |
| Sprint 6 | SQLite persistence · `GET /trips/{id}` endpoint | Planned |

### What works right now (Sprint 5.6 + Hotfixes + Frontend Polish)

The server is fully runnable. Start it and use any HTTP client:

```bash
uvicorn main:app --reload
```

**Health check:**
```bash
curl http://localhost:8000/api/v1/health
```

**Plan a trip from a natural language description (new in Sprint 5.6):**
```bash
curl -X POST http://localhost:8000/api/v1/trips/plan-from-text \
  -H "Content-Type: application/json" \
  -d '{
    "raw_text": "I'\''d like to spend three days in Brisbane, focusing mainly on food."
  }'
```

The LLM extracts destination, duration, and categories from the sentence, then the existing four-stage pipeline plans the itinerary. The response format is identical to `/trips/plan`.

**Plan a trip (structured input — still the primary interface):**
```bash
curl -X POST http://localhost:8000/api/v1/trips/plan \
  -H "Content-Type: application/json" \
  -d '{
    "destination": "beijing",
    "duration_days": 3,
    "budget_level": "mid_range",
    "travel_pace": "moderate",
    "preferred_categories": ["history_culture", "food_dining"],
    "free_text_preferences": "我喜欢古建筑和本地小吃，不想排队"
  }'
```

**Plan a trip (legacy weight input — still supported):**
```bash
curl -X POST http://localhost:8000/api/v1/trips/plan \
  -H "Content-Type: application/json" \
  -d '{
    "destination": "beijing",
    "duration_days": 3,
    "budget_level": "mid_range",
    "travel_pace": "moderate",
    "interests": {"history_culture": 0.9, "food_dining": 0.6}
  }'
```

Interactive API docs: `http://localhost:8000/docs`

All response fields are populated. LLM-generated fields (`overview`, `narrative`, `recommendation_reason`) use template text in mock mode and real AI-generated text when an API key is configured.

The frontend presents itineraries with broad time blocks (Morning / Afternoon / Evening) instead of exact timestamps, formatted budget tier labels, and contextual hint chips derived from existing API fields (meal slot labels, rainy-day indoor picks, local atmosphere, photo-friendly spots).

Preference alignment ensures the final itinerary matches user intent: free-text signals like "less crowded" suppress shopping and entertainment POIs via a 0.25× score multiplier; unselected categories are additionally capped at one appearance per day regardless of their popularity or budget score.

The planner also enforces several scheduling constraints:
- POIs more than 40 km apart are never placed on the same day (e.g. Forbidden City and Great Wall go on different days).
- Per-leg travel time is capped at 1.5 h when using the Haversine fallback, preventing schedule overflow past midnight.
- At most 3 `food_dining` POIs are allocated per day, ensuring other preferred categories (e.g. `local_life`) always have representation.
- Meal POIs are distributed across breakfast (~09:00), lunch (~12:00), and dinner (~18:00) slots based on count, rather than all stacking at day's end.

---

## MVP Scope

The first version implements:

- Traveler request schema (destination, days, budget, pace, interests, constraints)
- Traveler persona / profile model
- POI model with scoring attributes
- Local JSON mock POI data (Beijing, Shanghai, Chengdu)
- POI filtering and scoring engine
- Day allocation algorithm (greedy + geographic clustering)
- Within-day route ordering (nearest-neighbour + meal slot rules)
- Weather forecast integration (mock)
- LLM itinerary text generation (mock provider by default)
- Single API endpoint: `POST /api/v1/trips/plan`
- Natural language input endpoint: `POST /api/v1/trips/plan-from-text` (Sprint 5.6)
- Health check endpoint: `GET /api/v1/health`

Not included in MVP:
- Authentication or user accounts
- Frontend UI
- Background jobs or async task queues
- Advanced database persistence (SQLite save is optional)
- Agent-based or conversational workflows

---

## Architecture Summary

The backend is organized into five layers:

| Layer | Location | Responsibility |
|-------|----------|----------------|
| API | `app/api/` | HTTP routing, request validation, response formatting |
| Services | `app/services/` | Main planning flow orchestration |
| Core | `app/core/` | Pure planning logic: persona, scoring, allocation, routing |
| Integrations | `app/integrations/` | External APIs: POI, Maps, Weather (each with mock + real impl) |
| LLM | `app/llm/` | Text generation abstraction (mock, OpenAI, Claude) |

All external services (POI data, maps, weather, LLM) follow the same pattern:

```
BaseXxxProvider (abstract)
    ├── MockXxxProvider    ← works without any API key
    └── RealXxxProvider    ← activated by setting key in .env
```

If a real provider is configured but unavailable, the system automatically falls back to mock.

---

## Folder Structure

```
intelligent-trip-planner/
├── README.md
├── requirements.txt
├── .env.example
├── .gitignore
├── main.py                          # FastAPI app entry point
│
├── app/
│   ├── config/
│   │   └── settings.py              # All configuration via pydantic-settings
│   │
│   ├── api/
│   │   ├── router.py                # Aggregates all route groups
│   │   └── v1/
│   │       ├── trips.py             # POST /api/v1/trips/plan  +  /plan-from-text (Sprint 5.6)
│   │       └── health.py            # GET  /api/v1/health
│   │
│   ├── schemas/
│   │   ├── common.py                # Enums: TravelPace, BudgetLevel, POICategory
│   │   ├── trip_request.py          # TripRequest, InterestWeights, TripConstraints
│   │   ├── persona.py               # TravelerPersona
│   │   ├── poi.py                   # POI, ScoredPOI, ScheduledPOI, ScoreBreakdown
│   │   ├── itinerary.py             # DayPlan, ItineraryResponse
│   │   └── nl_request.py            # NaturalLanguageTripRequest, ParsedTripInput (Sprint 5.6)
│   │
│   ├── core/
│   │   ├── persona_builder.py       # Builds TravelerPersona from TripRequest
│   │   ├── poi_scorer.py            # Scores POIs against persona
│   │   ├── day_allocator.py         # Assigns scored POIs across days
│   │   └── route_optimizer.py       # Orders POIs within each day
│   │
│   ├── services/
│   │   ├── trip_planner.py          # Orchestrates the full planning pipeline
│   │   ├── itinerary_builder.py     # Assembles final ItineraryResponse
│   │   └── nl_input_parser.py       # NL text → ParsedTripInput → TripRequest (Sprint 5.6)
│   │
│   ├── integrations/
│   │   ├── poi/
│   │   │   ├── base.py              # BasePOIProvider ABC
│   │   │   ├── mock_provider.py     # Reads local JSON files
│   │   │   ├── google_places.py     # Google Places Nearby Search + Place Details
│   │   │   └── poi_factory.py
│   │   ├── maps/
│   │   │   ├── base.py              # BaseMapsProvider ABC
│   │   │   ├── mock_provider.py     # Haversine straight-line distance
│   │   │   ├── google_maps.py       # Google Maps Distance Matrix + Geocoding
│   │   │   ├── amap.py              # Amap (高德) driving route + WGS84→GCJ02
│   │   │   └── maps_factory.py
│   │   └── weather/
│   │       ├── base.py              # BaseWeatherProvider ABC
│   │       ├── mock_provider.py     # Seasonal fixed forecast
│   │       ├── openweathermap.py    # OWM 5-day/3-hour forecast
│   │       └── weather_factory.py
│   │
│   ├── llm/
│   │   ├── base.py                  # BaseLLMProvider ABC (+ parse_natural_language_request)
│   │   ├── mock_provider.py         # Template-based text + regex NL parsing, no API key needed
│   │   ├── openai_provider.py       # OpenAI integration (JSON mode for NL parsing)
│   │   ├── claude_provider.py       # Anthropic Claude integration (fence-stripped JSON)
│   │   ├── prompt_templates.py      # All prompt strings (+ build_parse_trip_prompt)
│   │   └── llm_factory.py           # Selects provider from settings
│   │
│   ├── data/
│   │   └── mock/                    # Local JSON files for mock POI data
│   │       ├── beijing_pois.json
│   │       ├── shanghai_pois.json
│   │       └── chengdu_pois.json
│   │
│   └── db/
│       ├── database.py              # SQLAlchemy + SQLite setup
│       └── models.py                # ORM models for saved itineraries
│
└── tests/
    ├── test_persona_builder.py
    ├── test_poi_scorer.py
    ├── test_day_allocator.py
    ├── test_nl_input_parser.py      # Sprint 5.6: 36 NL parser tests
    ├── test_integrations/
    └── fixtures/
        └── sample_request.json
```

---

## Setup Instructions

### 1. Clone and enter the project

```bash
git clone <repo-url>
cd intelligent-trip-planner
```

### 2. Create a virtual environment

```bash
python -m venv venv
source venv/bin/activate        # macOS / Linux
venv\Scripts\activate           # Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment

```bash
cp .env.example .env
```

For MVP (no API keys), the defaults in `.env.example` are sufficient — all providers are set to `mock`.

### 5. Run the server

```bash
uvicorn main:app --reload
```

API is available at: `http://localhost:8000`

Interactive docs: `http://localhost:8000/docs`

### 6. Test the planning endpoint

```bash
curl -X POST http://localhost:8000/api/v1/trips/plan \
  -H "Content-Type: application/json" \
  -d '{
    "destination": "beijing",
    "duration_days": 3,
    "budget_level": "mid_range",
    "travel_pace": "moderate",
    "interests": {
      "history_culture": 0.9,
      "food_dining": 0.6,
      "nature_scenery": 0.4
    }
  }'
```

### 7. Run tests

```bash
pytest tests/ -v
```

---

## How Mock Mode Works

By default, all external services run in mock mode. No API keys are required.

| Provider | Mock behavior |
|----------|---------------|
| `POI_PROVIDER=mock` | Reads from `app/data/mock/{destination}_pois.json` |
| `MAPS_PROVIDER=mock` | Computes straight-line distance using Haversine formula |
| `WEATHER_PROVIDER=mock` | Returns seasonally-appropriate fixed forecast data |
| `LLM_PROVIDER=mock` | Generates overview, narratives, and POI reasons from Python templates; infers soft preferences via keyword matching |

To activate a real provider, set its key in `.env` and change its `_PROVIDER` variable:

```ini
# Switch to real weather data
WEATHER_PROVIDER=openweathermap
OPENWEATHERMAP_API_KEY=your_key_here

# Switch to real POI data
POI_PROVIDER=google_places
GOOGLE_PLACES_API_KEY=your_key_here

# Switch to real maps routing
MAPS_PROVIDER=google          # or: amap
GOOGLE_MAPS_API_KEY=your_key_here

# Switch to real LLM
LLM_PROVIDER=openai
OPENAI_API_KEY=your_key_here
```

If a real provider is configured but fails (e.g., key is invalid), the system logs a warning and falls back to the corresponding mock provider automatically.

---

## Planned Future Extensions

The following features are out of scope for the MVP but are supported by the current architecture:

- ~~**Real external API integration**~~ — Completed in Sprint 5 (Google Places, Google Maps, Amap, OpenWeatherMap, OpenAI, Claude)
- **Itinerary refinement** — `POST /api/v1/trips/{id}/refine` accepts user feedback and re-generates text
- **SQLite persistence** — save and retrieve past itineraries via `GET /api/v1/trips/{id}`
- **PostgreSQL migration** — the SQLAlchemy layer is already abstracted for this
- **Streaming response** — `POST /api/v1/trips/plan/stream` for progressive display
- **LangChain integration** — optionally wrap real LLM providers with LangChain for structured output parsing; the `BaseLLMProvider` interface remains unchanged
- **Multi-city trips** — extend `TripRequest` to support sequential destinations
- **Preference learning** — store feedback to improve persona weights over time
