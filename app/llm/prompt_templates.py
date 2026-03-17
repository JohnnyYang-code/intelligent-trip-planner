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
