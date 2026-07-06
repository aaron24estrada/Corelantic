from datetime import date

import pytest
from sqlalchemy import column, select

from app.query.time import DateBucket, DateRange, Grain, resolve_range


def _sql(grain: Grain) -> str:
    statement = select(DateBucket(grain, column("d")).label("period"))
    return " ".join(str(statement.compile()).split())


def test_date_bucket_renders_generic_truncation_per_grain() -> None:
    assert _sql(Grain.WEEK) == "SELECT date_trunc('week', d) AS period"
    assert _sql(Grain.MONTH) == "SELECT date_trunc('month', d) AS period"
    assert _sql(Grain.QUARTER) == "SELECT date_trunc('quarter', d) AS period"


def _cache_key(grain: Grain, col: str) -> object:
    key = select(DateBucket(grain, column(col)).label("period"))._generate_cache_key()
    assert key is not None  # the construct must be cacheable, not opt out of caching
    return key.key


def test_date_bucket_cache_key_distinguishes_grain_and_column() -> None:
    # Guards the cache correctness of _traverse_internals: statement caching must never
    # serve one grain's (or column's) compiled SQL for another.
    assert _cache_key(Grain.WEEK, "d") != _cache_key(Grain.MONTH, "d")
    assert _cache_key(Grain.WEEK, "created_at") != _cache_key(Grain.WEEK, "referral_date")
    assert _cache_key(Grain.WEEK, "d") == _cache_key(Grain.WEEK, "d")


def test_resolve_relative_last_n_days_is_inclusive() -> None:
    got = resolve_range("last_90_days", date(2026, 7, 6))
    assert got == DateRange(start=date(2026, 4, 8), end=date(2026, 7, 6))


def test_resolve_month_and_year_to_date() -> None:
    assert resolve_range("month_to_date", date(2026, 7, 6)).start == date(2026, 7, 1)
    assert resolve_range("year_to_date", date(2026, 7, 6)).start == date(2026, 1, 1)


def test_resolve_unknown_spec_raises() -> None:
    with pytest.raises(ValueError):
        resolve_range("since_the_dawn_of_time", date(2026, 7, 6))


def test_date_range_rejects_start_after_end() -> None:
    with pytest.raises(ValueError):
        DateRange(start=date(2026, 6, 1), end=date(2026, 1, 1))
