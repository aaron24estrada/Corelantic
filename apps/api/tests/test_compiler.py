from typing import Any

import pytest
from sqlalchemy import Select

from app.query.compiler import compile_query
from app.query.errors import CrossEntityError, TimeIntelligenceRequiredError
from app.query.intent import QueryIntent
from app.semantic.errors import (
    InvalidFormulaError,
    MixedEntityError,
    UnknownDimensionError,
    UnknownMetricError,
)
from app.semantic.models import (
    ComparisonMetric,
    CumulativeMetric,
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
                window="ytd",
            ),
            "leads_wow_pct": ComparisonMetric(
                name="leads_wow_pct",
                label="Leads WoW %",
                description="x",
                measure="lead_count",
                period="wow",
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


# --- time-based types are deferred to B4 ----------------------------------------------


def test_cumulative_metric_defers_to_time_intelligence() -> None:
    with pytest.raises(TimeIntelligenceRequiredError):
        compile_query(QueryIntent(metric="spend_ytd"), _registry())


def test_comparison_metric_defers_to_time_intelligence() -> None:
    with pytest.raises(TimeIntelligenceRequiredError):
        compile_query(QueryIntent(metric="leads_wow_pct"), _registry())


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
