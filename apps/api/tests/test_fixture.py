import asyncio
from datetime import date
from itertools import pairwise
from typing import Any

import pytest

from app.adapters.data.fixture import FixtureDataSource
from app.core.config import get_settings
from app.query.compiler import compile_query
from app.query.errors import DateDimensionError, IncompatibleDimensionError, NotAdditiveError
from app.query.intent import Accumulation, Comparison, QueryIntent
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
    with pytest.raises(IncompatibleDimensionError) as caught:
        compile_query(QueryIntent(metric="new_leads", group_by=["stage_name"]), registry)
    assert sorted(caught.value.allowed) == ["channel", "lead_date", "state", "status"]


def _value(source: FixtureDataSource, metric: str, registry: Any) -> float:
    return float(_run(source, QueryIntent(metric=metric), registry)[0][metric])


def test_call_direction_splits_sum_to_total(
    fixture_source: FixtureDataSource, registry: Any
) -> None:
    total = _value(fixture_source, "total_calls", registry)
    inbound = _value(fixture_source, "inbound_calls", registry)
    outbound = _value(fixture_source, "outbound_calls", registry)
    assert inbound + outbound == total


def test_answered_calls_come_from_answer_time_not_the_disposition(
    fixture_source: FixtureDataSource, registry: Any
) -> None:
    # A call was picked up exactly when it has an answer_time, and COUNT skips NULLs. Some
    # hang_up calls were answered first, so this must exceed a call_result='answered' count.
    answered = _value(fixture_source, "calls_answered", registry)
    total = _value(fixture_source, "total_calls", registry)
    intent = QueryIntent(metric="total_calls", group_by=["call_result"])
    by_result = _run(fixture_source, intent, registry)
    disposition = next(int(r["total_calls"]) for r in by_result if r["call_result"] == "answered")
    assert disposition < answered < total
    assert 0.75 < _value(fixture_source, "answer_rate", registry) < 0.85  # ~80.9% in the source


def test_calls_linked_to_lead_skips_unlinked_calls(
    fixture_source: FixtureDataSource, registry: Any
) -> None:
    # LeadId is NULL on unlinked calls; count(LeadId) drops them without a join.
    linked = _value(fixture_source, "calls_linked_to_lead", registry)
    assert 0 < linked < _value(fixture_source, "total_calls", registry)
    assert 0.42 < _value(fixture_source, "call_to_lead_rate", registry) < 0.58  # ~50.8%


def test_unique_calls_never_exceeds_call_rows(
    fixture_source: FixtureDataSource, registry: Any
) -> None:
    # A row is a call leg: distinct call_id is at most the row count, ~89% of it.
    unique = _value(fixture_source, "unique_calls", registry)
    total = _value(fixture_source, "total_calls", registry)
    assert unique <= total
    assert 0.82 < unique / total < 0.95


def test_call_duration_is_seconds_not_milliseconds(
    fixture_source: FixtureDataSource, registry: Any
) -> None:
    # duration averages ~114s in the source; read as milliseconds this tile is 1000x wrong.
    assert 1.2 < _value(fixture_source, "avg_call_duration_min", registry) < 2.6


def test_agent_conversion_is_pooled_not_a_mean_of_rates(
    fixture_source: FixtureDataSource, registry: Any
) -> None:
    # sum(converted)/sum(contacted), not avg(conversion_rate_pct) — averaging ratios reads
    # 2.65% against a true 4.44% in the source.
    contacted = _value(fixture_source, "leads_contacted", registry)
    converted = _value(fixture_source, "leads_converted", registry)
    rate = _value(fixture_source, "agent_conversion_rate", registry)
    assert rate == pytest.approx(converted / contacted)
    assert 0.03 < rate < 0.06  # pooled 4.44% in the source


def test_call_metrics_cannot_reach_the_lead_tables(registry: Any) -> None:
    # zoom_calls declares no join, on purpose: reaching cases would make lead_date compete
    # with call_date and force every call trend to name a date dimension.
    with pytest.raises(IncompatibleDimensionError):
        compile_query(QueryIntent(metric="total_calls", group_by=["channel"]), registry)
    with pytest.raises(DateDimensionError):
        compile_query(
            QueryIntent(metric="total_calls", grain=Grain.MONTH, date_dimension="lead_date"),
            registry,
        )


