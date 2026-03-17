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
- **Soft preference support** — "avoid crowds" → 0.25× multiplier on shopping/entertainment
- **Weather-aware scheduling** — indoor POIs prioritized on rainy days
- **Geographic clustering** — prevents >40 km same-day travel
- **Food slot distribution** — breakfast, lunch, and dinner spread across each day
- **Mock mode** — full offline operation without any API keys
- **Bilingual support** — English and Chinese input/output

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
└── tests/                         # 133 tests across all core modules
```

---

## Mock Data

Mock mode ships with POI data for three cities:

- Beijing (北京)
- Shanghai (上海)
- Chengdu (成都)

To use real providers, set the corresponding `*_PROVIDER` env var and supply the API key.
