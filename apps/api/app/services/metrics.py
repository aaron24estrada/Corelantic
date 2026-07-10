"""Metrics service — the deterministic dashboard path.

Validates an intent against the registry, compiles it, runs it against the data source, and
describes what came back. Framework-agnostic: no FastAPI types here.

``today`` is passed in rather than read from the clock, so a dashboard load resolves "last 90
days" once and every visual on it covers the same days, even across midnight.
"""

from datetime import date

from app.adapters.data.base import DataSource
from app.query.compiler import compile_resolved
from app.query.intent import QueryIntent
from app.query.validate import validate_intent
from app.schemas.query import ResultSet
from app.semantic.models import SemanticRegistry
from app.services.result import build_result


class MetricsService:
    def __init__(self, registry: SemanticRegistry, data_source: DataSource) -> None:
        self._registry = registry
        self._data_source = data_source

    async def run(self, intent: QueryIntent, *, today: date) -> ResultSet:
        resolved = validate_intent(intent, self._registry, today=today)
        rows = await self._data_source.run(compile_resolved(resolved, self._registry))
        return build_result(resolved, self._registry, rows)
