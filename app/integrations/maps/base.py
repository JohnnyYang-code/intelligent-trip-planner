from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class Coordinates:
    latitude: float
    longitude: float


@dataclass
class DistanceResult:
    distance_km: float
    duration_minutes: float     # estimated travel time


class BaseMapsProvider(ABC):
    """
    Abstract interface for map and routing services.

    MVP implementation: MockMapsProvider (Haversine straight-line distance).
    Future implementations: GoogleMapsProvider, AmapProvider.
    """

    @abstractmethod
    def get_distance(
        self,
        origin: Coordinates,
        destination: Coordinates,
    ) -> DistanceResult:
        """
        Return the distance and estimated travel time between two points.

        The mock uses straight-line Haversine distance with a fixed walking speed.
        Real providers call the Distance Matrix API for actual road distance.
        """
        ...

    @abstractmethod
    async def geocode(self, address: str) -> Coordinates | None:
        """
        Convert an address string to coordinates.
        Returns None if the address cannot be resolved.
        """
        ...

    @abstractmethod
    def is_available(self) -> bool:
        ...

    @property
    @abstractmethod
    def provider_name(self) -> str:
        ...
