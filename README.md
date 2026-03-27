# Intelligent Trip Planner

A personalized multi-day travel itinerary generator powered by a deterministic planning pipeline and LLM-enhanced output. Built as a full-stack prototype with a React frontend and FastAPI backend.

---

## Overview

Most trip planners either demand too much manual configuration or produce generic AI outputs. This project takes a different approach:

> **Structured logic drives every planning decision. LLMs only handle language — not strategy.**

The result is an itinerary that is explainable, preference-aware, and does not rely on a black-box model to make scheduling choices.

---

## Architecture

```
Natural Language Input (optional)
        ↓
  LLM Input Parser          — extracts structured fields from free text
        ↓
   TripRequest              — destination, days, budget, pace, interests
        ↓
 Stage 1: PersonaBuilder    — builds traveler profile from preferences
        ↓
 Stage 2: POI Scorer        — scores candidates (interest × popularity × budget)
        ↓
 Stage 3: Day Allocator     — assigns POIs across days (weather-aware, geographically clustered)
        ↓
 Stage 4: Route Optimizer   — reorders POIs within each day (nearest-neighbor)
        ↓
  LLM Text Generation       — adds narrative, reasons, tips, and overview
        ↓
  ItineraryResponse         — final structured JSON output
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.11+, FastAPI, Uvicorn |
| Validation | Pydantic v2, pydantic-settings |
| Frontend | React 19, TypeScript, Vite, Tailwind CSS 4 |
| LLM Providers | OpenAI, Anthropic Claude, Mock (template-based) |
| Maps Providers | Google Maps, Amap (高德), Mock (Haversine) |
| POI Providers | Google Places, Mock (local JSON) |
| Weather Providers | OpenWeatherMap, Mock (seasonal fixed) |
| Database | SQLAlchemy + SQLite (async via aiosqlite) |
| Testing | pytest, pytest-asyncio |

---

## Features

- **Dual input modes** — structured form or free-text natural language
- **Persona-driven scoring** — interests weighted 55%, popularity 25%, budget fit 20%
- **Explicit preference enforcement** — categories not selected by the user receive a 0.40× score penalty, preventing popular-but-unselected venues (e.g. shopping malls) from outscoring preferred ones via popularity/budget alone
- **Soft preference support** — "avoid crowds" → 0.25× multiplier on shopping/entertainment; stacks with the preference penalty
- **Accommodation filtering** — hotels and serviced apartments are excluded at the provider boundary and never appear as itinerary stops
- **Weather-aware scheduling** — indoor POIs prioritized on rainy days
- **Geographic clustering** — prevents >40 km same-day travel
- **Food slot distribution** — breakfast, lunch, and dinner spread across each day
- **Mock mode** — full offline operation without any API keys
- **Bilingual support** — English and Chinese input/output

---

## Prompt Design

All prompts live in `app/llm/prompt_templates.py`. The system uses 5 purpose-specific prompts, each tightly scoped to a single task:

| Prompt | Purpose | Max tokens |
|---|---|---|
| `build_parse_trip_prompt` | Extract structured fields (destination, dates, budget, pace, categories) from free-text input | 350 |
| `build_soft_preference_prompt` | Convert free-text preferences to snake_case tags (e.g. `avoid_crowds`, `vegetarian_food`) | 80 |
| `build_overview_prompt` | Generate a 2–3 sentence trip introduction after planning completes | 200 |
| `build_day_narrative_prompt` | Generate a 2–3 sentence weather-aware summary per day | 150 |
| `build_poi_reason_prompt` | Generate a single recommendation sentence per POI (≤40 chars) | 60 |

**Design principles:**

- **Strict output contracts** — every prompt specifies exact format, length, and what to omit (e.g. "no bullets", "one sentence only", "return empty string if nothing found"). This keeps downstream parsing simple and predictable.
- **LLM as narrator, not planner** — the first two prompts run before scoring (to enrich the input), the last three run after the 4-stage pipeline (to describe its output). The LLM never decides which POIs to include or how to schedule them.
- **Minimal token budgets** — each prompt is sized to its task; POI reasons get 60 tokens, full trip parsing gets 350. This keeps latency low and forces concise outputs.
- **Provider differences handled at the call site** — OpenAI uses native `json_object` mode for structured outputs; Claude responses are post-processed with regex to strip markdown fences before JSON parsing.

---

## Quick Start

### Backend

```bash
# Create and activate virtual environment
python -m venv venv
source venv/bin/activate       # macOS/Linux
# venv\Scripts\activate        # Windows

# Install dependencies
pip install -r requirements.txt

# Configure environment (optional — mock mode works without API keys)
cp .env.example .env

# Start the server
uvicorn main:app --reload
# → http://localhost:8000
# → http://localhost:8000/docs  (Swagger UI)
```

### Frontend

```bash
cd frontend
npm install
npm run dev
# → http://localhost:5173
```

### Tests

```bash
pytest tests/ -v
```

---

## Configuration

All settings are controlled via `.env`. The project runs fully in **mock mode** by default — no API keys required.

```ini
# LLM Provider: mock | openai | claude
LLM_PROVIDER=mock
OPENAI_API_KEY=
ANTHROPIC_API_KEY=

# Maps Provider: mock | google | amap
MAPS_PROVIDER=mock
GOOGLE_MAPS_API_KEY=
AMAP_API_KEY=

# POI Provider: mock | google_places
POI_PROVIDER=mock
GOOGLE_PLACES_API_KEY=

# Weather Provider: mock | openweathermap
WEATHER_PROVIDER=mock
OPENWEATHERMAP_API_KEY=

