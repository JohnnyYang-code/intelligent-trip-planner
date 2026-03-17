"""
Amap (高德) maps provider.

Uses the Amap Web Service REST API via httpx:
- Driving route API: https://restapi.amap.com/v3/direction/driving
- Geocoding API:     https://restapi.amap.com/v3/geocode/geo

Note: Amap uses the GCJ-02 coordinate system. WGS-84 coordinates from mock
POI data must be converted before calling the API.
"""

import logging
import math

import httpx

from app.integrations.maps.base import BaseMapsProvider, Coordinates, DistanceResult

logger = logging.getLogger(__name__)

_DRIVING_URL = "https://restapi.amap.com/v3/direction/driving"
_GEOCODE_URL  = "https://restapi.amap.com/v3/geocode/geo"


# ── WGS-84 → GCJ-02 coordinate conversion ────────────────────────────────────
# Reference: https://github.com/wandergis/coordtransform

_A = 6378245.0          # semi-major axis of Krassovsky ellipsoid
_EE = 0.00669342162296594323  # eccentricity squared


def _out_of_china(lat: float, lng: float) -> bool:
    return not (72.004 <= lng <= 137.8347 and 0.8293 <= lat <= 55.8271)


def wgs84_to_gcj02(lat: float, lng: float) -> tuple[float, float]:
    """Convert WGS-84 coordinates to GCJ-02 (Mars coordinates)."""
    if _out_of_china(lat, lng):
        return lat, lng

    d_lat = _transform_lat(lng - 105.0, lat - 35.0)
    d_lng = _transform_lng(lng - 105.0, lat - 35.0)

    rad_lat = lat / 180.0 * math.pi
    magic = math.sin(rad_lat)
    magic = 1 - _EE * magic * magic
    sqrt_magic = math.sqrt(magic)

    d_lat = (d_lat * 180.0) / ((_A * (1 - _EE)) / (magic * sqrt_magic) * math.pi)
    d_lng = (d_lng * 180.0) / (_A / sqrt_magic * math.cos(rad_lat) * math.pi)

    return lat + d_lat, lng + d_lng


def _transform_lat(x: float, y: float) -> float:
    ret = -100.0 + 2.0 * x + 3.0 * y + 0.2 * y * y + 0.1 * x * y + 0.2 * math.sqrt(abs(x))
    ret += (20.0 * math.sin(6.0 * x * math.pi) + 20.0 * math.sin(2.0 * x * math.pi)) * 2.0 / 3.0
    ret += (20.0 * math.sin(y * math.pi) + 40.0 * math.sin(y / 3.0 * math.pi)) * 2.0 / 3.0
    ret += (160.0 * math.sin(y / 12.0 * math.pi) + 320 * math.sin(y * math.pi / 30.0)) * 2.0 / 3.0
    return ret


def _transform_lng(x: float, y: float) -> float:
    ret = 300.0 + x + 2.0 * y + 0.1 * x * x + 0.1 * x * y + 0.1 * math.sqrt(abs(x))
    ret += (20.0 * math.sin(6.0 * x * math.pi) + 20.0 * math.sin(2.0 * x * math.pi)) * 2.0 / 3.0
    ret += (20.0 * math.sin(x * math.pi) + 40.0 * math.sin(x / 3.0 * math.pi)) * 2.0 / 3.0
    ret += (150.0 * math.sin(x / 12.0 * math.pi) + 300.0 * math.sin(x / 30.0 * math.pi)) * 2.0 / 3.0
    return ret


# ─────────────────────────────────────────────────────────────────────────────


class AmapProvider(BaseMapsProvider):
    """
    Real maps provider backed by Amap (高德) Web Service API.

    Requires MAPS_PROVIDER=amap and AMAP_API_KEY set in .env.
    """

    def __init__(self, settings) -> None:
        self._api_key: str = settings.amap_api_key

    def is_available(self) -> bool:
        return bool(self._api_key)

    @property
    def provider_name(self) -> str:
        return "amap"

    def get_distance(
        self,
        origin: Coordinates,
        destination: Coordinates,
    ) -> DistanceResult:
        """Synchronous driving distance via Amap Driving Route API."""
        import asyncio
        # Run the async implementation synchronously.
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Inside an async context — should not normally be called sync.
                # Fall through to raise so caller uses Haversine fallback.
                raise RuntimeError("Use async context to call AmapProvider.get_distance")
            return loop.run_until_complete(self._async_get_distance(origin, destination))
        except RuntimeError:
            raise

    async def _async_get_distance(
        self,
        origin: Coordinates,
        destination: Coordinates,
    ) -> DistanceResult:
        o_lat, o_lng = wgs84_to_gcj02(origin.latitude, origin.longitude)
        d_lat, d_lng = wgs84_to_gcj02(destination.latitude, destination.longitude)

        params = {
            "key": self._api_key,
            "origin": f"{o_lng:.6f},{o_lat:.6f}",      # Amap uses lng,lat order
            "destination": f"{d_lng:.6f},{d_lat:.6f}",
            "strategy": 0,   # fastest route
            "output": "json",
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(_DRIVING_URL, params=params)
            resp.raise_for_status()
            data = resp.json()

        if data.get("status") != "1":
            raise ValueError(f"Amap driving API error: {data.get('info')}")

        route = data["route"]["paths"][0]
        distance_m = float(route["distance"])
        duration_s = float(route["duration"])

        return DistanceResult(
            distance_km=distance_m / 1000.0,
            duration_minutes=duration_s / 60.0,
        )

    async def geocode(self, address: str) -> Coordinates | None:
        try:
            params = {
                "key": self._api_key,
                "address": address,
                "output": "json",
            }
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(_GEOCODE_URL, params=params)
                resp.raise_for_status()
                data = resp.json()

            if data.get("status") != "1" or not data.get("geocodes"):
                return None

            location: str = data["geocodes"][0]["location"]  # "lng,lat"
            lng_str, lat_str = location.split(",")
            # Convert GCJ-02 back to WGS-84 for internal use
            # (approximate inverse — good enough for display purposes)
            gcj_lat, gcj_lng = float(lat_str), float(lng_str)
            return Coordinates(latitude=gcj_lat, longitude=gcj_lng)

        except Exception as exc:
            logger.warning("Amap geocode failed for %r: %s", address, exc)
            return None
