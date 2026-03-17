"""
Prompt Templates

Pure functions that build prompt strings for each LLM generation task.
Used by OpenAI and Claude providers; the mock provider bypasses these
and returns template-based text directly.

Keep prompts explicit and structured so outputs are predictable and easy
to validate in tests.
"""


def build_overview_prompt(
    destination: str,
    duration_days: int,
    persona_summary: str,
    day_themes: list[str],
    weather_summary: str,
) -> str:
    themes_str = ", ".join(day_themes) if day_themes else "mixed activities"
    return (
        f"You are a helpful travel writer. Write a warm, engaging 2-3 sentence "
        f"introduction for a {duration_days}-day trip to {destination}.\n\n"
        f"Traveler profile: {persona_summary}\n"
        f"Daily themes: {themes_str}\n"
        f"Weather outlook: {weather_summary}\n\n"
        f"Requirements:\n"
        f"- 2-3 sentences only\n"
        f"- Mention the destination and trip duration\n"
        f"- Reflect the traveler's interests and pace\n"
        f"- Do not use bullet points\n"
        f"- Write in second person (\"you\")\n"
    )


def build_day_narrative_prompt(
    day_number: int,
    theme: str,
    poi_names: list[str],
    weather_condition: str,
    travel_advisory: str,
) -> str:
    pois_str = ", ".join(poi_names) if poi_names else "various attractions"
    advisory = f" {travel_advisory}" if travel_advisory else ""
    return (
        f"You are a helpful travel writer. Write a 2-3 sentence narrative for "
        f"Day {day_number} of a trip.\n\n"
        f"Day theme: {theme}\n"
        f"Places to visit: {pois_str}\n"
        f"Weather: {weather_condition}.{advisory}\n\n"
        f"Requirements:\n"
        f"- 2-3 sentences only\n"
        f"- Mention at least one specific place by name\n"
        f"- Include a brief weather note naturally\n"
        f"- Do not use bullet points\n"
        f"- Write in second person (\"you\")\n"
    )


def build_poi_reason_prompt(
    poi_name: str,
    category: str,
    top_interest: str,
) -> str:
    return (
        f"Write a single recommendation sentence for \"{poi_name}\" "
        f"(category: {category}) for a traveler whose top interest is {top_interest}.\n\n"
        f"Requirements:\n"
        f"- One sentence only, under 40 characters\n"
        f"- No quotation marks around the sentence\n"
        f"- Be specific and engaging\n"
    )


def build_soft_preference_prompt(free_text: str) -> str:
    return (
        f"Extract travel preference tags from this text: \"{free_text}\"\n\n"
        f"Return ONLY a comma-separated list of short snake_case tags "
        f"(e.g. ancient_architecture, avoid_crowds, vegetarian_food).\n"
        f"If no clear preferences are found, return an empty string.\n"
        f"Do not include any explanation or punctuation other than commas.\n"
    )


def build_parse_trip_prompt(raw_text: str) -> str:
    """
    Build a prompt that instructs the LLM to extract structured trip fields
    from a free-text description and return them as a strict JSON object.

    The LLM must return ONLY the JSON object — no prose, no markdown fences.
    """
    return (
        "You are a travel assistant that extracts structured information from "
        "trip descriptions. Extract the fields below from the user message and "
        "return them as a single JSON object.\n\n"
        f'User message: "{raw_text}"\n\n'
        "Return ONLY a valid JSON object with exactly these fields "
        "(use null for any field not mentioned):\n"
        "{\n"
        '  "destination": <city name as a string, or null>,\n'
        '  "duration_days": <integer between 1 and 14, or null>,\n'
        '  "start_date": <"YYYY-MM-DD" string, or null>,\n'
        '  "end_date": <"YYYY-MM-DD" string, or null>,\n'
        '  "budget_level": <"budget" | "mid_range" | "luxury" | null>,\n'
        '  "travel_pace": <"relaxed" | "moderate" | "intensive" | null>,\n'
        '  "preferred_categories": <array of zero or more values from '
        '["history_culture", "nature_scenery", "food_dining", "shopping", '
        '"art_museum", "entertainment", "local_life"], or null>,\n'
        '  "free_text_preferences": <qualitative soft preferences not captured '
        'by the fields above, as a plain string, or null>\n'
        "}\n\n"
        "Rules:\n"
        "- Output ONLY the JSON object. No explanation, no markdown, no code blocks.\n"
        "- duration_days: set if explicitly stated (e.g. 'three days' → 3). "
        "If only dates are given, leave null and set start_date/end_date instead.\n"
        "- preferred_categories: map interests to the closest category value. "
        "Examples: food/eating/cuisine → food_dining, "
        "history/heritage/temple → history_culture, "
        "nature/park/beach/outdoor → nature_scenery, "
        "art/museum/gallery → art_museum, "
        "shopping/market/mall → shopping, "
        "local/neighbourhood/authentic → local_life, "
        "entertainment/nightlife/show → entertainment.\n"
        "- free_text_preferences: capture only qualitative statements that cannot "
        "be expressed as categories (e.g. 'I hate crowds', 'vegetarian only', "
        "'prefer quiet places'). Do not repeat information already captured above.\n"
        "- budget_level: 'budget' for cheap/affordable, 'luxury' for high-end/five-star, "
        "'mid_range' only if explicitly stated. Otherwise null.\n"
        "- travel_pace: 'relaxed' for slow/leisurely, 'intensive' for packed/busy. "
        "Otherwise null.\n"
    )
