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
User Input
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

**The LLM does not plan the trip. It narrates it.**

The structured pipeline decides:
- which POIs to include
- how many per day
- in what order
- with what time estimates

The LLM is responsible for:
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
| Sprint 4 | LLM layer (`base`, mock, OpenAI/Claude providers, prompt templates) · narrative generation | Planned |
| Sprint 5 | Real external API implementations (Google Places, Maps, Amap, OpenWeatherMap) | Planned |
| Sprint 6 | SQLite persistence · `GET /trips/{id}` endpoint | Planned |

### What works right now (Sprint 3)

The server is fully runnable. Start it and use any HTTP client:

```bash
uvicorn main:app --reload
```

**Health check:**
```bash
curl http://localhost:8000/api/v1/health
```

**Plan a trip:**
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

LLM-generated fields (`overview`, `narrative`, `tips`, `recommendation_reason`) are empty strings until Sprint 4.

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
│   │       ├── trips.py             # POST /api/v1/trips/plan
│   │       └── health.py            # GET  /api/v1/health
│   │
│   ├── schemas/
│   │   ├── common.py                # Enums: TravelPace, BudgetLevel, POICategory
│   │   ├── trip_request.py          # TripRequest, InterestWeights, TripConstraints
│   │   ├── persona.py               # TravelerPersona
│   │   ├── poi.py                   # POI, ScoredPOI, ScheduledPOI, ScoreBreakdown
│   │   └── itinerary.py             # DayPlan, ItineraryResponse
│   │
│   ├── core/
│   │   ├── persona_builder.py       # Builds TravelerPersona from TripRequest
│   │   ├── poi_scorer.py            # Scores POIs against persona
│   │   ├── day_allocator.py         # Assigns scored POIs across days
│   │   └── route_optimizer.py       # Orders POIs within each day
│   │
│   ├── services/
│   │   ├── trip_planner.py          # Orchestrates the full planning pipeline
│   │   └── itinerary_builder.py     # Assembles final ItineraryResponse
│   │
│   ├── integrations/
│   │   ├── poi/                     # POI data source (mock JSON / Google Places)
│   │   ├── maps/                    # Distance & routing (mock Haversine / Google Maps / Amap)
│   │   └── weather/                 # Weather forecast (mock / OpenWeatherMap)
│   │
│   ├── llm/
│   │   ├── base.py                  # BaseLLMProvider ABC
│   │   ├── mock_provider.py         # Template-based text, no API key needed
│   │   ├── openai_provider.py       # OpenAI integration
│   │   ├── claude_provider.py       # Anthropic Claude integration
│   │   ├── prompt_templates.py      # All prompt strings
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
| `LLM_PROVIDER=mock` | Generates itinerary text from Python string templates |

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

- **Real external API integration** — Google Places, Google Maps / Amap, OpenWeatherMap, OpenAI / Claude
- **Itinerary refinement** — `POST /api/v1/trips/{id}/refine` accepts user feedback and re-generates text
- **SQLite persistence** — save and retrieve past itineraries via `GET /api/v1/trips/{id}`
- **PostgreSQL migration** — the SQLAlchemy layer is already abstracted for this
- **Streaming response** — `POST /api/v1/trips/plan/stream` for progressive display
- **LangChain integration** — optionally wrap real LLM providers with LangChain for structured output parsing; the `BaseLLMProvider` interface remains unchanged
- **Multi-city trips** — extend `TripRequest` to support sequential destinations
- **Preference learning** — store feedback to improve persona weights over time
