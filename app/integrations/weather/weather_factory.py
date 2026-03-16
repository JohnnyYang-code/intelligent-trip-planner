import logging

from app.config.settings import Settings
from app.integrations.weather.base import BaseWeatherProvider
from app.integrations.weather.mock_provider import MockWeatherProvider

logger = logging.getLogger(__name__)


def create_weather_provider(settings: Settings) -> BaseWeatherProvider:
    """
    Return the configured weather provider.

    Falls back to MockWeatherProvider when the configured provider is unavailable.
    """
    if settings.weather_provider == "openweathermap":
        try:
            from app.integrations.weather.openweathermap import OpenWeatherMapProvider  # noqa: PLC0415

            provider = OpenWeatherMapProvider(settings)
            if provider.is_available():
                logger.info("Weather provider: openweathermap")
                return provider
            logger.warning(
                "OpenWeatherMapProvider not available (missing API key?). "
                "Falling back to mock."
            )
        except ImportError:
            logger.warning("OpenWeatherMap provider module not found. Falling back to mock.")

    logger.info("Weather provider: mock")
    return MockWeatherProvider()
