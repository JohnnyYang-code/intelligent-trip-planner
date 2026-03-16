import random
from datetime import date, timedelta

from app.integrations.weather.base import BaseWeatherProvider
from app.schemas.itinerary import DailyWeather

# Seasonal baseline weather data per city.
# Structure: city → month (1–12) → (condition, high_c, low_c, humidity, precip_mm, wind_kmh, uv)
_CITY_WEATHER: dict[str, dict[int, tuple]] = {
    "beijing": {
        1:  ("Sunny",  2,  -8, 35, 2,  12, 2),
        2:  ("Cloudy", 6,  -4, 38, 4,  13, 3),
        3:  ("Windy",  13,  2, 42, 8,  16, 4),
        4:  ("Sunny",  21,  9, 45, 12, 14, 6),
        5:  ("Sunny",  27, 15, 48, 15, 12, 7),
        6:  ("Cloudy", 31, 20, 55, 25, 10, 8),
        7:  ("Rainy",  31, 22, 70, 60,  8, 7),
        8:  ("Rainy",  30, 21, 68, 55,  8, 7),
        9:  ("Sunny",  25, 14, 55, 20, 10, 6),
        10: ("Sunny",  18,  7, 50, 10, 11, 4),
        11: ("Cloudy", 9,   0, 45, 6,  13, 3),
        12: ("Sunny",  3,  -6, 38, 3,  12, 2),
    },
    "shanghai": {
        1:  ("Cloudy", 8,   2, 68, 50, 14, 2),
        2:  ("Rainy",  10,  4, 72, 60, 13, 3),
        3:  ("Rainy",  14,  8, 74, 70, 14, 4),
        4:  ("Cloudy", 20, 13, 72, 80, 12, 5),
        5:  ("Sunny",  25, 18, 68, 60, 10, 7),
        6:  ("Rainy",  29, 23, 80, 90,  9, 7),
        7:  ("Sunny",  33, 27, 78, 40, 10, 9),
        8:  ("Sunny",  33, 27, 76, 45, 10, 9),
        9:  ("Cloudy", 28, 22, 74, 55, 10, 7),
        10: ("Sunny",  23, 16, 68, 40, 11, 5),
        11: ("Cloudy", 16, 10, 68, 50, 13, 3),
        12: ("Cloudy", 10,  4, 68, 50, 14, 2),
    },
    "chengdu": {
        1:  ("Foggy",  9,   3, 80, 20,  5, 1),
        2:  ("Cloudy", 12,  5, 78, 25,  6, 2),
        3:  ("Cloudy", 17,  9, 76, 30,  7, 3),
        4:  ("Rainy",  22, 14, 78, 50,  7, 5),
        5:  ("Cloudy", 26, 18, 76, 55,  8, 6),
        6:  ("Rainy",  28, 21, 82, 80,  7, 6),
        7:  ("Rainy",  30, 23, 84, 90,  6, 7),
        8:  ("Rainy",  30, 23, 82, 85,  6, 7),
        9:  ("Rainy",  25, 18, 84, 70,  6, 5),
        10: ("Cloudy", 19, 13, 82, 40,  6, 3),
        11: ("Foggy",  13,  7, 82, 25,  5, 2),
        12: ("Foggy",  9,   3, 80, 20,  5, 1),
    },
}

_DEFAULT_WEATHER = ("Sunny", 20, 12, 60, 10, 10, 5)

_CONDITION_ADVISORIES: dict[str, str] = {
    "Sunny":  "Great weather for outdoor sightseeing. Bring sunscreen.",
    "Cloudy": "Comfortable temperatures. Good day for both indoor and outdoor activities.",
    "Rainy":  "Bring an umbrella. Consider prioritising indoor attractions today.",
    "Windy":  "Strong winds expected. Dress in layers and avoid elevated outdoor spots.",
    "Foggy":  "Limited visibility. Scenic views may be obscured; indoor options recommended.",
    "Snowy":  "Snow expected. Check opening hours of outdoor attractions in advance.",
}


class MockWeatherProvider(BaseWeatherProvider):
    """
    Returns plausible seasonal weather forecasts without any API call.

    Each day has a small random variation applied to temperature and precipitation
    so that a multi-day forecast looks realistic rather than identical.
    """

    async def get_forecast(self, city: str, days: int) -> list[DailyWeather]:
        city_key = city.lower()
        monthly = _CITY_WEATHER.get(city_key)

        # Attempt Chinese aliases
        if monthly is None:
            alias_map = {"北京": "beijing", "上海": "shanghai", "成都": "chengdu"}
            mapped = alias_map.get(city)
            if mapped:
                monthly = _CITY_WEATHER.get(mapped)

        today = date.today()
        month = today.month

        result: list[DailyWeather] = []
        rng = random.Random(42)  # fixed seed for reproducibility in tests

        for i in range(days):
            travel_date = today + timedelta(days=i)
            day_month = travel_date.month

            if monthly:
                condition, high, low, humidity, precip, wind, uv = monthly[day_month]
            else:
                condition, high, low, humidity, precip, wind, uv = _DEFAULT_WEATHER

            # Small daily variation
            high_var = high + rng.uniform(-2, 2)
            low_var = low + rng.uniform(-2, 2)
            precip_var = max(0.0, precip + rng.uniform(-5, 5))

            advisory = _CONDITION_ADVISORIES.get(condition, "")

            result.append(
                DailyWeather(
                    date=travel_date.isoformat(),
                    condition=condition,
                    temp_high_c=round(high_var, 1),
                    temp_low_c=round(low_var, 1),
                    humidity_pct=humidity,
                    precipitation_mm=round(precip_var, 1),
                    wind_speed_kmh=float(wind),
                    uv_index=uv,
                    travel_advisory=advisory,
                )
            )

        return result

    def is_available(self) -> bool:
        return True

    @property
    def provider_name(self) -> str:
        return "mock"
