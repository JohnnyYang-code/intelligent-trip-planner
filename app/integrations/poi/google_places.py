"""
Google Places POI provider.

Uses the `googlemaps` Python SDK to call:
- Nearby Search    (find POIs near city centre by category)
- Place Details    (enrich each result with opening hours, price level, etc.)

Score mapping
-------------
- rating (0–5)          → quality_score (×2 → 0–10)
- user_ratings_total    → popularity_score (log-normalised to 0–10)
- price_level (0–4)     → BudgetLevel + avg_cost_cny estimate
"""

import logging
import math
from typing import Optional

from app.integrations.poi.base import BasePOIProvider
from app.schemas.common import BudgetLevel, POICategory
from app.schemas.poi import POI

logger = logging.getLogger(__name__)

# Map Google Places types → internal POICategory (first match wins).
_TYPE_MAP: list[tuple[str, POICategory]] = [
    ("museum",                  POICategory.art_museum),
    ("art_gallery",             POICategory.art_museum),
    ("tourist_attraction",      POICategory.history_culture),
    ("place_of_worship",        POICategory.history_culture),
    ("cemetery",                POICategory.history_culture),
    ("park",                    POICategory.nature_scenery),
    ("natural_feature",         POICategory.nature_scenery),
    ("campground",              POICategory.nature_scenery),
    ("restaurant",              POICategory.food_dining),
    ("cafe",                    POICategory.food_dining),
    ("bar",                     POICategory.food_dining),
    ("food",                    POICategory.food_dining),
    ("bakery",                  POICategory.food_dining),
    ("meal_takeaway",           POICategory.food_dining),
    ("shopping_mall",           POICategory.shopping),
    ("store",                   POICategory.shopping),
    ("clothing_store",          POICategory.shopping),
    ("amusement_park",          POICategory.entertainment),
    ("bowling_alley",           POICategory.entertainment),
    ("movie_theater",           POICategory.entertainment),
    ("night_club",              POICategory.entertainment),
    ("stadium",                 POICategory.entertainment),
    ("zoo",                     POICategory.entertainment),
    ("aquarium",                POICategory.entertainment),
    ("market",                  POICategory.local_life),
    ("library",                 POICategory.local_life),
    ("city_hall",               POICategory.local_life),
]

# Estimated avg cost in CNY per price_level tier (0=free, 4=very expensive).
_PRICE_LEVEL_CNY = {0: 0, 1: 50, 2: 150, 3: 400, 4: 800}
_PRICE_LEVEL_BUDGET = {
    0: BudgetLevel.budget,
    1: BudgetLevel.budget,
    2: BudgetLevel.mid_range,
    3: BudgetLevel.luxury,
    4: BudgetLevel.luxury,
}

# Typical visit durations per category (hours).
_CATEGORY_DURATION: dict[POICategory, float] = {
    POICategory.history_culture: 2.0,
    POICategory.nature_scenery:  2.5,
    POICategory.food_dining:     1.5,
    POICategory.shopping:        1.5,
    POICategory.art_museum:      1.5,
    POICategory.entertainment:   2.0,
    POICategory.local_life:      1.0,
}

# Nearby Search radius in metres per category search.
_SEARCH_RADIUS_M = 15_000

# Google Places type keywords used for each category Nearby Search.
_CATEGORY_SEARCH_TYPES: dict[POICategory, str] = {
    POICategory.history_culture: "tourist_attraction",
    POICategory.nature_scenery:  "park",
    POICategory.food_dining:     "restaurant",
    POICategory.shopping:        "shopping_mall",
    POICategory.art_museum:      "museum",
    POICategory.entertainment:   "amusement_park",
    POICategory.local_life:      "market",
}

# Indoor flag heuristics by Google type.
_INDOOR_TYPES = {
    "museum", "art_gallery", "shopping_mall", "store", "clothing_store",
    "movie_theater", "bowling_alley", "aquarium", "library", "restaurant",
    "cafe", "bar", "bakery", "meal_takeaway", "night_club",
}


