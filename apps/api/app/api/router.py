from fastapi import APIRouter, Depends

from app.api.routes import catalog, health, nlq, query
from app.api.security import require_internal_api_key
from app.schemas.error import ErrorResponse

api_router = APIRouter(prefix="/api/v1")

# Health is open for liveness probes. Business routes require the BFF secret.
api_router.include_router(health.router)

guarded = [Depends(require_internal_api_key)]
# Every 422 this service emits is an `ErrorResponse`, including the ones pydantic raises before a
# handler runs (see main.py). Declaring it here is what puts `code`, `field` and `allowed` in the
# generated TypeScript client, so `<ErrorState>` can name the options rather than say "failed".
errors: dict[int | str, dict[str, type[ErrorResponse]]] = {422: {"model": ErrorResponse}}
api_router.include_router(catalog.router, dependencies=guarded, responses=errors)
api_router.include_router(query.router, dependencies=guarded, responses=errors)
api_router.include_router(nlq.router, dependencies=guarded, responses=errors)
