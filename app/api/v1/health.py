"""
GET /api/v1/health

Returns the operational status of the application and each external provider.
Useful for checking which providers are running in mock vs real mode before
submitting a planning request.
"""

from fastapi import APIRouter
from pydantic import BaseModel

from app.config.settings import get_settings
from app.integrations.poi.poi_factory import create_poi_provider
from app.integrations.maps.maps_factory import create_maps_provider
from app.integrations.weather.weather_factory import create_weather_provider

router = APIRouter()


class ProviderStatus(BaseModel):
    name: str
    available: bool
    mode: str       # e.g. "mock" or "google_places"


class HealthResponse(BaseModel):
    status: str     # "ok"
    providers: dict[str, ProviderStatus]


@router.get("/health", response_model=HealthResponse, tags=["health"])
async def health_check() -> HealthResponse:
    """
    Check the health of all external provider integrations.

    ``available: true`` means the provider is configured and reachable.
    ``mode`` indicates whether it is running in mock or real mode.
    """
    settings = get_settings()

    poi      = create_poi_provider(settings)
    maps     = create_maps_provider(settings)
    weather  = create_weather_provider(settings)

    providers = {
        "poi": ProviderStatus(
            name=poi.provider_name,
            available=poi.is_available(),
            mode=settings.poi_provider,
        ),
        "maps": ProviderStatus(
            name=maps.provider_name,
            available=maps.is_available(),
            mode=settings.maps_provider,
        ),
        "weather": ProviderStatus(
            name=weather.provider_name,
            available=weather.is_available(),
            mode=settings.weather_provider,
        ),
        "llm": ProviderStatus(
            name=settings.llm_provider,
            available=True,             # LLM layer implemented in Sprint 4
            mode=settings.llm_provider,
        ),
    }

    return HealthResponse(status="ok", providers=providers)
