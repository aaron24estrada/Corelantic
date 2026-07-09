import asyncio
from datetime import date
from typing import Any

import pytest

from app.adapters.data.fixture import FixtureDataSource
from app.core.config import get_settings
from app.query.compiler import compile_query
from app.query.intent import QueryIntent
from app.query.time import DateRange, Grain
from app.semantic.errors import JoinFanOutError
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


def test_funnel_stages_drop_off_monotonically(
    fixture_source: FixtureDataSource, registry: Any
) -> None:
    reached = [
        int(_run(fixture_source, QueryIntent(metric=metric), registry)[0][metric])
        for metric in (
            "vouchers",
            "leads_reached_xray",
            "leads_reached_bread",
            "leads_reached_bank_complete",
        )
    ]
    assert reached[0] < 500  # not every lead reaches voucher
    assert reached == sorted(reached, reverse=True)  # each stage is a subset of the prior


def test_voucher_rate_matches_the_source_ballpark(
    fixture_source: FixtureDataSource, registry: Any
) -> None:
    [row] = _run(fixture_source, QueryIntent(metric="voucher_rate"), registry)
    assert 0.18 < float(row["voucher_rate"]) < 0.30  # ~24% in the real funnel


def test_funnel_trends_by_the_joined_lead_date(
    fixture_source: FixtureDataSource, registry: Any
) -> None:
    # stages has no date of its own; the compiler reaches cases.CreateDate many-to-one. Each
    # lead sits in exactly one bucket, so the months must sum back to the ungrouped total.
    total = int(_run(fixture_source, QueryIntent(metric="vouchers"), registry)[0]["vouchers"])
    rows = _run(fixture_source, QueryIntent(metric="vouchers", grain=Grain.MONTH), registry)
    assert len(rows) > 1
    assert sum(int(row["vouchers"]) for row in rows) == total


def test_funnel_respects_a_date_range(fixture_source: FixtureDataSource, registry: Any) -> None:
    full = _run(fixture_source, QueryIntent(metric="vouchers"), registry)[0]["vouchers"]
    windowed = _run(
        fixture_source,
        QueryIntent(metric="vouchers", date_range=DateRange(start=date(2026, 1, 1))),
        registry,
    )[0]["vouchers"]
    assert 0 < int(windowed) < int(full)


def test_revenue_values_vouchers_at_the_case_fee(
    fixture_source: FixtureDataSource, registry: Any
) -> None:
    vouchers = int(_run(fixture_source, QueryIntent(metric="vouchers"), registry)[0]["vouchers"])
    revenue = float(_run(fixture_source, QueryIntent(metric="revenue"), registry)[0]["revenue"])
    assert revenue == vouchers * registry.constant("case_fee").value


def test_lead_metric_grouped_by_stage_is_rejected(registry: Any) -> None:
    # cases → stages is one_to_many; joining would inflate the lead count, so refuse it.
    with pytest.raises(JoinFanOutError):
        compile_query(QueryIntent(metric="new_leads", group_by=["stage_name"]), registry)


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
