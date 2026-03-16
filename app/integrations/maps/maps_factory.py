import logging

from app.config.settings import Settings
from app.integrations.maps.base import BaseMapsProvider
from app.integrations.maps.mock_provider import MockMapsProvider

logger = logging.getLogger(__name__)


def create_maps_provider(settings: Settings) -> BaseMapsProvider:
    """
    Return the configured maps provider.

    Falls back to MockMapsProvider when the configured provider is unavailable.
    """
    if settings.maps_provider == "google":
        try:
            from app.integrations.maps.google_maps import GoogleMapsProvider  # noqa: PLC0415

            provider = GoogleMapsProvider(settings)
            if provider.is_available():
                logger.info("Maps provider: google")
                return provider
            logger.warning("GoogleMapsProvider not available. Falling back to mock.")
        except ImportError:
            logger.warning("googlemaps package not installed. Falling back to mock maps provider.")

    elif settings.maps_provider == "amap":
        try:
            from app.integrations.maps.amap import AmapProvider  # noqa: PLC0415

            provider = AmapProvider(settings)
            if provider.is_available():
                logger.info("Maps provider: amap")
                return provider
            logger.warning("AmapProvider not available. Falling back to mock.")
        except ImportError:
            logger.warning("Amap provider module not found. Falling back to mock maps provider.")

    logger.info("Maps provider: mock")
    return MockMapsProvider()
