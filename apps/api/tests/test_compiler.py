from datetime import date
from typing import Any

import pytest
from sqlalchemy import Select

from app.query.compiler import compile_query
from app.query.errors import CrossEntityError, DateDimensionError
from app.query.intent import QueryIntent
from app.query.time import DateRange, Grain
from app.semantic.errors import (
    InvalidFormulaError,
    MixedEntityError,
    UnknownDimensionError,
    UnknownMetricError,
)
from app.semantic.models import (
    ComparisonMetric,
    ComparisonPeriod,
    CumulativeMetric,
    CumulativeWindow,
    DerivedMetric,
    Dimension,
    Entity,
    Measure,
    MetricFormat,
    RatioMetric,
    SemanticRegistry,
    SimpleMetric,
)


def _registry() -> SemanticRegistry:
    return SemanticRegistry(
        entities={
            "leads": Entity(name="leads", label="Leads", source="analytics.v_leads"),
            "cases": Entity(name="cases", label="Cases", source="analytics.v_cases"),
        },
        measures={
            "lead_count": Measure(name="lead_count", entity="leads", expression="count(*)"),
            "spend_total": Measure(name="spend_total", entity="leads", expression="sum(spend)"),
            "revenue_total": Measure(
                name="revenue_total", entity="leads", expression="sum(revenue)"
            ),
            "case_count": Measure(name="case_count", entity="cases", expression="count(*)"),
        },
        metrics={
            "new_leads": SimpleMetric(
                name="new_leads", label="New leads", description="x", measure="lead_count"
            ),
            "cost_per_lead": RatioMetric(
                name="cost_per_lead",
                label="Cost per lead",
                description="x",
                numerator="spend_total",
                denominator="lead_count",
                format=MetricFormat.CURRENCY,
            ),
            "roas": RatioMetric(
                name="roas",
                label="ROAS",
                description="x",
                numerator="revenue_total",
                denominator="spend_total",
            ),
            "margin_pct": DerivedMetric(
                name="margin_pct",
                label="Margin %",
                description="x",
                measures=["revenue_total", "spend_total"],
                expression="(revenue_total - spend_total) / revenue_total * 100",
            ),
            "spend_ytd": CumulativeMetric(
                name="spend_ytd",
                label="Spend YTD",
                description="x",
                measure="spend_total",
                window=CumulativeWindow.YTD,
            ),
            "leads_wow_pct": ComparisonMetric(
                name="leads_wow_pct",
                label="Leads WoW %",
                description="x",
                measure="lead_count",
                period=ComparisonPeriod.WOW,
            ),
            "leads_per_case": RatioMetric(
                name="leads_per_case",
                label="Leads per case",
                description="x",
                numerator="lead_count",  # on leads
                denominator="case_count",  # on cases — spans entities
            ),
        },
        dimensions={
            "channel": Dimension(name="channel", label="Channel", entity="leads", column="channel"),
            "region": Dimension(name="region", label="Region", entity="leads", column="metro"),
            "lead_date": Dimension(
                name="lead_date",
                label="Lead date",
                entity="leads",
                column="created_at",
                date_role="lead",
            ),
            "attorney": Dimension(
                name="attorney", label="Attorney", entity="cases", column="attorney"
            ),
        },
    )


def _rendered(statement: Select[Any]) -> tuple[str, dict[str, Any]]:
    # Collapse the dialect's clause-per-line layout so assertions read as one statement.
    compiled = statement.compile()
    return " ".join(str(compiled).split()), dict(compiled.params)


# --- simple ---------------------------------------------------------------------------


def test_simple_metric_surfaces_its_measure() -> None:
    sql, params = _rendered(compile_query(QueryIntent(metric="new_leads"), _registry()))
    assert sql == "SELECT count(*) AS new_leads FROM analytics.v_leads"
    assert params == {}


def test_simple_metric_with_group_by_and_filter() -> None:
    intent = QueryIntent(metric="new_leads", group_by=["channel"], filters={"region": "Houston"})
    sql, params = _rendered(compile_query(intent, _registry()))
    assert sql == (
        "SELECT channel AS channel, count(*) AS new_leads "
        "FROM analytics.v_leads WHERE metro = :metro_1 GROUP BY channel"
    )
    assert params == {"metro_1": "Houston"}