# Scoring weights (must sum to 1.0)
SCORE_WEIGHT_INTEREST=0.55
SCORE_WEIGHT_POPULARITY=0.25
SCORE_WEIGHT_BUDGET=0.20
```

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/trips/plan` | Plan a trip from a structured request |
| `POST` | `/api/v1/trips/plan-from-text` | Plan a trip from natural language |
| `GET` | `/api/v1/health` | Backend and provider status |

Interactive docs available at `/docs` (Swagger) and `/redoc` (ReDoc).

---

## Project Structure

```
intelligent-trip-planner/
├── main.py                        # FastAPI entry point
├── requirements.txt
├── .env.example
│
├── app/
│   ├── api/v1/                    # Route handlers
│   ├── core/                      # Deterministic planning logic
│   │   ├── persona_builder.py
│   │   ├── poi_scorer.py
│   │   ├── day_allocator.py
│   │   └── route_optimizer.py
│   ├── services/                  # Orchestration layer
│   ├── integrations/              # POI, Maps, Weather providers
│   ├── llm/                       # LLM providers and prompt templates
│   ├── schemas/                   # Pydantic models
│   └── data/mock/                 # Local POI data (Beijing, Shanghai, Chengdu)
│
├── frontend/
│   └── src/
│       ├── App.tsx
│       ├── api.ts
│       └── types.ts
│
└── tests/                         # 141 tests across all core modules
```

---

## Done

**Core pipeline**
- [x] Deterministic 4-stage planning pipeline (PersonaBuilder → POIScorer → DayAllocator → RouteOptimizer)
- [x] Preference enforcement with stacking soft penalties (e.g. avoid_crowds ×0.25, unselected category ×0.40)
- [x] Weather-aware scheduling and geographic clustering (≤40 km same-day travel)
- [x] 141 unit tests across all core modules

**LLM integration** (`app/llm/`)
- [x] Natural language trip request parsing — extracts destination, dates, budget, pace, and categories from free text
- [x] Soft preference inference — converts free-text preferences to structured tags before scoring
- [x] Post-planning text generation: trip overview, per-day narratives, per-POI recommendation reasons
- [x] LLM runs entirely after the 4-stage pipeline — narrates decisions, never makes them
- [x] Parallel async generation via `asyncio.gather` (overview + day narratives + POI reasons)
- [x] Dual provider support: Claude (Anthropic SDK, manual JSON extraction) and OpenAI (native `json_object` mode)

**External APIs** (`app/integrations/`)
- [x] **Google Places** — geocoding + nearby search per category (60 candidates, 15 km radius); log-normalized popularity scores
- [x] **Google Maps / Amap** — driving distance matrix for route optimization; Amap includes WGS-84 → GCJ-02 coordinate conversion
- [x] **OpenWeatherMap** — 5-day/3-hour forecast with noon-slot sampling; condition → travel advisory mapping
- [x] **Anthropic API** — `claude-3-5-haiku-20241022`
- [x] **OpenAI API** — `gpt-4o-mini`

**Frontend & DX**
- [x] React 19 + TypeScript + Tailwind CSS 4 frontend
- [x] Dual input modes: structured form and natural language
- [x] Bilingual support (English and Chinese)

---

## To Do

**POI Scorer improvements**
- [ ] Opening hours awareness — filter or penalize POIs closed on the scheduled travel day/time slot
- [ ] Time-of-day scoring — boost category weights by time (e.g. parks at sunrise, dining in evenings)
- [ ] Category diversity cap — penalize scheduling the same category more than N times per day
- [ ] Seasonal popularity adjustment — scale `popularity_score` by month (e.g. outdoor venues in summer)
- [ ] Dynamic crowding model — use day-of-week and holiday calendar to adjust `avoid_crowds` multiplier

**Itinerary realism**
- [ ] Real travel time in DayAllocator — replace Haversine straight-line estimate with actual Maps API driving/transit time
- [ ] Rest buffer insertion — add pace-dependent gaps between POIs (e.g. relaxed pace → 20 min buffer)
- [ ] Meal slot pinning — hard-constrain breakfast/lunch/dinner to realistic time windows
- [ ] Visit duration variability — adjust estimated duration by group size, pace, and POI type
- [ ] Reservation flags — identify POIs requiring advance booking and surface warnings in itinerary output

---

## Blockers

- **Itinerary realism gap** *(main)* — the pipeline has no awareness of actual visit durations, real travel times between POIs, or opening hour constraints; generated schedules can exceed what's physically doable in a day
- **Travel time is a straight-line estimate** — DayAllocator uses Haversine distance with a fixed speed; actual driving/transit time in dense cities is 2–3× longer, making "feasible" days infeasible in practice
- **No opening hours in POI data** — Google Places nearby search doesn't fetch `opening_hours` in the current implementation; POIs get scheduled regardless of whether they're actually open
- **Flat cost estimates per category** — budget scoring uses hardcoded CNY values per category (e.g. all food_dining at ¥120) instead of POI-level price data, making budget fit scores unreliable
- **POI candidate pool is small and static** — only 60 candidates fetched from Google Places; when early candidates are filtered out by constraints, no re-ranking or pool expansion occurs, leading to thin days for niche preferences
- **Claude has no native JSON mode** — OpenAI's `json_object` mode guarantees valid JSON; Claude requires manual regex stripping of markdown fences, which can silently fail on edge cases in the NL parser

---

## Mock Data

Mock mode ships with POI data for three cities:

- Beijing (北京)
- Shanghai (上海)
- Chengdu (成都)

To use real providers, set the corresponding `*_PROVIDER` env var and supply the API key.
