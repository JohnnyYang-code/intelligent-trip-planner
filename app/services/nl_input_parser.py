"""
Natural Language Input Parser — Sprint 5.6

Converts a free-text trip description into a TripRequest by:
  1. Calling llm.parse_natural_language_request(raw_text) → raw dict
  2. Validating the raw dict into ParsedTripInput (Pydantic)
  3. Applying safe defaults for any missing fields
  4. Mapping to TripRequest — the input expected by the existing pipeline

The LLM is responsible only for field extraction.
All default logic and validation live here, in pure Python.
"""

import logging
from datetime import date

from fastapi import HTTPException, status

from app.llm.base import BaseLLMProvider
from app.schemas.common import BudgetLevel, TravelPace
from app.schemas.nl_request import ParsedTripInput
from app.schemas.trip_request import InterestWeights, TripConstraints, TripRequest

logger = logging.getLogger(__name__)


class NLInputParser:
    """
    Converts raw natural language text into a TripRequest.

    Raises HTTPException 422 when:
      - the LLM returns a response that cannot be parsed into ParsedTripInput
      - destination cannot be extracted (the only mandatory field for planning)
    """

    def __init__(self, llm: BaseLLMProvider) -> None:
        self._llm = llm

    async def parse(self, raw_text: str) -> TripRequest:
        """
        Main entry point.

        Calls the LLM, validates the result, applies defaults, and returns
        a fully populated TripRequest ready for the planning pipeline.
        """

        # Step 1: LLM extraction
        try:
            raw_dict = await self._llm.parse_natural_language_request(raw_text)
        except Exception as exc:
            logger.error("LLM parse_natural_language_request raised: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Failed to parse your trip description. Please try rephrasing.",
            ) from exc

        # Step 2: Validate into ParsedTripInput
        try:
            parsed = ParsedTripInput(**raw_dict)
        except Exception as exc:
            logger.warning(
                "ParsedTripInput validation failed: %s | raw_dict=%s", exc, raw_dict
            )
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Could not understand the trip description: {exc}",
            ) from exc

        # Step 3: Destination is the only truly required field
        if not parsed.destination:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=(
                    "Could not extract a destination from your description. "
                    "Please mention the city or place you want to visit."
                ),
            )

        # Step 4: Apply defaults and build TripRequest
        trip_request = self._apply_defaults(parsed)
        logger.info(
            "NL parsed → destination=%s, days=%d, budget=%s, pace=%s",
            trip_request.destination,
            trip_request.duration_days,
            trip_request.budget_level.value,
            trip_request.travel_pace.value,
        )
        return trip_request

    # ── Default application ───────────────────────────────────────────────────

    def _apply_defaults(self, parsed: ParsedTripInput) -> TripRequest:
        return TripRequest(
            destination=parsed.destination.strip().lower(),
            duration_days=self._resolve_duration(parsed),
            budget_level=parsed.budget_level or BudgetLevel.mid_range,
            travel_pace=parsed.travel_pace or TravelPace.moderate,
            # InterestWeights() defaults (0.3–0.5 per category) are used when no
            # preferred_categories are set. PersonaBuilder overrides interests with
            # _categories_to_weights() when preferred_categories is present (Sprint 5.5).
            interests=InterestWeights(),
            preferred_categories=parsed.preferred_categories or None,
            free_text_preferences=parsed.free_text_preferences or None,
            # Constraints not extracted from free text in Sprint 5.6.
            constraints=TripConstraints(),
        )

    def _resolve_duration(self, parsed: ParsedTripInput) -> int:
        """
        Priority:
          1. Explicit duration_days from LLM
          2. Computed from start_date and end_date (if both present and valid)
          3. Safe default: 3
        """
        if parsed.duration_days is not None:
            return parsed.duration_days

        if parsed.start_date and parsed.end_date:
            try:
                start = date.fromisoformat(parsed.start_date)
                end = date.fromisoformat(parsed.end_date)
                days = (end - start).days
                if 1 <= days <= 14:
                    return days
                logger.warning(
                    "Computed duration %d outside valid range [1, 14]; defaulting to 3",
                    days,
                )
            except ValueError as exc:
                logger.warning("Invalid date strings in parsed input: %s", exc)

        return 3
