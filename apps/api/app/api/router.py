from fastapi import APIRouter

from app.api.routes import health, metrics, nlq

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router)
api_router.include_router(metrics.router)
api_router.include_router(nlq.router)
