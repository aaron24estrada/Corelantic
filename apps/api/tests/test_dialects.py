"""DateBucket must render in every dialect we run against — including nested.

An accumulation buckets a date, then buckets the *bucket* to find its reset period. That
second DateBucket takes a subquery column rather than a table column, and each dialect
renders it differently. A generic-dialect test would pass while SQL Server rejected the
statement at runtime, which is exactly the failure we cannot see from here.
"""

from typing import Any

import pytest
from sqlalchemy import Select
from sqlalchemy.dialects import mssql, sqlite

import app.adapters.data.mssql
import app.adapters.data.sqlite  # noqa: F401 — registers the DateBucket SQLite rendering
from app.query.compiler import compile_query
from app.query.intent import Accumulation, Comparison, QueryIntent
from app.query.time import Grain
from tests.test_compiler import _registry

_DIALECTS: dict[str, Any] = {
    "sqlite": sqlite.dialect(),
    # SQLAlchemy does not annotate the mssql dialect factory; the object it returns is fine.
    "mssql": mssql.dialect(),  # type: ignore[no-untyped-call]
}


def _render(statement: Select[Any], dialect_name: str) -> str:
    compiled = statement.compile(dialect=_DIALECTS[dialect_name])
    return " ".join(str(compiled).split())


@pytest.mark.parametrize("dialect", ["sqlite", "mssql"])
def test_an_accumulation_renders_its_nested_bucket(dialect: str) -> None:
    intent = QueryIntent(
        metric="spend", grain=Grain.MONTH, accumulate=Accumulation(reset=Grain.YEAR)
    )
    sql = _render(compile_query(intent, _registry()), dialect)

    assert "date_trunc" not in sql  # the generic placeholder never reaches a real database
    assert "PARTITION BY" in sql
    assert "ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW" in sql


@pytest.mark.parametrize("dialect", ["sqlite", "mssql"])
def test_a_comparison_renders_its_bucket_and_lag(dialect: str) -> None:
    intent = QueryIntent(metric="new_leads", grain=Grain.WEEK, compare=Comparison())
    sql = _render(compile_query(intent, _registry()), dialect)

    assert "date_trunc" not in sql
    assert "lag(" in sql.lower()


def test_sql_server_truncates_a_month_with_dateadd() -> None:
    intent = QueryIntent(
        metric="spend", grain=Grain.MONTH, accumulate=Accumulation(reset=Grain.YEAR)
    )
    sql = _render(compile_query(intent, _registry()), "mssql")

    assert "DATEADD(month, DATEDIFF(month, 0," in sql  # the inner bucket
    assert "DATEADD(year, DATEDIFF(year, 0," in sql  # the reset, over the bucket


def test_sqlite_truncates_a_week_to_its_monday() -> None:
    intent = QueryIntent(metric="new_leads", grain=Grain.WEEK, compare=Comparison())
    sql = _render(compile_query(intent, _registry()), "sqlite")

    assert "strftime('%w'" in sql
