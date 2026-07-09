"""SQL Server rendering of the compiler's dialect-neutral ``DateBucket``.

The counterpart to app/adapters/data/sqlite; the Azure adapter imports it for the
``@compiles`` side effect. Grain is a closed enum inlined at compile time, never data.
"""

from typing import Any

from sqlalchemy.ext.compiler import compiles

from app.query.time import DateBucket, Grain

# {c} is the compiled date column. DATEDIFF/DATEADD off anchor 0 (1900-01-01, a Monday)
# truncates to the period start, independent of DATEFIRST. DATEDIFF(week) counts Sunday
# boundaries, so a raw week bucket would push Sunday into the next Monday; shifting back a
# day groups Sunday with the preceding Monday (ISO), matching the SQLite rendering.
_BUCKET: dict[Grain, str] = {
    Grain.DAY: "CAST({c} AS date)",
    Grain.WEEK: "DATEADD(week, DATEDIFF(week, 0, DATEADD(day, -1, {c})), 0)",
    Grain.MONTH: "DATEADD(month, DATEDIFF(month, 0, {c}), 0)",
    Grain.QUARTER: "DATEADD(quarter, DATEDIFF(quarter, 0, {c}), 0)",
    Grain.YEAR: "DATEADD(year, DATEDIFF(year, 0, {c}), 0)",
}


@compiles(DateBucket, "mssql")
def _render_date_bucket_mssql(element: DateBucket, compiler: Any, **kw: Any) -> str:
    inner = compiler.process(element.date_expr, **kw)
    return _BUCKET[element.grain].format(c=inner)
