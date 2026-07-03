"""The structured query intent.

This is what the agent emits and what the compiler consumes — a request expressed only
in registry vocabulary (metric and dimension names), never SQL. The model plans an
intent; it never hands us SQL to run. See app/query/compiler.py.
"""

from pydantic import BaseModel, Field


class QueryIntent(BaseModel):
    metric: str = Field(description="Registry name of the metric to compute.")
    group_by: list[str] = Field(
        default_factory=list, description="Dimension names to group the metric by."
    )
    filters: dict[str, str] = Field(
        default_factory=dict,
        description="Dimension name to the exact value it must equal.",
    )
