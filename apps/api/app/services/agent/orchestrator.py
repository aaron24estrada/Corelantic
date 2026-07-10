"""The NL analytics orchestrator.

The one workflow: plan an intent from the question, compile it to parameterized SQL,
run it read-only, and write a narrative grounded in the rows. Every step goes through a
seam (LLM provider, data source) or the pure compiler, so the trust boundary holds and
the pieces stay swappable.
"""

from dataclasses import dataclass
from datetime import date

from app.adapters.data.base import DataSource
from app.adapters.llm.base import LLMProvider
from app.query.compiler import compile_resolved
from app.query.validate import validate_intent
from app.schemas.query import ResultSet
from app.semantic.models import SemanticRegistry
from app.services.result import build_result


@dataclass(frozen=True)
class AskResult:
    result: ResultSet
    narrative: str


class Orchestrator:
    def __init__(
        self,
        llm: LLMProvider,
        registry: SemanticRegistry,
        data_source: DataSource,
    ) -> None:
        self._llm = llm
        self._registry = registry
        self._data_source = data_source

    async def ask(self, question: str, *, today: date) -> AskResult:
        intent = await self._llm.plan_intent(question, self._registry)
        # The planned intent is validated against the registry before it compiles. An intent
        # the model invented reaches the caller as a 422 naming what it could have asked for,
        # which is what lets a later pass repair it rather than guess again.
        resolved = validate_intent(intent, self._registry, today=today)
        rows = await self._data_source.run(compile_resolved(resolved, self._registry))
        narrative = await self._llm.write_narrative(question, rows)
        return AskResult(result=build_result(resolved, self._registry, rows), narrative=narrative)
