"""
OpenWeatherMap weather provider.

Calls the free 5-day / 3-hour forecast endpoint and picks the 12:00 slot
for each requested day as the daily representative value.

API reference: https://openweathermap.org/forecast5
"""

import logging
from datetime import date, timedelta

import httpx

from app.integrations.weather.base import BaseWeatherProvider
from app.schemas.itinerary import DailyWeather

logger = logging.getLogger(__name__)

_FORECAST_URL = "https://api.openweathermap.org/data/2.5/forecast"

# Map OWM weather main codes to internal condition strings.
_OWM_CONDITION_MAP: dict[str, str] = {
    "Clear":        "Sunny",
    "Clouds":       "Cloudy",
    "Rain":         "Rainy",
    "Drizzle":      "Rainy",
    "Thunderstorm": "Rainy",
    "Snow":         "Snowy",
    "Mist":         "Foggy",
    "Fog":          "Foggy",
    "Haze":         "Foggy",
    "Smoke":        "Foggy",
    "Dust":         "Windy",
    "Sand":         "Windy",
    "Ash":          "Foggy",
    "Squall":       "Windy",
    "Tornado":      "Windy",
}

_CONDITION_ADVISORIES: dict[str, str] = {
    "Sunny":  "Great weather for outdoor sightseeing. Bring sunscreen.",
    "Cloudy": "Comfortable temperatures. Good day for both indoor and outdoor activities.",
    "Rainy":  "Bring an umbrella. Consider prioritising indoor attractions today.",
    "Windy":  "Strong winds expected. Dress in layers and avoid elevated outdoor spots.",
    "Foggy":  "Limited visibility. Scenic views may be obscured; indoor options recommended.",
    "Snowy":  "Snow expected. Check opening hours of outdoor attractions in advance.",
}


class OpenWeatherMapProvider(BaseWeatherProvider):
    """
    Fetches real weather forecasts from OpenWeatherMap.

    Falls back gracefully: if any day's data is missing from the API response
    (OWM free tier only covers ~5 days) the last available day is repeated.
    """

    def __init__(self, settings) -> None:
        self._api_key: str = settings.openweathermap_api_key

    def is_available(self) -> bool:
        return bool(self._api_key)

    @property
    def provider_name(self) -> str:
        return "openweathermap"

    async def get_forecast(self, city: str, days: int) -> list[DailyWeather]:
        try:
            return await self._fetch(city, days)
        except Exception as exc:
            logger.warning("OpenWeatherMap forecast failed for %s: %s", city, exc)
            # Return empty list; caller (TripPlanner) will proceed without weather.
            return []

    async def _fetch(self, city: str, days: int) -> list[DailyWeather]:
        # OWM returns up to 40 slots (5 days × 8 slots/day).
        cnt = min(days * 8, 40)
        params = {
            "q": city,
            "cnt": cnt,
            "appid": self._api_key,
            "units": "metric",
            "lang": "en",
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(_FORECAST_URL, params=params)
            resp.raise_for_status()
            data = resp.json()

        # Index slots by date string "YYYY-MM-DD", keep the one closest to 12:00.
        slots_by_date: dict[str, dict] = {}
        for slot in data.get("list", []):
            dt_txt: str = slot.get("dt_txt", "")  # "2024-03-18 12:00:00"
            slot_date = dt_txt[:10]
            slot_hour = int(dt_txt[11:13]) if len(dt_txt) >= 13 else 0

            if slot_date not in slots_by_date:
                slots_by_date[slot_date] = slot
            else:
                # Prefer slot closest to 12:00
                existing_hour = int(slots_by_date[slot_date].get("dt_txt", "00:00")[11:13] or 0)
                if abs(slot_hour - 12) < abs(existing_hour - 12):
                    slots_by_date[slot_date] = slot

        result: list[DailyWeather] = []
        today = date.today()
        last_entry: DailyWeather | None = None

        for i in range(days):
            travel_date = today + timedelta(days=i)
            date_str = travel_date.isoformat()

            if date_str in slots_by_date:
                slot = slots_by_date[date_str]
                entry = _slot_to_daily_weather(date_str, slot)
                last_entry = entry
            elif last_entry is not None:
                # Repeat last known day if API doesn't cover the full range.
                entry = DailyWeather(
                    **{**last_entry.model_dump(), "date": date_str}
                )
            else:
                # No data at all — return empty and let mock take over upstream.
                break

            result.append(entry)

        return result


def _slot_to_daily_weather(date_str: str, slot: dict) -> DailyWeather:
    main = slot.get("main", {})
    weather_list = slot.get("weather", [{}])
    wind = slot.get("wind", {})
    rain = slot.get("rain", {})
    snow = slot.get("snow", {})

    owm_main = weather_list[0].get("main", "Clear") if weather_list else "Clear"
    condition = _OWM_CONDITION_MAP.get(owm_main, "Sunny")

    precip_mm = rain.get("3h", 0.0) + snow.get("3h", 0.0)

    return DailyWeather(
        date=date_str,
        condition=condition,
        temp_high_c=round(main.get("temp_max", main.get("temp", 20.0)), 1),
        temp_low_c=round(main.get("temp_min", main.get("temp", 12.0)), 1),
        humidity_pct=int(main.get("humidity", 60)),
        precipitation_mm=round(float(precip_mm), 1),
        wind_speed_kmh=round(wind.get("speed", 10.0) * 3.6, 1),  # m/s → km/h
        uv_index=0,   # not provided by free forecast endpoint
        travel_advisory=_CONDITION_ADVISORIES.get(condition, ""),
    )
