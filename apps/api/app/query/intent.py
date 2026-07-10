"""The structured query intent.

This is what the agent emits and what the compiler consumes — a request expressed only
in registry vocabulary (metric and dimension names) and closed enums, never SQL. The
model plans an intent; it never hands us SQL to run. See app/query/compiler.py.

Time intelligence rides here rather than in the registry, because a week-over-week change is
a property of the question and not of the metric. ``grain`` buckets a date dimension,
``date_range`` bounds it, ``date_dimension`` names which date to use when an entity has more
than one role (lead vs referral), ``compare`` measures each bucket against the one before it,
and ``accumulate`` runs a total that resets each period.
"""

from typing import Literal

from pydantic import BaseModel, Field

from app.query.time import DateRange, Grain, RelativeRange


class Comparison(BaseModel):
    """Measure each bucket against the previous one.

    There is no period field: ``grain`` already says what a period is. Week-over-week is
    ``grain=week`` with a comparison, month-over-month is ``grain=month``. Year-over-year at
    monthly grain would be ``lag(value, 12)`` — an offset this shape admits the day something
    needs it, and nothing does yet.
    """

    kind: Literal["pct", "change"] | None = Field(
        default=None,
        description=(
            "Relative change ('pct') or absolute ('change'). Left unset it is resolved from "
            "the metric's format, because the honest default differs: a count moving from "
            "400 to 480 rose 20 percent, while a rate moving from 20% to 24% rose 4 points. "
            "Calling that second one '20 percent' is true of the ratio and misleading about "
            "the business."
        ),
    )


class Accumulation(BaseModel):
    """A running total that restarts at the beginning of each ``reset`` period.

    Month-to-date is ``reset=month``; year-to-date is ``reset=year``. Only meaningful for a
    metric whose values may be summed across buckets — see ``MetricBase.additive``.
    """

    reset: Grain = Field(description="The period the running total restarts within.")


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
    date_range: DateRange | RelativeRange | None = Field(
        default=None,
        description="An explicit date window, or one named relative to today and resolved here.",
    )
    compare: Comparison | None = Field(
        default=None, description="Compare each bucket to the previous one. Requires a grain."
    )
    accumulate: Accumulation | None = Field(
        default=None, description="Run a total that resets each period. Requires a grain."
    )
