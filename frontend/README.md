# Thesis Demo Frontend

A lightweight React + Vite frontend for the **Intelligent Trip Planning Assistant** thesis project.

## What this frontend covers

- Structured input mode → `POST /api/v1/trips/plan`
- Natural language input mode → `POST /api/v1/trips/plan-from-text`
- Backend health check → `GET /api/v1/health`
- Loading / error states
- Itinerary display for overview, persona summary, planning notes, daily plans, POIs, and weather

## Design intent

This frontend is intentionally small and presentation-focused:

- single-page thesis demo UI
- no login / auth / user system
- no chatbot metaphor
- no complex state management
- no over-engineering

## Run locally

From the project root:

```bash
cd frontend
npm install
npm run dev
```

By default the frontend calls:

```bash
http://localhost:8000/api/v1
```

If your backend is running somewhere else, create a `.env` file inside `frontend/`:

```bash
VITE_API_BASE_URL=http://localhost:8000/api/v1
```

## Production build

```bash
cd frontend
npm run build
```

## Suggested demo flow

1. Start the FastAPI backend (`uvicorn main:app --reload`)
2. Start the frontend (`npm run dev`)
3. Show backend health status
4. Demo a structured request
5. Demo a natural-language request
6. Walk through persona summary, overview, and per-day itinerary output
