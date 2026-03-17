"""
Trip planning endpoints.

POST /api/v1/trips/plan
    Accepts a structured TripRequest and returns a fully-formed ItineraryResponse
    produced by the four-stage planning pipeline.

POST /api/v1/trips/plan-from-text  (Sprint 5.6)
    Accepts a free-text trip description, uses the LLM to extract structured
    fields into a TripRequest, then runs the same four-stage pipeline.
    The LLM is used only for field extraction — planning logic is unchanged.
"""

import logging

from fastapi import APIRouter, HTTPException, status

from app.config.settings import get_settings
from app.llm.llm_factory import create_llm_provider
from app.schemas.itinerary import ItineraryResponse
from app.schemas.nl_request import NaturalLanguageTripRequest
from app.schemas.trip_request import TripRequest
from app.services.nl_input_parser import NLInputParser
from app.services.trip_planner import TripPlanner

logger = logging.getLogger(__name__)
router = APIRouter()

# Shared singletons — all providers are stateless and safe to reuse.
_planner = TripPlanner()
_nl_parser = NLInputParser(llm=create_llm_provider(get_settings()))


@router.post(
    "/trips/plan",
    response_model=ItineraryResponse,
    status_code=status.HTTP_200_OK,
    tags=["trips"],
    summary="Generate a personalized multi-day itinerary",
    response_description="Structured itinerary with per-day POI schedules and weather info",
)
async def plan_trip(request: TripRequest) -> ItineraryResponse:
    """
    Generate a personalized multi-day trip itinerary.

    The response includes:
    - A scored and ordered list of POIs for each day
    - Suggested visit times per POI
    - Daily weather forecast (mock by default)
    - Traveler persona summary used for planning

    LLM-generated narrative fields (`overview`, `narrative`, `tips`,
    `recommendation_reason`) are empty strings until Sprint 4.
    """
    logger.info(
        "Received plan request: destination=%s, days=%d",
        request.destination,
        request.duration_days,
    )

    try:
        itinerary = await _planner.plan(request)
    except Exception as exc:
        logger.exception("Planning failed for destination=%s", request.destination)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Trip planning failed: {exc}",
        ) from exc

    return itinerary


@router.post(
    "/trips/plan-from-text",
    response_model=ItineraryResponse,
    status_code=status.HTTP_200_OK,
    tags=["trips"],
    summary="Generate an itinerary from a natural language description",
    response_description="Structured itinerary — same format as /trips/plan",
)
async def plan_trip_from_text(request: NaturalLanguageTripRequest) -> ItineraryResponse:
    """
    Accept a free-text trip description, parse it into a structured TripRequest
    via LLM, then run the existing four-stage planning pipeline.

    The LLM is used ONLY for field extraction (destination, duration, categories,
    etc.). All planning decisions — POI scoring, day allocation, route ordering —
    remain with the deterministic structured pipeline.

    Returns 422 if a destination cannot be extracted from the description.
    """
    logger.info("NL plan request: %.80s...", request.raw_text)

    # Step 1: Parse natural language → TripRequest (raises 422 on failure)
    trip_request = await _nl_parser.parse(request.raw_text)

    logger.info(
        "NL parsed → destination=%s, days=%d",
        trip_request.destination,
        trip_request.duration_days,
    )

    # Step 2: Run the existing planning pipeline (unchanged)
    try:
        return await _planner.plan(trip_request)
    except Exception as exc:
        logger.exception(
            "Planning failed after NL parse, destination=%s", trip_request.destination
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Trip planning failed: {exc}",
        ) from exc
