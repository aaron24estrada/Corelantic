"""Dialect-neutral time-intelligence primitives for the compiler.

The compiler builds a SQLAlchemy Core tree that knows *what* it wants — "bucket this date
by week" — without knowing *how* any database spells that. ``DateBucket`` is that abstract
construct: it carries a grain (a closed enum, never user text) and a date expression, and
a per-dialect ``@compiles`` rule renders it. The generic rendering here is a placeholder
for tests and unknown dialects; the SQL Server rendering lands with the Azure adapter
(C2), at the dialect seam where the concrete dialect is finally known.

Grain never reaches SQL as data — it is inlined from a fixed enum during compilation, so
there is no injection surface. Only bound date *values* (ranges) flow as parameters.
"""

from datetime import date, timedelta
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, model_validator
from sqlalchemy import Date
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.sql.expression import ColumnElement
from sqlalchemy.sql.visitors import InternalTraversal


class Grain(StrEnum):
    DAY = "day"
    WEEK = "week"
    MONTH = "month"
    QUARTER = "quarter"
    YEAR = "year"


# Which grains a running total may reset on, per bucket grain. This is a calendar fact, not
# an ordering: a week straddles a month boundary, so "month-to-date over weekly buckets" has
# no honest answer — the straddling week belongs to both. Weeks are admitted into years only
# because DateBucket assigns a week to the year of its Monday, which is at least
# deterministic. Days and months nest cleanly and carry the real cases (MTD, YTD).
_NESTS_IN: dict[Grain, frozenset[Grain]] = {
    Grain.DAY: frozenset({Grain.WEEK, Grain.MONTH, Grain.QUARTER, Grain.YEAR}),
    Grain.WEEK: frozenset({Grain.YEAR}),
    Grain.MONTH: frozenset({Grain.QUARTER, Grain.YEAR}),
    Grain.QUARTER: frozenset({Grain.YEAR}),
    Grain.YEAR: frozenset(),
}


def nests_in(inner: Grain, outer: Grain) -> bool:
    """Whether every ``inner`` bucket falls wholly inside one ``outer`` period."""

    return outer in _NESTS_IN[inner]


def nesting_grains(inner: Grain) -> list[str]:
    """The grains ``inner`` nests in, for an error message that names the options."""

    return sorted(grain.value for grain in _NESTS_IN[inner])


def period_start(day: date, grain: Grain) -> date:
    """The first day of the ``grain`` period containing ``day``.

    Mirrors ``DateBucket``: both dialect renderings truncate a week to its Monday, so this
    does too. Used to tell whether a date range begins on a period boundary — a running total
    that starts mid-period is not the total it claims to be.
    """

    if grain is Grain.DAY:
        return day
    if grain is Grain.WEEK:
        return day - timedelta(days=day.weekday())
    if grain is Grain.MONTH:
        return day.replace(day=1)
    if grain is Grain.QUARTER:
        return day.replace(month=(day.month - 1) // 3 * 3 + 1, day=1)
    return day.replace(month=1, day=1)  # Grain.YEAR


class DateBucket(ColumnElement[Any]):
    """Truncate a date expression to the start of its ``grain`` period.

    ``_traverse_internals`` makes ``grain`` and ``date_expr`` part of the construct's
    cache key and reachable by SQLAlchemy visitors — without it, statement caching could
    reuse one grain's compiled SQL for another (a week bucket served as a month bucket).
    """

    _traverse_internals = [  # noqa: RUF012  (SQLAlchemy declares this instance-level)
        ("grain", InternalTraversal.dp_string),
        ("date_expr", InternalTraversal.dp_clauseelement),
    ]

    def __init__(self, grain: Grain, date_expr: ColumnElement[Any]) -> None:
        self.grain = grain
        self.date_expr = date_expr
        self.type = Date()


@compiles(DateBucket)
def _render_date_bucket(element: DateBucket, compiler: Any, **kw: Any) -> str:
    inner = compiler.process(element.date_expr, **kw)
    # Generic default (date_trunc is Postgres/Snowflake/DuckDB shape). SQL Server renders
    # this differently (DATETRUNC / DATEADD); that override ships with the C2 adapter.
    return f"date_trunc('{element.grain.value}', {inner})"


class DateRange(BaseModel):
    """An explicit, inclusive date window. Either bound may be open."""

    start: date | None = Field(default=None, description="Earliest date to include.")
    end: date | None = Field(default=None, description="Latest date to include.")

    @model_validator(mode="after")
    def _ordered(self) -> "DateRange":
        if self.start is not None and self.end is not None and self.start > self.end:
            raise ValueError(f"date range start {self.start} is after end {self.end}")
        return self


class RelativeRange(StrEnum):
    """A date window named relative to today, resolved once at the API boundary.

    A closed enum rather than a free string so it lands in the OpenAPI schema: the agent can
    only pick a window we implement, and the dashboard does not reimplement "last 90 days"
    in TypeScript and disagree with us about whether it is inclusive.
    """

    LAST_7_DAYS = "last_7_days"
    LAST_30_DAYS = "last_30_days"
    LAST_90_DAYS = "last_90_days"
    LAST_365_DAYS = "last_365_days"
    MONTH_TO_DATE = "month_to_date"
    YEAR_TO_DATE = "year_to_date"


_RELATIVE_DAYS = {
    RelativeRange.LAST_7_DAYS: 7,
    RelativeRange.LAST_30_DAYS: 30,
    RelativeRange.LAST_90_DAYS: 90,
    RelativeRange.LAST_365_DAYS: 365,
}


def resolve_range(spec: RelativeRange, today: date) -> DateRange:
    """Resolve a relative range against ``today`` into an explicit, inclusive ``DateRange``.

    Kept pure — the reference date is passed in, never read from the clock — so the window is
    fixed once, at the boundary, and the compiler only ever sees explicit dates. Two visuals
    on one dashboard load therefore cover the same window even across midnight.
    """

    if spec in _RELATIVE_DAYS:
        return DateRange(start=today - timedelta(days=_RELATIVE_DAYS[spec] - 1), end=today)
    if spec is RelativeRange.MONTH_TO_DATE:
        return DateRange(start=today.replace(day=1), end=today)
    if spec is RelativeRange.YEAR_TO_DATE:
        return DateRange(start=today.replace(month=1, day=1), end=today)
    raise AssertionError(f"unhandled relative range: {spec!r}")
