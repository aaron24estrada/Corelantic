from datetime import date

import pytest
from sqlalchemy import column, select

from app.query.time import (
    DateBucket,
    DateRange,
    Grain,
    RelativeRange,
    nesting_grains,
    nests_in,
    resolve_range,
)


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
    got = resolve_range(RelativeRange.LAST_90_DAYS, date(2026, 7, 6))
    assert got == DateRange(start=date(2026, 4, 8), end=date(2026, 7, 6))


def test_resolve_month_and_year_to_date() -> None:
    assert resolve_range(RelativeRange.MONTH_TO_DATE, date(2026, 7, 6)).start == date(2026, 7, 1)
    assert resolve_range(RelativeRange.YEAR_TO_DATE, date(2026, 7, 6)).start == date(2026, 1, 1)


def test_an_unknown_relative_range_cannot_be_constructed() -> None:
    # A closed enum, so an invented window is rejected at the request boundary rather than
    # reaching resolve_range at all.
    with pytest.raises(ValueError):
        RelativeRange("since_the_dawn_of_time")


def test_days_nest_in_every_coarser_period() -> None:
    assert nests_in(Grain.DAY, Grain.MONTH)
    assert nests_in(Grain.MONTH, Grain.YEAR)
    assert nests_in(Grain.QUARTER, Grain.YEAR)


def test_a_week_does_not_nest_in_a_month() -> None:
    # The week that straddles a month boundary belongs to both, so a month-to-date over
    # weekly buckets has no honest answer.
    assert not nests_in(Grain.WEEK, Grain.MONTH)
    assert not nests_in(Grain.WEEK, Grain.QUARTER)
    assert nesting_grains(Grain.WEEK) == ["year"]


def test_nothing_nests_in_itself() -> None:
    for grain in Grain:
        assert not nests_in(grain, grain)


def test_date_range_rejects_start_after_end() -> None:
    with pytest.raises(ValueError):
        DateRange(start=date(2026, 6, 1), end=date(2026, 1, 1))
