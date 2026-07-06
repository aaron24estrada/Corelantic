"""The structured query intent.

This is what the agent emits and what the compiler consumes — a request expressed only
in registry vocabulary (metric and dimension names) and closed enums, never SQL. The
model plans an intent; it never hands us SQL to run. See app/query/compiler.py.

Time intelligence rides on the intent: ``grain`` buckets a date dimension, ``date_range``
bounds it (explicit dates — relative ranges are resolved to these upstream by
``app/query/time.resolve_range``), and ``date_dimension`` names which date to use when an
entity has more than one role (lead vs referral).
"""

from pydantic import BaseModel, Field

from app.query.time import DateRange, Grain


class QueryIntent(BaseModel):
    metric: str = Field(description="Registry name of the metric to compute.")
    group_by: list[str] = Field(
        default_factory=list, description="Dimension names to group the metric by."
    )
    filters: dict[str, str] = Field(
        default_factory=dict,
        description="Dimension name to the exact value it must equal.",
    )
    grain: Grain | None = Field(
        default=None, description="Bucket the date dimension by this grain (day/week/month/...)."
    )
    date_dimension: str | None = Field(
        default=None,
        description="Which date dimension to bucket/range on; inferred when the entity has one.",
    )
    date_range: DateRange | None = Field(
        default=None, description="Explicit date window to restrict the query to."
    )