# --- ratio ----------------------------------------------------------------------------


def test_ratio_metric_divides_measures_guarding_zero() -> None:
    sql, _ = _rendered(compile_query(QueryIntent(metric="cost_per_lead"), _registry()))
    # numerator / nullif(denominator, 0), aliased to the metric name.
    assert "sum(spend) /" in sql
    assert "nullif(count(*)" in sql
    assert sql.endswith("AS cost_per_lead FROM analytics.v_leads")


def test_ratio_metric_roas() -> None:
    sql, _ = _rendered(compile_query(QueryIntent(metric="roas"), _registry()))
    assert "sum(revenue) /" in sql
    assert "nullif(sum(spend)" in sql
    assert "AS roas" in sql


def test_ratio_metric_groups_by_a_dimension() -> None:
    intent = QueryIntent(metric="cost_per_lead", group_by=["channel"])
    sql, _ = _rendered(compile_query(intent, _registry()))
    assert sql.startswith("SELECT channel AS channel,")
    assert sql.endswith("GROUP BY channel")


# --- derived --------------------------------------------------------------------------


def test_derived_metric_compiles_its_formula() -> None:
    sql, _ = _rendered(compile_query(QueryIntent(metric="margin_pct"), _registry()))
    assert "sum(revenue) - sum(spend)" in sql
    assert "nullif(sum(revenue)" in sql  # the division is zero-guarded
    assert "* 100" in sql
    assert "AS margin_pct" in sql


def test_derived_formula_referencing_a_measure_not_declared_raises() -> None:
    registry = _registry()
    registry.metrics["bad"] = DerivedMetric(
        name="bad",
        label="Bad",
        description="x",
        measures=["lead_count"],
        expression="lead_count + spend_total",  # spend_total not in measures
    )
    with pytest.raises(InvalidFormulaError):
        compile_query(QueryIntent(metric="bad"), registry)


def test_derived_formula_with_disallowed_syntax_raises() -> None:
    registry = _registry()
    registry.metrics["bad"] = DerivedMetric(
        name="bad",
        label="Bad",
        description="x",
        measures=["lead_count"],
        expression="evil(lead_count)",  # a call is not in the allowlist
    )
    with pytest.raises(InvalidFormulaError):
        compile_query(QueryIntent(metric="bad"), registry)


# --- grain bucketing ------------------------------------------------------------------


def test_grain_buckets_on_the_date_dimension() -> None:
    # The date dimension is inferred (the entity has exactly one), bucketed, and grouped.
    intent = QueryIntent(metric="new_leads", grain=Grain.MONTH)
    sql, _ = _rendered(compile_query(intent, _registry()))
    assert sql == (
        "SELECT date_trunc('month', created_at) AS period, count(*) AS new_leads "
        "FROM analytics.v_leads GROUP BY date_trunc('month', created_at)"
    )


def test_grain_combines_with_group_by() -> None:
    intent = QueryIntent(metric="new_leads", grain=Grain.WEEK, group_by=["channel"])
    sql, _ = _rendered(compile_query(intent, _registry()))
    assert sql.startswith("SELECT date_trunc('week', created_at) AS period, channel AS channel,")
    assert sql.endswith("GROUP BY date_trunc('week', created_at), channel")


def test_grain_without_a_date_dimension_raises() -> None:
    # cases has no temporal dimension.
    registry = _registry()
    registry.metrics["case_total"] = SimpleMetric(
        name="case_total", label="Cases", description="x", measure="case_count"
    )
    with pytest.raises(DateDimensionError):
        compile_query(QueryIntent(metric="case_total", grain=Grain.MONTH), registry)


# --- date ranges ----------------------------------------------------------------------


def test_date_range_binds_both_bounds() -> None:
    intent = QueryIntent(
        metric="new_leads", date_range=DateRange(start=date(2026, 1, 1), end=date(2026, 6, 30))
    )
    sql, params = _rendered(compile_query(intent, _registry()))
    # Upper bound is half-open (< end + 1 day) so a timestamp column still includes all
    # of the end date.
    assert sql == (
        "SELECT count(*) AS new_leads FROM analytics.v_leads "
        "WHERE created_at >= :created_at_1 AND created_at < :created_at_2"
    )
    assert set(params.values()) == {date(2026, 1, 1), date(2026, 7, 1)}


