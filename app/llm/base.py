"""
LLM Provider — Abstract Base Class

Defines the contract that all LLM providers must implement.
Each method corresponds to one text-generation task in the pipeline.

The LLM layer sits *after* the four-stage structured planning pipeline;
it narrates and explains the plan but never makes planning decisions.

Responsibilities
----------------
  generate_overview          Overall trip introduction paragraph
  generate_day_narrative     Day-by-day narrative with weather context
  generate_poi_reason        One-sentence recommendation reason per POI
  infer_soft_preferences     Parse free-text preferences → tag list
"""

from abc import ABC, abstractmethod


class BaseLLMProvider(ABC):

    @abstractmethod
    async def generate_overview(
        self,
        destination: str,
        duration_days: int,
        persona_summary: str,
        day_themes: list[str],
        weather_summary: str,
    ) -> str:
        """
        Generate a 2-3 sentence overall trip introduction.

        Parameters
        ----------
        destination     : City name, e.g. "beijing".
        duration_days   : Number of travel days.
        persona_summary : One-sentence traveler profile from PersonaBuilder.
        day_themes      : List of per-day theme strings, e.g. ["History & Culture", ...].
        weather_summary : Short weather note, e.g. "mostly sunny with mild temperatures".
        """
        ...

    @abstractmethod
    async def generate_day_narrative(
        self,
        day_number: int,
        theme: str,
        poi_names: list[str],
        weather_condition: str,
        travel_advisory: str,
    ) -> str:
        """
        Generate a 2-3 sentence narrative for a single travel day.

        Parameters
        ----------
        day_number       : 1-based day index.
        theme            : Day theme, e.g. "History & Culture".
        poi_names        : Ordered list of POI names for this day.
        weather_condition: Weather condition string, e.g. "Sunny".
        travel_advisory  : Short advisory from the weather provider.
        """
        ...

    @abstractmethod
    async def generate_poi_reason(
        self,
        poi_name: str,
        category: str,
        top_interest: str,
    ) -> str:
        """
        Generate a one-sentence recommendation reason (target ≤ 40 characters).

        Parameters
        ----------
        poi_name     : Display name of the POI.
        category     : POI category value string.
        top_interest : The traveler's highest-weighted interest category.
        """
        ...

    @abstractmethod
    async def infer_soft_preferences(self, free_text: str) -> list[str]:
        """
        Parse a free-text preference string and return a list of preference tags.

        Example input : "I love ancient architecture but dislike crowded places."
        Example output: ["ancient_architecture", "avoid_crowds"]

        Returns an empty list if no meaningful preferences can be inferred.
        """
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """Return True if this provider is properly configured and operational."""
        ...

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Human-readable provider name for logging and health checks."""
        ...