def test_call_metrics_trend_on_the_call_date(
    fixture_source: FixtureDataSource, registry: Any
) -> None:
    # zoom_calls declares no join, so call_date is the only reachable date: no ambiguity.
    total = _value(fixture_source, "total_calls", registry)
    rows = _run(fixture_source, QueryIntent(metric="total_calls", grain=Grain.MONTH), registry)
    assert len(rows) > 1
    assert sum(int(row["total_calls"]) for row in rows) == total


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


# --- time intelligence on the intent --------------------------------------------------


def test_week_over_week_of_a_ratio_matches_a_hand_computed_series(
    fixture_source: FixtureDataSource, registry: Any
) -> None:
    """The claim the whole design rests on, checked against real numbers.

    A comparison used to be able to wrap only a bare measure, so "voucher rate week over
    week" was unrepresentable. The ratio must be recomputed *inside* each bucket and then
    compared — not a global ratio reweighted.
    """

    from sqlalchemy import case, column, distinct, func, select, table

    from app.query.time import DateBucket

    intent = QueryIntent(
        metric="voucher_rate", grain=Grain.WEEK, compare=Comparison(), date_dimension="lead_date"
    )
    got = {row["period"]: row for row in _run(fixture_source, intent, registry)}

    # Recompute numerator/denominator per week straight from the tables.
    stages = table("stages", column("LeadId"), column("StageName"), schema="gold_tspot").alias("s")
    cases = table("cases", column("LeadId"), column("CreateDate"), schema="gold_tspot").alias("c")
    bucket = DateBucket(Grain.WEEK, cases.c.CreateDate)
    manual = (
        select(
            bucket.label("period"),
            func.count(
                distinct(case((stages.c.StageName == "Voucher (Initial Intake)", stages.c.LeadId)))
            ).label("numerator"),
            func.count(distinct(stages.c.LeadId)).label("denominator"),
        )
        .select_from(stages.join(cases, stages.c.LeadId == cases.c.LeadId, isouter=True))
        .where(cases.c.CreateDate.is_not(None))
        .group_by(bucket)
    )
    expected = asyncio.run(fixture_source.run(manual))

    checked = 0
    for row in expected:
        if not row["denominator"]:
            continue
        rate = float(row["numerator"]) / float(row["denominator"])  # type: ignore[arg-type]
        assert got[row["period"]]["voucher_rate"] == pytest.approx(rate)
        checked += 1
    assert checked > 100


def test_a_percent_metrics_delta_is_the_difference_in_points(
    fixture_source: FixtureDataSource, registry: Any
) -> None:
    intent = QueryIntent(
        metric="voucher_rate", grain=Grain.WEEK, compare=Comparison(), date_dimension="lead_date"
    )
    rows = _run(fixture_source, intent, registry)
    for earlier, later in pairwise(rows):
        assert later["previous"] == pytest.approx(earlier["voucher_rate"])
        assert later["delta"] == pytest.approx(later["voucher_rate"] - earlier["voucher_rate"])


def test_revenue_accumulates_because_it_declares_itself_additive(
    fixture_source: FixtureDataSource, registry: Any
) -> None:
    monthly = _run(
        fixture_source,
        QueryIntent(metric="revenue", grain=Grain.MONTH, date_dimension="lead_date"),
        registry,
    )
    running = _run(
        fixture_source,
        QueryIntent(
            metric="revenue",
            grain=Grain.MONTH,
            date_dimension="lead_date",
            accumulate=Accumulation(reset=Grain.YEAR),
        ),
        registry,
    )
    by_period = {row["period"]: row["revenue"] for row in monthly}

    total = 0.0
    for row in running:
        period = row["period"]
        assert isinstance(period, date)
        if period.month == 1:
            total = 0.0
        total += float(by_period[period])
        assert row["revenue"] == pytest.approx(total)


def test_a_rate_cannot_be_accumulated(fixture_source: FixtureDataSource, registry: Any) -> None:
    # Summing weekly voucher rates does not produce a voucher rate.
    with pytest.raises(NotAdditiveError) as caught:
        _run(
            fixture_source,
            QueryIntent(
                metric="voucher_rate",
                grain=Grain.MONTH,
                date_dimension="lead_date",
                accumulate=Accumulation(reset=Grain.YEAR),
            ),
            registry,
        )
    assert "revenue" in caught.value.allowed
    assert "voucher_rate" not in caught.value.allowed
