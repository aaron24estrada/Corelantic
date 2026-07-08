import asyncio
from datetime import date
from typing import Any

import pytest

from app.adapters.data.fixture import FixtureDataSource
from app.core.config import get_settings
from app.query.compiler import compile_query
from app.query.intent import QueryIntent
from app.query.time import DateRange, Grain
from app.semantic.registry import load_registry


@pytest.fixture(scope="module")
def fixture_source() -> FixtureDataSource:
    # A small deterministic seed keeps the tests fast.
    return FixtureDataSource(leads=500, seed=1)


@pytest.fixture(scope="module")
def registry() -> Any:
    return load_registry(get_settings().semantic_dir)


def _run(source: FixtureDataSource, intent: QueryIntent, registry: Any) -> list[dict[str, Any]]:
    return asyncio.run(source.run(compile_query(intent, registry)))


def test_simple_metric_returns_the_seeded_count(
    fixture_source: FixtureDataSource, registry: Any
) -> None:
    rows = _run(fixture_source, QueryIntent(metric="new_leads"), registry)
    assert rows == [{"new_leads": 500}]


def test_ratio_metric_is_in_the_krw_ballpark(
    fixture_source: FixtureDataSource, registry: Any
) -> None:
    [row] = _run(fixture_source, QueryIntent(metric="roas"), registry)
    assert 2.0 < float(row["roas"]) < 5.0  # ROAS ~3.4x by construction


def test_join_across_entities_returns_rows_per_state(
    fixture_source: FixtureDataSource, registry: Any
) -> None:
    rows = _run(fixture_source, QueryIntent(metric="new_leads", group_by=["state"]), registry)
    assert {row["state"] for row in rows} <= {"TX", "CA", "AZ"}
    assert sum(int(row["new_leads"]) for row in rows) == 500  # every lead has a geo row


def test_grain_buckets_by_month(fixture_source: FixtureDataSource, registry: Any) -> None:
    rows = _run(fixture_source, QueryIntent(metric="marketing_spend", grain=Grain.MONTH), registry)
    assert len(rows) > 1  # data spans several months
    assert all("period" in row and "marketing_spend" in row for row in rows)


def test_date_range_narrows_the_result(fixture_source: FixtureDataSource, registry: Any) -> None:
    full = _run(fixture_source, QueryIntent(metric="new_leads"), registry)[0]["new_leads"]
    windowed = _run(
        fixture_source,
        QueryIntent(metric="new_leads", date_range=DateRange(start=date(2026, 1, 1))),
        registry,
    )[0]["new_leads"]
    assert 0 < int(windowed) < int(full)
