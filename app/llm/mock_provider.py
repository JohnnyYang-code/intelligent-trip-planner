"""
Mock LLM Provider

Returns deterministic template-based text for each generation task.
No API key or network access required.

Used as the default provider and as the fallback when a real provider
is misconfigured or unavailable.
"""

import re

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

    async def parse_natural_language_request(self, raw_text: str) -> dict:
        """
        Regex/keyword-based NL field extraction — no API required.

        Supports English (primary) and Chinese (lightweight).
        Returns a dict with all ParsedTripInput keys; unextracted values are None.
        """
        text = raw_text.strip()
        lower = text.lower()
        lang = _detect_language(text)

        # ── destination ───────────────────────────────────────────────────────
        destination = None
        if lang == "zh":
            # Chinese: look for city markers like "去X" "在X" "到X"
            zh_dest = re.search(r"[去在到]([^\s，。！？,\.]{2,6}?)(?:[玩旅游游玩，。]|$)", text)
            if zh_dest:
                destination = zh_dest.group(1).strip()
        else:
            # English: capitalize word(s) after "in" or "to", stopping when
            # the next word is lowercase (a verb/preposition) or at punctuation.
            en_dest = re.search(
                r"\b(?:in|to)\s+([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)*)"
                r"(?=\s*[,.]|\s+[a-z]|$)",
                text,
            )
            if en_dest:
                destination = en_dest.group(1).strip()

        # ── duration_days ─────────────────────────────────────────────────────
        _WORD_TO_INT = {
            "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
            "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
        }
        duration_days = None
        dur_match = re.search(
            r"\b(\d+|" + "|".join(_WORD_TO_INT) + r")\s*[-\s]?days?\b",
            lower,
        )
        if dur_match:
            raw_dur = dur_match.group(1)
            duration_days = int(raw_dur) if raw_dur.isdigit() else _WORD_TO_INT.get(raw_dur)

        if duration_days is None and lang == "zh":
            zh_dur = re.search(r"(\d+)\s*天", text)
            if zh_dur:
                duration_days = int(zh_dur.group(1))

        # ── ISO dates ─────────────────────────────────────────────────────────
        start_date = end_date = None
        iso_dates = re.findall(r"\b(\d{4}-\d{2}-\d{2})\b", text)
        if len(iso_dates) >= 2:
            start_date, end_date = iso_dates[0], iso_dates[1]

        # ── budget_level ──────────────────────────────────────────────────────
        budget_level = None
        if any(w in lower for w in ["budget", "cheap", "affordable", "low-cost"]):
            budget_level = "budget"
        elif any(w in lower for w in ["luxury", "five-star", "5-star", "splurge", "high-end"]):
            budget_level = "luxury"
        elif lang == "zh":
            if any(w in text for w in ["便宜", "省钱", "经济"]):
                budget_level = "budget"
            elif any(w in text for w in ["奢华", "高端", "五星"]):
                budget_level = "luxury"

        # ── travel_pace ───────────────────────────────────────────────────────
        travel_pace = None
        if any(w in lower for w in ["relax", "leisurely", "slow", "easy-going"]):
            travel_pace = "relaxed"
        elif any(w in lower for w in ["intensive", "packed", "busy", "hectic", "fast-paced"]):
            travel_pace = "intensive"
        elif lang == "zh":
            if any(w in text for w in ["轻松", "悠闲", "慢慢", "放松"]):
                travel_pace = "relaxed"
            elif any(w in text for w in ["紧凑", "密集", "多玩"]):
                travel_pace = "intensive"

        # ── preferred_categories ──────────────────────────────────────────────
        _EN_CAT_KEYWORDS: dict[str, list[str]] = {
            "history_culture":  ["history", "historic", "culture", "heritage", "temple", "palace", "ancient"],
            "nature_scenery":   ["nature", "scenery", "outdoor", "park", "mountain", "beach", "hike", "hiking"],
            "food_dining":      ["food", "dining", "eat", "restaurant", "cuisine", "foodie", "culinary"],
            "shopping":         ["shop", "shopping", "market", "mall", "buy"],
            "art_museum":       ["art", "museum", "gallery", "exhibition"],
            "entertainment":    ["entertainment", "nightlife", "show", "concert", "theme park"],
            "local_life":       ["local", "authentic", "neighbourhood", "neighborhood", "street life"],
        }
        _ZH_CAT_KEYWORDS: dict[str, list[str]] = {
            "history_culture":  ["历史", "文化", "古迹", "寺庙", "遗址", "故宫"],
            "nature_scenery":   ["自然", "风景", "公园", "山", "海", "户外"],
            "food_dining":      ["美食", "吃", "餐厅", "小吃", "食物"],
            "shopping":         ["购物", "商场", "市场", "买"],
            "art_museum":       ["艺术", "博物馆", "画廊", "展览"],
            "entertainment":    ["娱乐", "演出", "演唱会", "夜生活"],
            "local_life":       ["当地", "本地", "地道", "街头"],
        }
        cat_keywords = _ZH_CAT_KEYWORDS if lang == "zh" else _EN_CAT_KEYWORDS
        search_text = text if lang == "zh" else lower
        preferred_categories = [
            cat for cat, kws in cat_keywords.items()
            if any(kw in search_text for kw in kws)
        ] or None

        # ── free_text_preferences ─────────────────────────────────────────────
        # Capture qualitative soft preferences not expressible as categories
        free_text_preferences = None
        soft_keywords_en = ["hate", "avoid", "dislike", "love", "prefer",
                             "vegetarian", "vegan", "crowd", "quiet", "wheelchair"]
        soft_keywords_zh = ["讨厌", "不喜欢", "喜欢", "素食", "拥挤", "安静", "避开"]
        if lang == "zh":
            if any(w in text for w in soft_keywords_zh):
                free_text_preferences = text
        elif any(w in lower for w in soft_keywords_en):
            free_text_preferences = text

        return {
            "destination": destination,
            "duration_days": duration_days,
            "start_date": start_date,
            "end_date": end_date,
            "budget_level": budget_level,
            "travel_pace": travel_pace,
            "preferred_categories": preferred_categories,
            "free_text_preferences": free_text_preferences,
        }

    def is_available(self) -> bool:
        return True

    @property
    def provider_name(self) -> str:
        return "mock"
