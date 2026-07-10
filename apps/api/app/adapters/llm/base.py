"""The LLM-provider seam.

The interface encodes the trust boundary: the model *plans* a query (returns a
structured intent drawn from the registry) and *writes a narrative* grounded in the
returned rows. It never returns SQL or code we execute. Concrete providers (Claude,
pending a key) live beside this module and are selected by the factory.
"""

from typing import Protocol

from app.query.intent import QueryIntent
from app.query.rows import Row
from app.semantic.models import SemanticRegistry


class LLMProvider(Protocol):
    async def plan_intent(self, question: str, registry: SemanticRegistry) -> QueryIntent:
        """Interpret a question into a structured intent, using only registry vocabulary."""
        ...

    async def write_narrative(self, question: str, rows: list[Row]) -> str:
        """Write a short narrative grounded strictly in the returned rows."""
        ...
