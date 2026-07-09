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

_CHANNELS = {
    "CTV",
    "Linear TV",
    "Phone/SMS",
    "Facebook",
    "Referral",
    "Unknown",
    "Other Social Media",
    "Website/Email",
    "Other",
}


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


def test_channel_breakdown_sums_to_total(fixture_source: FixtureDataSource, registry: Any) -> None:
    rows = _run(fixture_source, QueryIntent(metric="new_leads", group_by=["channel"]), registry)
    assert {row["channel"] for row in rows} <= _CHANNELS
    assert sum(int(row["new_leads"]) for row in rows) == 500


def test_group_by_state_keeps_leads_without_geo(
    fixture_source: FixtureDataSource, registry: Any
) -> None:
    # ~38% of leads have no geo row; the outer join must keep them as a NULL group, so the
    # per-state counts still sum to every lead (the dashboard's "(Blank)" bucket).
    rows = _run(fixture_source, QueryIntent(metric="new_leads", group_by=["state"]), registry)
    states = {row["state"] for row in rows}
    assert "TX" in states
    assert None in states  # leads with no geo survive as a NULL group
    assert sum(int(row["new_leads"]) for row in rows) == 500


def test_grain_buckets_by_month(fixture_source: FixtureDataSource, registry: Any) -> None:
    rows = _run(fixture_source, QueryIntent(metric="new_leads", grain=Grain.MONTH), registry)
    assert len(rows) > 1  # data spans several months
    assert all("period" in row and "new_leads" in row for row in rows)


def test_concurrent_reads_are_safe(fixture_source: FixtureDataSource, registry: Any) -> None:
    # The shared SQLite connection is lock-serialized; many parallel reads must all succeed.
    statement = compile_query(QueryIntent(metric="new_leads"), registry)

    async def many() -> list[list[dict[str, Any]]]:
        return await asyncio.gather(*[fixture_source.run(statement) for _ in range(24)])

    results = asyncio.run(many())
    assert all(rows == [{"new_leads": 500}] for rows in results)


def test_date_range_narrows_the_result(fixture_source: FixtureDataSource, registry: Any) -> None:
    full = _run(fixture_source, QueryIntent(metric="new_leads"), registry)[0]["new_leads"]
    windowed = _run(
        fixture_source,
        QueryIntent(metric="new_leads", date_range=DateRange(start=date(2026, 1, 1))),
        registry,
    )[0]["new_leads"]
    assert 0 < int(windowed) < int(full)
