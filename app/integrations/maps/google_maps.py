"""
Google Maps provider.

Uses the `googlemaps` Python SDK to call:
- Distance Matrix API  (driving travel time between two coordinates)
- Geocoding API        (address → coordinates)
"""

import logging

from app.integrations.maps.base import BaseMapsProvider, Coordinates, DistanceResult

logger = logging.getLogger(__name__)


class GoogleMapsProvider(BaseMapsProvider):
    """
    Real maps provider backed by Google Maps APIs.

    Requires MAPS_PROVIDER=google and GOOGLE_MAPS_API_KEY set in .env.
    """

    def __init__(self, settings) -> None:
        self._api_key: str = settings.google_maps_api_key
        self._client = None

    def _get_client(self):
        if self._client is None:
            import googlemaps  # lazy import — safe if package is absent
            self._client = googlemaps.Client(key=self._api_key)
        return self._client

    def is_available(self) -> bool:
        return bool(self._api_key)

    @property
    def provider_name(self) -> str:
        return "google_maps"

    def get_distance(
        self,
        origin: Coordinates,
        destination: Coordinates,
    ) -> DistanceResult:
        client = self._get_client()
        result = client.distance_matrix(
            origins=[(origin.latitude, origin.longitude)],
            destinations=[(destination.latitude, destination.longitude)],
            mode="driving",
            units="metric",
        )

        element = result["rows"][0]["elements"][0]
        if element["status"] != "OK":
            raise ValueError(f"Distance Matrix returned status: {element['status']}")

        distance_m = element["distance"]["value"]
        duration_s = element["duration"]["value"]

        return DistanceResult(
            distance_km=distance_m / 1000.0,
            duration_minutes=duration_s / 60.0,
        )

    async def geocode(self, address: str) -> Coordinates | None:
        try:
            client = self._get_client()
            results = client.geocode(address)
            if not results:
                return None
            loc = results[0]["geometry"]["location"]
            return Coordinates(latitude=loc["lat"], longitude=loc["lng"])
        except Exception as exc:
            logger.warning("Google geocode failed for %r: %s", address, exc)
            return None
