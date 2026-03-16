import math

from app.integrations.maps.base import BaseMapsProvider, Coordinates, DistanceResult

# Average walking speed used for travel-time estimation.
_WALKING_SPEED_KMH = 4.0


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return the great-circle distance in kilometres between two WGS-84 points."""
    r = 6371.0  # Earth radius in km
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)

    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


class MockMapsProvider(BaseMapsProvider):
    """
    Estimates distance using straight-line Haversine formula.

    Travel time is derived from distance ÷ walking speed. This is an
    approximation; real-road distance is typically 20–40 % longer.
    """

    def get_distance(
        self,
        origin: Coordinates,
        destination: Coordinates,
    ) -> DistanceResult:
        dist_km = haversine_km(
            origin.latitude, origin.longitude,
            destination.latitude, destination.longitude,
        )
        duration_minutes = (dist_km / _WALKING_SPEED_KMH) * 60.0
        return DistanceResult(distance_km=dist_km, duration_minutes=duration_minutes)

    async def geocode(self, address: str) -> Coordinates | None:
        # Mock: no geocoding capability; return None.
        return None

    def is_available(self) -> bool:
        return True

    @property
    def provider_name(self) -> str:
        return "mock"
