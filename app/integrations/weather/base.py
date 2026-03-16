from abc import ABC, abstractmethod

from app.schemas.itinerary import DailyWeather


class BaseWeatherProvider(ABC):
    """
    Abstract interface for weather forecast services.

    MVP implementation: MockWeatherProvider (fixed seasonal data).
    Future implementation: OpenWeatherMapProvider.
    """

    @abstractmethod
    async def get_forecast(self, city: str, days: int) -> list[DailyWeather]:
        """
        Return a day-by-day weather forecast.

        Args:
            city: City name or normalised key, e.g. "beijing".
            days: Number of forecast days requested (1–14).

        Returns:
            List of DailyWeather objects, one per requested day.
            If the provider cannot serve the full range, returns what it can.
        """
        ...

    @abstractmethod
    def is_available(self) -> bool:
        ...

    @property
    @abstractmethod
    def provider_name(self) -> str:
        ...
