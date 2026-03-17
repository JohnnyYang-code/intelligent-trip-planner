"""
Mock LLM Provider

Returns deterministic template-based text for each generation task.
No API key or network access required.

Used as the default provider and as the fallback when a real provider
is misconfigured or unavailable.
"""

from app.llm.base import BaseLLMProvider

# Condition-specific weather notes injected into day narratives.
_WEATHER_NOTES: dict[str, str] = {
    "Sunny":  "With clear skies ahead, it's a perfect day to be outdoors.",
    "Cloudy": "The overcast sky keeps temperatures comfortable for walking.",
    "Rainy":  "Pack an umbrella — today's itinerary leans toward indoor highlights.",
    "Foggy":  "A misty atmosphere adds an air of mystery to the streets.",
    "Snowy":  "A dusting of snow makes the scenery especially picturesque.",
    "Windy":  "Dress in layers — the breeze is brisk but the sights are worth it.",
}

_CATEGORY_DESCRIPTORS: dict[str, str] = {
    "history_culture": "rich historical significance",
    "nature_scenery":  "stunning natural beauty",
    "food_dining":     "exceptional local flavors",
    "shopping":        "great shopping variety",
    "art_museum":      "impressive artistic collection",
    "entertainment":   "lively entertainment options",
    "local_life":      "authentic local atmosphere",
}


class MockLLMProvider(BaseLLMProvider):
    """
    Template-based text generation — no external calls.

    Output quality is intentionally simple and predictable so that the
    structured pipeline output can be inspected without distraction.
    """

    async def generate_overview(
        self,
        destination: str,
        duration_days: int,
        persona_summary: str,
        day_themes: list[str],
        weather_summary: str,
    ) -> str:
        themes_str = " and ".join(day_themes[:2]) if day_themes else "local highlights"
        return (
            f"Welcome to {destination.capitalize()}! "
            f"Your {duration_days}-day itinerary has been crafted around your interests in {themes_str}. "
            f"Expect a well-paced journey through the city's best experiences, "
            f"with {weather_summary} making for great travel conditions."
        )

    async def generate_day_narrative(
        self,
        day_number: int,
        theme: str,
        poi_names: list[str],
        weather_condition: str,
        travel_advisory: str,
    ) -> str:
        first_poi = poi_names[0] if poi_names else "your first stop"
        count = len(poi_names)
        weather_note = _WEATHER_NOTES.get(weather_condition, "Enjoy the day!")
        return (
            f"Day {day_number} is all about {theme.lower()}. "
            f"You'll begin at {first_poi} and explore {count} carefully selected "
            f"{'spot' if count == 1 else 'spots'} throughout the day. "
            f"{weather_note}"
        )

    async def generate_poi_reason(
        self,
        poi_name: str,
        category: str,
        top_interest: str,
    ) -> str:
        descriptor = _CATEGORY_DESCRIPTORS.get(category, "unique character")
        return f"Known for its {descriptor}."

    async def infer_soft_preferences(self, free_text: str) -> list[str]:
        """
        Lightweight keyword-based inference — no ML required.

        Detects common preference signals and maps them to tags.
        A real LLM provider would extract these more accurately.
        """
        text = free_text.lower()
        tags: list[str] = []

        if any(w in text for w in ["ancient", "historic", "old", "heritage", "dynasty"]):
            tags.append("ancient_architecture")
        if any(w in text for w in ["crowd", "crowded", "busy", "tourist trap"]):
            tags.append("avoid_crowds")
        if any(w in text for w in ["local", "authentic", "traditional"]):
            tags.append("authentic_local_experience")
        if any(w in text for w in ["food", "eat", "dining", "cuisine", "restaurant"]):
            tags.append("food_focused")
        if any(w in text for w in ["nature", "park", "outdoor", "scenery", "mountain"]):
            tags.append("nature_outdoor")
        if any(w in text for w in ["museum", "art", "gallery", "exhibition"]):
            tags.append("art_museum_enthusiast")
        if any(w in text for w in ["relax", "slow", "leisurely", "peaceful"]):
            tags.append("relaxed_pace")
        if any(w in text for w in ["photo", "instagram", "scenic"]):
            tags.append("photography_focused")

        return tags

    def is_available(self) -> bool:
        return True

    @property
    def provider_name(self) -> str:
        return "mock"
