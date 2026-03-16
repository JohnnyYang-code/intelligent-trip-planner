from abc import ABC, abstractmethod

from app.schemas.poi import POI


class BasePOIProvider(ABC):
    """
    Abstract interface for POI data sources.

    MVP implementation: MockPOIProvider (reads local JSON files).
    Future implementation: GooglePlacesPOIProvider.

    The provider returns raw POI candidates. All filtering and scoring
    are handled by the core planning modules, not here.
    """

    @abstractmethod
    async def search_pois(self, destination: str, limit: int = 60) -> list[POI]:
        """
        Return POI candidates for the given destination.

        Args:
            destination: Normalised city key, e.g. "beijing".
            limit: Maximum number of results to return.

        Returns:
            List of POI objects, unscored and unfiltered.
        """
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """Return True if this provider is properly configured and can serve requests."""
        ...

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Human-readable name shown in health checks and logs."""
        ...
