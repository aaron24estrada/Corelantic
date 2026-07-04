"""The NL analytics orchestrator.

The one workflow: plan an intent from the question, compile it to parameterized SQL,
run it read-only, and write a narrative grounded in the rows. Every step goes through a
seam (LLM provider, data source) or the pure compiler, so the trust boundary holds and
the pieces stay swappable.
"""

from dataclasses import dataclass

from app.adapters.data.base import DataSource
from app.adapters.llm.base import LLMProvider
from app.query.compiler import compile_query
from app.query.intent import QueryIntent
from app.semantic.models import SemanticRegistry


@dataclass(frozen=True)
class AskResult:
    intent: QueryIntent
    rows: list[dict[str, object]]
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

    async def ask(self, question: str) -> AskResult:
        intent = await self._llm.plan_intent(question, self._registry)
        statement = compile_query(intent, self._registry)
        rows = await self._data_source.run(statement)
        narrative = await self._llm.write_narrative(question, rows)
        return AskResult(intent=intent, rows=rows, narrative=narrative)
