import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.config.settings import get_settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger(__name__)

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    description=(
        "Hybrid intelligent travel planning backend. "
        "Structured personalization logic + LLM-enhanced text generation."
    ),
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api")


@app.on_event("startup")
async def on_startup() -> None:
    logger.info("Starting %s", settings.app_name)
    logger.info(
        "Providers — LLM: %s | POI: %s | Maps: %s | Weather: %s",
        settings.llm_provider,
        settings.poi_provider,
        settings.maps_provider,
        settings.weather_provider,
    )


@app.on_event("shutdown")
async def on_shutdown() -> None:
    logger.info("Shutting down %s", settings.app_name)
