"""SQLite rendering for the compiler's dialect-neutral constructs.

The fixture DataSource runs against SQLite, so the abstract ``DateBucket`` (app/query/time)
needs a SQLite rendering — the counterpart to the SQL Server rendering the Azure adapter
(C2) will add, and proof that the dialect seam works. Importing this module registers the
``@compiles`` rule; the fixture adapter imports it for that side effect.

The grain is a closed enum, inlined during compilation — never data — so there is no
injection surface. SQLite has no ``date_trunc``; each grain maps to a ``date(...)``
modifier expression (weeks start Monday, matching ISO).
"""

from typing import Any

from sqlalchemy.ext.compiler import compiles

from app.query.time import DateBucket, Grain

# {c} is the already-compiled date column expression (e.g. "leads.created_at").
_BUCKET: dict[Grain, str] = {
    Grain.DAY: "date({c})",
    Grain.WEEK: "date({c}, '-' || ((strftime('%w', {c}) + 6) % 7) || ' days')",
    Grain.MONTH: "date({c}, 'start of month')",
    Grain.QUARTER: (
        "date({c}, 'start of month', "
        "'-' || ((cast(strftime('%m', {c}) as integer) - 1) % 3) || ' months')"
    ),
    Grain.YEAR: "date({c}, 'start of year')",
}


@compiles(DateBucket, "sqlite")
def _render_date_bucket_sqlite(element: DateBucket, compiler: Any, **kw: Any) -> str:
    inner = compiler.process(element.date_expr, **kw)
    return _BUCKET[element.grain].format(c=inner)
