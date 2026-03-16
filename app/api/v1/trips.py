"""
POST /api/v1/trips/plan

Accepts a TripRequest and returns a fully structured ItineraryResponse
produced by the four-stage planning pipeline.
"""

import logging

from fastapi import APIRouter, HTTPException, status

from app.schemas.itinerary import ItineraryResponse
from app.schemas.trip_request import TripRequest
from app.services.trip_planner import TripPlanner

logger = logging.getLogger(__name__)
router = APIRouter()

# A single shared planner instance reused across requests.
# All providers are stateless and safe to reuse.
_planner = TripPlanner()


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
