import logging

from app.config.settings import Settings
from app.integrations.poi.base import BasePOIProvider
from app.integrations.poi.mock_provider import MockPOIProvider

logger = logging.getLogger(__name__)


def create_poi_provider(settings: Settings) -> BasePOIProvider:
    """
    Return the configured POI provider.

    Falls back to MockPOIProvider when:
    - settings.poi_provider == "mock"
    - the configured real provider is not available (missing API key)
    """
    if settings.poi_provider == "google_places":
        # Import lazily so the module doesn't fail if googlemaps isn't installed.
        try:
            from app.integrations.poi.google_places import GooglePlacesPOIProvider  # noqa: PLC0415

            provider = GooglePlacesPOIProvider(settings)
            if provider.is_available():
                logger.info("POI provider: google_places")
                return provider
            logger.warning(
                "GooglePlacesPOIProvider is not available (missing API key?). "
                "Falling back to mock."
            )
        except ImportError:
            logger.warning(
                "googlemaps package not installed. Falling back to mock POI provider."
            )

    logger.info("POI provider: mock")
    return MockPOIProvider()
