from datetime import date

from fastapi import APIRouter

from app.api.dependencies import DataSourceDep, RegistryDep
from app.query.intent import QueryIntent
from app.schemas.query import ResultSet
from app.services.metrics import MetricsService

router = APIRouter(prefix="/query", tags=["query"])


@router.post("", response_model=ResultSet)
async def run_query(
    intent: QueryIntent, registry: RegistryDep, data_source: DataSourceDep
) -> ResultSet:
    """Answer one question expressed in registry vocabulary.

    The body is an intent, never SQL: names are checked against the registry and values are
    bound as parameters, so a caller cannot widen what it is allowed to read. The deterministic
    twin of /nlq/ask, which reaches this same engine through a planned intent.
    """

    service = MetricsService(registry=registry, data_source=data_source)
    # The clock lives at the boundary. Every relative window in this request resolves against
    # one reference date rather than each visual reading the clock for itself.
    return await service.run(intent, today=date.today())
