from fastapi import APIRouter, Depends

from app.api.routes import health, metrics, nlq
from app.api.security import require_internal_api_key

api_router = APIRouter(prefix="/api/v1")

# Health is open for liveness probes. Business routes require the BFF secret.
api_router.include_router(health.router)

guarded = [Depends(require_internal_api_key)]
api_router.include_router(metrics.router, dependencies=guarded)
api_router.include_router(nlq.router, dependencies=guarded)
