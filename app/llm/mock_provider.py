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


def _detect_language(text: str) -> str:
    """
    Lightweight language detection based on Unicode character ratio.

    Returns "zh" if >15% of characters are CJK Unified Ideographs,
    "en" if the text contains only ASCII-range characters, or "unknown"
    when neither condition is met confidently.
    """
    if not text:
        return "unknown"
    chinese_chars = sum(1 for c in text if "\u4e00" <= c <= "\u9fff")
    ratio = chinese_chars / len(text)
    if ratio > 0.15:
        return "zh"
    if all(ord(c) < 128 for c in text):
        return "en"
    return "unknown"


def _infer_zh(text: str) -> list[str]:
    """Chinese keyword-based soft-preference inference."""
    tags: list[str] = []
    if any(w in text for w in ["古建筑", "历史", "文化", "遗址", "古迹"]):
        tags.append("ancient_architecture")
    if any(w in text for w in ["不想排队", "少排队", "不喜欢人多", "人太多"]):
        tags.append("avoid_crowds")
    if any(w in text for w in ["本地", "当地", "地道", "传统"]):
        tags.append("authentic_local_experience")
    if any(w in text for w in ["小吃", "美食", "餐厅", "美味", "吃饭"]):
        tags.append("food_focused")
    if any(w in text for w in ["自然", "公园", "户外", "风景", "爬山"]):
        tags.append("nature_outdoor")
    if any(w in text for w in ["博物馆", "艺术", "画廊", "展览"]):
        tags.append("art_museum_enthusiast")
    if any(w in text for w in ["轻松", "悠闲", "不要太赶", "放松", "慢慢"]):
        tags.append("relaxed_pace")
    if any(w in text for w in ["拍照", "摄影", "打卡"]):
        tags.append("photography_focused")
    return tags


def _infer_en(text: str) -> list[str]:
    """English keyword-based soft-preference inference (text must be lowercased)."""
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

        Detects the input language first (Chinese vs English via Unicode ratio),
        then applies the matching keyword table.  Returns an empty list when
        the language cannot be determined confidently.
        A real LLM provider would extract these more accurately.
        """
        lang = _detect_language(free_text)
        if lang == "zh":
            return _infer_zh(free_text)
        if lang == "en":
            return _infer_en(free_text.lower())
        return []

    def is_available(self) -> bool:
        return True

    @property
    def provider_name(self) -> str:
        return "mock"
