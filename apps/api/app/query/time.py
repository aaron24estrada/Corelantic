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


_RELATIVE_DAYS = {
    "last_7_days": 7,
    "last_30_days": 30,
    "last_90_days": 90,
    "last_365_days": 365,
}


def resolve_range(spec: str, today: date) -> DateRange:
    """Resolve a relative range spec against ``today`` into an explicit ``DateRange``.

    Kept pure — the reference date is passed in, never read from the clock — so callers
    (the service or agent) resolve "last 90 days" once and the compiler only ever sees
    explicit, deterministic dates.
    """

    if spec in _RELATIVE_DAYS:
        return DateRange(start=today - timedelta(days=_RELATIVE_DAYS[spec] - 1), end=today)
    if spec == "month_to_date":
        return DateRange(start=today.replace(day=1), end=today)
    if spec == "year_to_date":
        return DateRange(start=today.replace(month=1, day=1), end=today)
    raise ValueError(f"unknown relative range: {spec!r}")