class GooglePlacesPOIProvider(BasePOIProvider):
    """
    Fetches real POI candidates from Google Places API.

    Requires POI_PROVIDER=google_places and GOOGLE_PLACES_API_KEY set in .env.
    """

    def __init__(self, settings) -> None:
        self._api_key: str = settings.google_places_api_key
        self._client = None

    def _get_client(self):
        if self._client is None:
            import googlemaps  # lazy import
            self._client = googlemaps.Client(key=self._api_key)
        return self._client

    def is_available(self) -> bool:
        return bool(self._api_key)

    @property
    def provider_name(self) -> str:
        return "google_places"

    async def search_pois(self, destination: str, limit: int = 60) -> list[POI]:
        try:
            return await self._fetch_pois(destination, limit)
        except Exception as exc:
            logger.warning("Google Places search failed for %s: %s", destination, exc)
            return []

    async def _fetch_pois(self, destination: str, limit: int) -> list[POI]:
        client = self._get_client()

        # Step 1: Geocode the city centre.
        geo_results = client.geocode(destination)
        if not geo_results:
            raise ValueError(f"Cannot geocode destination: {destination!r}")

        centre = geo_results[0]["geometry"]["location"]
        location = (centre["lat"], centre["lng"])

        # Step 2: Nearby Search per category.
        pois: list[POI] = []
        seen_place_ids: set[str] = set()
        per_category = max(1, limit // len(_CATEGORY_SEARCH_TYPES))

        for category, gtype in _CATEGORY_SEARCH_TYPES.items():
            try:
                results = client.places_nearby(
                    location=location,
                    radius=_SEARCH_RADIUS_M,
                    type=gtype,
                )
                candidates = results.get("results", [])[:per_category]

                for place in candidates:
                    place_id = place.get("place_id", "")
                    if place_id in seen_place_ids:
                        continue
                    seen_place_ids.add(place_id)

                    poi = _place_to_poi(place, destination, category)
                    if poi is not None:
                        pois.append(poi)

            except Exception as exc:
                logger.warning("Nearby search for %s/%s failed: %s", destination, gtype, exc)

        logger.debug("Google Places: fetched %d POIs for %s", len(pois), destination)
        return pois[:limit]


# ── Conversion helpers ────────────────────────────────────────────────────────

def _place_to_poi(
    place: dict,
    destination: str,
    category: POICategory,
) -> Optional[POI]:
    """Convert a Google Places Nearby Search result dict to a POI."""
    place_id = place.get("place_id")
    name = place.get("name", "")
    if not place_id or not name:
        return None

    geo = place.get("geometry", {}).get("location", {})
    lat = geo.get("lat")
    lng = geo.get("lng")
    if lat is None or lng is None:
        return None

    # Determine category from place types (override default if better match).
    place_types: list[str] = place.get("types", [])
    detected_category = _map_category(place_types) or category

    # Quality & popularity scores.
    rating: float = place.get("rating", 7.0)
    quality_score = min(10.0, rating * 2.0)

    ratings_count: int = place.get("user_ratings_total", 0)
    popularity_score = min(10.0, math.log1p(ratings_count) / math.log1p(10_000) * 10.0)

    # Budget.
    price_level: int = place.get("price_level", 1)
    budget_tier = _PRICE_LEVEL_BUDGET.get(price_level, BudgetLevel.mid_range)
    avg_cost_cny = float(_PRICE_LEVEL_CNY.get(price_level, 150))

    # Indoor flag.
    is_indoor = bool(set(place_types) & _INDOOR_TYPES)

    # District from vicinity (rough — take second comma-separated segment).
    vicinity: str = place.get("vicinity", "")
    parts = [p.strip() for p in vicinity.split(",")]
    district = parts[-1] if parts else destination

    return POI(
        id=place_id,
        name=name,
        destination=destination.lower(),
        category=detected_category,
        latitude=lat,
        longitude=lng,
        district=district,
        popularity_score=round(popularity_score, 2),
        quality_score=round(quality_score, 2),
        avg_cost_cny=avg_cost_cny,
        budget_tier=budget_tier,
        duration_hours=_CATEGORY_DURATION.get(detected_category, 1.5),
        indoor=is_indoor,
        tags=place_types[:5],
        description=vicinity,
    )


def _map_category(place_types: list[str]) -> Optional[POICategory]:
    """Return the first matching POICategory for the given Google Place types."""
    for gtype, category in _TYPE_MAP:
        if gtype in place_types:
            return category
    return None
