"""Metrics service — the deterministic dashboard path.

Compiles a metric (optionally grouped and filtered) from the registry and runs it
against the data source. Framework-agnostic: no FastAPI types here.
"""

from app.adapters.data.base import DataSource
from app.query.compiler import compile_query
from app.query.intent import QueryIntent
from app.semantic.models import SemanticRegistry


class MetricsService:
    def __init__(self, registry: SemanticRegistry, data_source: DataSource) -> None:
        self._registry = registry
        self._data_source = data_source

    async def compute(self, intent: QueryIntent) -> list[dict[str, object]]:
        compiled = compile_query(intent, self._registry)
        return await self._data_source.run(compiled.sql, compiled.params)
