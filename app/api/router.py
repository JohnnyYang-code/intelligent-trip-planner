from fastapi import APIRouter

from app.api.v1 import health, trips

api_router = APIRouter()

api_router.include_router(health.router, prefix="/v1")
api_router.include_router(trips.router,  prefix="/v1")