def test_open_ended_range_binds_one_bound() -> None:
    intent = QueryIntent(metric="new_leads", date_range=DateRange(start=date(2026, 1, 1)))
    sql, params = _rendered(compile_query(intent, _registry()))
    assert sql.endswith("WHERE created_at >= :created_at_1")
    assert list(params.values()) == [date(2026, 1, 1)]


# --- comparison (WoW/MoM) -------------------------------------------------------------


def test_comparison_computes_prior_period_pct_delta() -> None:
    sql, _ = _rendered(compile_query(QueryIntent(metric="leads_wow_pct"), _registry()))
    # Weekly buckets in a subquery; LAG gives the prior week; delta is guarded pct change.
    assert "date_trunc('week', created_at) AS period" in sql
    assert "lag(anon_1.value) OVER (ORDER BY anon_1.period)" in sql
    assert "nullif(lag(anon_1.value)" in sql  # zero-guarded division
    assert "AS leads_wow_pct" in sql


def test_comparison_change_kind_is_a_plain_difference() -> None:
    registry = _registry()
    registry.metrics["leads_wow"] = ComparisonMetric(
        name="leads_wow",
        label="Leads WoW",
        description="x",
        measure="lead_count",
        period=ComparisonPeriod.WOW,
        kind="change",
    )
    sql, _ = _rendered(compile_query(QueryIntent(metric="leads_wow"), registry))
    assert "anon_1.value - lag(anon_1.value) OVER (ORDER BY anon_1.period) AS leads_wow" in sql
    assert "nullif" not in sql  # a difference, not a ratio


def test_comparison_partitions_by_group_dimension() -> None:
    intent = QueryIntent(metric="leads_wow_pct", group_by=["channel"])
    sql, _ = _rendered(compile_query(intent, _registry()))
    assert "PARTITION BY anon_1.channel ORDER BY anon_1.period" in sql


# --- cumulative (MTD/YTD) -------------------------------------------------------------


def test_cumulative_is_a_running_total_resetting_each_window() -> None:
    intent = QueryIntent(metric="spend_ytd", grain=Grain.MONTH)
    sql, _ = _rendered(compile_query(intent, _registry()))
    assert "date_trunc('month', created_at) AS period" in sql  # accumulation grain
    assert (
        "sum(anon_1.value) OVER (PARTITION BY date_trunc('year', anon_1.period) "
        "ORDER BY anon_1.period ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)"
    ) in sql
    assert "AS spend_ytd" in sql


# --- date-dimension resolution --------------------------------------------------------


def test_named_non_date_dimension_is_rejected() -> None:
    with pytest.raises(DateDimensionError):
        compile_query(
            QueryIntent(metric="new_leads", grain=Grain.MONTH, date_dimension="channel"),
            _registry(),
        )


# --- guards -----------------------------------------------------------------------------


def test_filter_value_is_bound_never_interpolated() -> None:
    # A hostile value must land in the bound parameters, never in the SQL text — the
    # structural guarantee of building a Core statement instead of a string.
    hostile = "Houston'; DROP TABLE v_leads; --"
    statement = compile_query(
        QueryIntent(metric="new_leads", filters={"region": hostile}), _registry()
    )
    sql, params = _rendered(statement)
    assert hostile not in sql
    assert sql == "SELECT count(*) AS new_leads FROM analytics.v_leads WHERE metro = :metro_1"
    assert params == {"metro_1": hostile}


def test_unknown_metric_raises() -> None:
    with pytest.raises(UnknownMetricError):
        compile_query(QueryIntent(metric="missing"), _registry())


def test_unknown_dimension_raises() -> None:
    with pytest.raises(UnknownDimensionError):
        compile_query(QueryIntent(metric="new_leads", group_by=["missing"]), _registry())


def test_cross_entity_dimension_raises() -> None:
    with pytest.raises(CrossEntityError):
        compile_query(QueryIntent(metric="new_leads", group_by=["attorney"]), _registry())


def test_metric_mixing_entities_raises() -> None:
    with pytest.raises(MixedEntityError):
        compile_query(QueryIntent(metric="leads_per_case"), _registry())
