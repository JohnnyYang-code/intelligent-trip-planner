from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ───────────────────────────────────────────────────────────
    app_name: str = "Intelligent Trip Planner"
    debug: bool = False

    # ── LLM ───────────────────────────────────────────────────────────────────
    llm_provider: Literal["mock", "openai", "claude"] = "mock"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    anthropic_api_key: str = ""
    claude_model: str = "claude-3-5-haiku-20241022"

    # ── Maps ──────────────────────────────────────────────────────────────────
    maps_provider: Literal["mock", "google", "amap"] = "mock"
    google_maps_api_key: str = ""
    amap_api_key: str = ""

    # ── POI ───────────────────────────────────────────────────────────────────
    poi_provider: Literal["mock", "google_places"] = "mock"
    google_places_api_key: str = ""

    # ── Weather ───────────────────────────────────────────────────────────────
    weather_provider: Literal["mock", "openweathermap"] = "mock"
    openweathermap_api_key: str = ""

    # ── Database ──────────────────────────────────────────────────────────────
    database_url: str = "sqlite:///./trip_planner.db"

    # ── Scoring weights ───────────────────────────────────────────────────────
    score_weight_interest: float = 0.55
    score_weight_popularity: float = 0.25
    score_weight_budget: float = 0.20

    # ── Planning parameters ───────────────────────────────────────────────────
    daily_hours_budget: float = 8.0
    transport_buffer_minutes: int = 15


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
