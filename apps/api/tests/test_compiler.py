from datetime import date
from typing import Any

import pytest
from sqlalchemy import Select

from app.query.compiler import compile_query
from app.query.errors import (
    DateDimensionError,
    DimensionNotDefinedError,
    IncompatibleDimensionError,
    MetricNotDefinedError,
)
from app.query.intent import QueryIntent
from app.query.time import DateRange, Grain
from app.semantic.errors import (
    InvalidFormulaError,
    MixedEntityError,
)
from app.semantic.models import (
    Aggregation,
    Cardinality,
    ComparisonMetric,
    ComparisonPeriod,
    Constant,
    CumulativeMetric,
    CumulativeWindow,
    DerivedMetric,
    Dimension,
    Entity,
    JoinEdge,
    Measure,
    MeasureFilter,
    MetricFormat,
    RatioMetric,
    SemanticRegistry,
    SimpleMetric,
)


def _registry() -> SemanticRegistry:
    return SemanticRegistry(
        entities={
            "leads": Entity(
                name="leads",
                label="Leads",
                source="analytics.v_leads",
                joins=[
                    JoinEdge(to="geo", left="lead_id", right="lead_id"),
                    JoinEdge(
                        to="stages",
                        left="lead_id",
                        right="lead_id",
                        cardinality=Cardinality.ONE_TO_MANY,
                    ),
                ],
            ),
            "geo": Entity(name="geo", label="Geo", source="analytics.v_geo"),
            "stages": Entity(name="stages", label="Stages", source="analytics.v_stages"),
            "cases": Entity(name="cases", label="Cases", source="analytics.v_cases"),
        },
        measures={
            "lead_count": Measure(name="lead_count", entity="leads", agg=Aggregation.COUNT),
            "unique_leads": Measure(
                name="unique_leads",
                entity="leads",
                agg=Aggregation.COUNT,
                column="lead_id",
                distinct=True,
            ),
            "spend_total": Measure(
                name="spend_total", entity="leads", agg=Aggregation.SUM, column="spend"
            ),
            "revenue_total": Measure(
                name="revenue_total", entity="leads", agg=Aggregation.SUM, column="revenue"
            ),
            "case_count": Measure(name="case_count", entity="cases", agg=Aggregation.COUNT),
            "voucher_reached": Measure(
                name="voucher_reached",
                entity="stages",
                agg=Aggregation.COUNT,
                column="lead_id",
                distinct=True,
                filter=MeasureFilter(column="name", equals="Voucher"),
            ),
            "stage_rows": Measure(
                name="stage_rows",
                entity="stages",
                agg=Aggregation.COUNT,
                filter=MeasureFilter(column="name", equals="Voucher"),
            ),
            "linked_count": Measure(
                name="linked_count", entity="stages", agg=Aggregation.COUNT, column="lead_id"
            ),
        },
        metrics={
            "new_leads": SimpleMetric(
                name="new_leads", label="New leads", description="x", measure="lead_count"
            ),
            "unique": SimpleMetric(
                name="unique", label="Unique leads", description="x", measure="unique_leads"
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
            "vouchers": SimpleMetric(
                name="vouchers", label="Vouchers", description="x", measure="voucher_reached"
            ),
            "revenue": DerivedMetric(
                name="revenue",
                label="Revenue",
                description="x",
                measures=["voucher_reached"],
                expression="voucher_reached * case_fee",
                format=MetricFormat.CURRENCY,
            ),
            "voucher_rows": SimpleMetric(
                name="voucher_rows", label="Voucher rows", description="x", measure="stage_rows"
            ),
            "linked_calls": SimpleMetric(
                name="linked_calls", label="Linked", description="x", measure="linked_count"
            ),
            "leads_per_case": RatioMetric(
                name="leads_per_case",
                label="Leads per case",
                description="x",
                numerator="lead_count",  # on leads
                denominator="case_count",  # on cases — spans entities
            ),
        },
        constants={
            "case_fee": Constant(name="case_fee", value=6000, description="Fee per case."),
        },
        dimensions={
            "channel": Dimension(name="channel", label="Channel", entity="leads", column="channel"),
            "region": Dimension(name="region", label="Region", entity="leads", column="metro"),
            "state": Dimension(name="state", label="State", entity="geo", column="state"),
            "lead_date": Dimension(
                name="lead_date",
                label="Lead date",
                entity="leads",
                column="created_at",
                date_role="lead",
            ),
            "stage_name": Dimension(
                name="stage_name", label="Stage", entity="stages", column="name"
            ),
            "stage_date": Dimension(
                name="stage_date",
                label="Stage date",
                entity="stages",
                column="completed_at",
                date_role="stage",
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


# --- simple + structural measures -----------------------------------------------------


def test_simple_metric_surfaces_its_measure() -> None:
    sql, params = _rendered(compile_query(QueryIntent(metric="new_leads"), _registry()))
    assert sql == "SELECT count(*) AS new_leads FROM analytics.v_leads AS leads"
    assert params == {}


def test_columns_are_table_qualified() -> None:
    intent = QueryIntent(metric="new_leads", group_by=["channel"], filters={"region": "Houston"})
    sql, params = _rendered(compile_query(intent, _registry()))
    assert sql == (
        "SELECT leads.channel AS channel, count(*) AS new_leads FROM analytics.v_leads AS leads "
        "WHERE leads.metro = :metro_1 GROUP BY leads.channel"
    )
    assert params == {"metro_1": "Houston"}


def test_count_with_a_column_counts_non_nulls_not_rows() -> None:
    # Several metrics lean on this: count(answer_time) is "calls picked up", count(LeadId)
    # is "calls linked to a lead". A count measure with a column must not become count(*).
    sql, _ = _rendered(compile_query(QueryIntent(metric="linked_calls"), _registry()))
    assert "count(stages.lead_id)" in sql
    assert "count(*)" not in sql


def test_sum_measure_qualifies_its_column() -> None:
    sql, _ = _rendered(compile_query(QueryIntent(metric="cost_per_lead"), _registry()))
    assert "sum(leads.spend) /" in sql
    assert "nullif(count(*)" in sql


# --- joins across entities ------------------------------------------------------------


def test_group_by_dimension_on_another_entity_joins() -> None:
    # The acceptance case: a leads metric sliced by geo.state, joined on the key edge.
    sql, _ = _rendered(
        compile_query(QueryIntent(metric="new_leads", group_by=["state"]), _registry())
    )
    assert sql == (
        "SELECT geo.state AS state, count(*) AS new_leads "
        "FROM analytics.v_leads AS leads LEFT OUTER JOIN analytics.v_geo AS geo "
        "ON leads.lead_id = geo.lead_id GROUP BY geo.state"
    )


def test_distinct_count_of_join_key_is_unambiguous() -> None:
    # The whole point of structural measures: lead_id is on both tables, but the measure's
    # column is bound to its own entity, so the distinct count is qualified.
    sql, _ = _rendered(compile_query(QueryIntent(metric="unique", group_by=["state"]), _registry()))
    assert "count(DISTINCT leads.lead_id)" in sql
    assert "JOIN analytics.v_geo AS geo ON leads.lead_id = geo.lead_id" in sql


def test_filter_on_joined_entity_joins() -> None:
    intent = QueryIntent(metric="new_leads", filters={"state": "TX"})
    sql, params = _rendered(compile_query(intent, _registry()))
    assert "JOIN analytics.v_geo AS geo" in sql
    assert "WHERE geo.state = :state_1" in sql
    assert params == {"state_1": "TX"}


def test_dimension_with_no_join_path_raises() -> None:
    # cases has no join edge to leads.
    with pytest.raises(IncompatibleDimensionError) as caught:
        compile_query(QueryIntent(metric="new_leads", group_by=["attorney"]), _registry())
    assert "not related" in str(caught.value)
    assert "attorney" not in caught.value.allowed


def test_one_to_many_join_is_rejected_to_avoid_fan_out() -> None:
    # leads → stages is one-to-many; joining it would inflate count(*), so reject it.
    with pytest.raises(IncompatibleDimensionError) as caught:
        compile_query(QueryIntent(metric="new_leads", group_by=["stage_name"]), _registry())
    assert "inflate" in str(caught.value)


def test_a_rejected_dimension_names_the_ones_that_would_have_worked() -> None:
    # `allowed` is what lets the agent repair its intent instead of retrying blind.
    with pytest.raises(IncompatibleDimensionError) as caught:
        compile_query(QueryIntent(metric="new_leads", group_by=["stage_name"]), _registry())
    assert "state" in caught.value.allowed
    assert caught.value.field == "group_by"


def test_fact_to_dimension_join_is_left_outer() -> None:
    # Regression (#36): inner join drops facts with no dimension row, understating counts.
    sql, _ = _rendered(
        compile_query(QueryIntent(metric="new_leads", group_by=["state"]), _registry())
    )
    assert "LEFT OUTER JOIN analytics.v_geo AS geo" in sql
    assert "JOIN analytics.v_geo" in sql and " INNER JOIN " not in sql


def test_filter_on_a_joined_dimension_still_constrains() -> None:
    # A filter on a joined dimension is a real predicate: it excludes NULLs. Correct, not
    # a regression of the outer join — "(Blank)" only appears when grouping.
    sql, params = _rendered(
        compile_query(QueryIntent(metric="new_leads", filters={"state": "TX"}), _registry())
    )
    assert "LEFT OUTER JOIN analytics.v_geo AS geo" in sql
    assert "WHERE geo.state = :state_1" in sql
    assert params == {"state_1": "TX"}


# --- filtered measures ----------------------------------------------------------------


def test_filtered_measure_scopes_the_aggregate_with_a_case() -> None:
    # SQL Server has no FILTER clause, so the predicate becomes a CASE inside the aggregate:
    # rows outside it are NULL and drop out. Distinct still applies to the CASE result.
    sql, params = _rendered(compile_query(QueryIntent(metric="vouchers"), _registry()))
    assert "count(DISTINCT CASE WHEN (stages.name = :name_1) THEN stages.lead_id END)" in sql
    assert params == {"name_1": "Voucher"}


def test_filtered_measure_value_is_bound_never_interpolated() -> None:
    sql, params = _rendered(compile_query(QueryIntent(metric="vouchers"), _registry()))
    assert "Voucher" not in sql  # the value reaches SQL only as a bound parameter
    assert params["name_1"] == "Voucher"


def test_filtered_count_of_rows_counts_a_case() -> None:
    # count(*) has no column; filtered, it counts a CASE that is 1 where the predicate holds.
    sql, _ = _rendered(compile_query(QueryIntent(metric="voucher_rows"), _registry()))
    assert "count(CASE WHEN (stages.name = :name_1) THEN :param_1 END)" in sql


def test_slicing_by_a_filtered_column_is_rejected() -> None:
    # "vouchers by stage" is malformed: the filter pins the stage, so every other group is
    # empty. Refuse it rather than answer 100% / 0%.
    with pytest.raises(IncompatibleDimensionError) as caught:
        compile_query(QueryIntent(metric="vouchers", group_by=["stage_name"]), _registry())
    assert "aggregate to nothing" in str(caught.value)

    filtered = QueryIntent(metric="vouchers", filters={"stage_name": "Voucher"})
    with pytest.raises(IncompatibleDimensionError) as caught:
        compile_query(filtered, _registry())
    assert caught.value.field == "filters"


def test_filtered_measure_can_still_be_sliced_by_another_dimension() -> None:
    # Vouchers by channel is the useful case: stages → leads is many_to_one, so it joins.
    intent = QueryIntent(metric="vouchers", group_by=["channel"])
    sql, _ = _rendered(compile_query(intent, _registry()))
    assert "count(DISTINCT CASE WHEN" in sql
    assert "GROUP BY leads.channel" in sql


def test_date_dimension_on_a_safely_joined_entity_is_allowed() -> None:
    # A funnel metric lives on stages but trends by the lead's intake date on leads —
    # reachable many-to-one, so joining it neither fans out nor changes the aggregate.
    intent = QueryIntent(metric="vouchers", grain=Grain.MONTH, date_dimension="lead_date")
    sql, _ = _rendered(compile_query(intent, _registry()))
    assert "date_trunc('month', leads.created_at)" in sql
    assert "FROM analytics.v_stages AS stages LEFT OUTER JOIN analytics.v_leads AS leads" in sql


def test_date_dimension_across_a_fan_out_join_is_rejected() -> None:
    # leads → stages fans out; bucketing a lead metric by a stage date would inflate it.
    intent = QueryIntent(metric="new_leads", grain=Grain.MONTH, date_dimension="stage_date")
    with pytest.raises(DateDimensionError):
        compile_query(intent, _registry())


def test_ambiguous_date_dimensions_must_be_named() -> None:
    # stages owns stage_date and can also reach lead_date. Which one a trend means changes
    # the answer, so refuse to guess — never silently re-anchor on the base's own date.
    intent = QueryIntent(metric="vouchers", grain=Grain.MONTH)
    with pytest.raises(DateDimensionError):
        compile_query(intent, _registry())


def test_date_range_on_a_joined_date_filters_the_joined_column() -> None:
    # An unmatched (NULL) joined date is excluded by a range — the same, correct semantics
    # as a NULL date column: a row we cannot date is in no date window.
    intent = QueryIntent(
        metric="vouchers",
        date_dimension="lead_date",
        date_range=DateRange(start=date(2026, 1, 1), end=date(2026, 3, 31)),
    )
    sql, params = _rendered(compile_query(intent, _registry()))
    assert "WHERE leads.created_at >= :created_at_1 AND leads.created_at < :created_at_2" in sql
    assert params["created_at_1"] == date(2026, 1, 1)


def test_temporal_metrics_exclude_undated_rows() -> None:
    # A NULL bucket would sort ahead of every real period and LAG would read across it.
    sql, _ = _rendered(compile_query(QueryIntent(metric="leads_wow_pct"), _registry()))
    assert "leads.created_at IS NOT NULL" in sql


def test_filter_column_is_added_to_the_plan_and_qualified() -> None:
    # The predicate's column is not the aggregated one; it must still be bound to its table.
    sql, _ = _rendered(compile_query(QueryIntent(metric="vouchers"), _registry()))
    assert "FROM analytics.v_stages AS stages" in sql
    assert "stages.name" in sql and "stages.lead_id" in sql


# --- ratio / derived ------------------------------------------------------------------


def test_ratio_metric_divides_measures_guarding_zero() -> None:
    sql, _ = _rendered(compile_query(QueryIntent(metric="roas"), _registry()))
    assert "sum(leads.revenue) /" in sql
    assert "nullif(sum(leads.spend)" in sql
    assert "AS roas" in sql


def test_derived_metric_compiles_its_formula() -> None:
    sql, _ = _rendered(compile_query(QueryIntent(metric="margin_pct"), _registry()))
    assert "sum(leads.revenue) - sum(leads.spend)" in sql
    assert "nullif(sum(leads.revenue)" in sql
    assert "* :param_1" in sql  # numeric literals bind, never inline
    assert "AS margin_pct" in sql


def test_derived_formula_binds_a_registry_constant() -> None:
    # The case fee reaches SQL as a bound parameter, never interpolated into the text.
    sql, params = _rendered(compile_query(QueryIntent(metric="revenue"), _registry()))
    assert "count(DISTINCT CASE WHEN" in sql and "* :param_1" in sql
    assert params["param_1"] == 6000
    assert "6000" not in sql


def test_derived_formula_referencing_a_measure_not_declared_raises() -> None:
    registry = _registry()
    registry.metrics["bad"] = DerivedMetric(
        name="bad",
        label="Bad",
        description="x",
        measures=["lead_count"],
        expression="lead_count + spend_total",
    )
    with pytest.raises(InvalidFormulaError):
        compile_query(QueryIntent(metric="bad"), registry)


# --- grain bucketing ------------------------------------------------------------------


def test_grain_buckets_on_the_date_dimension() -> None:
    sql, _ = _rendered(
        compile_query(QueryIntent(metric="new_leads", grain=Grain.MONTH), _registry())
    )
    assert sql == (
        "SELECT date_trunc('month', leads.created_at) AS period, count(*) AS new_leads "
        "FROM analytics.v_leads AS leads GROUP BY date_trunc('month', leads.created_at)"
    )


def test_grain_without_a_date_dimension_raises() -> None:
    registry = _registry()
    registry.metrics["case_total"] = SimpleMetric(
        name="case_total", label="Cases", description="x", measure="case_count"
    )
    with pytest.raises(DateDimensionError):
        compile_query(QueryIntent(metric="case_total", grain=Grain.MONTH), registry)


# --- date ranges ----------------------------------------------------------------------


def test_date_range_is_half_open() -> None:
    intent = QueryIntent(
        metric="new_leads", date_range=DateRange(start=date(2026, 1, 1), end=date(2026, 6, 30))
    )
    sql, params = _rendered(compile_query(intent, _registry()))
    assert sql == (
        "SELECT count(*) AS new_leads FROM analytics.v_leads AS leads "
        "WHERE leads.created_at >= :created_at_1 AND leads.created_at < :created_at_2"
    )
    assert set(params.values()) == {date(2026, 1, 1), date(2026, 7, 1)}


# --- comparison / cumulative ----------------------------------------------------------


def test_comparison_computes_prior_period_pct_delta() -> None:
    sql, _ = _rendered(compile_query(QueryIntent(metric="leads_wow_pct"), _registry()))
    assert "date_trunc('week', leads.created_at) AS period" in sql
    assert "lag(anon_1.value) OVER (ORDER BY anon_1.period)" in sql
    assert "nullif(lag(anon_1.value)" in sql
    assert "AS leads_wow_pct" in sql


def test_comparison_partitions_by_group_dimension() -> None:
    sql, _ = _rendered(
        compile_query(QueryIntent(metric="leads_wow_pct", group_by=["channel"]), _registry())
    )
    assert "PARTITION BY anon_1.channel ORDER BY anon_1.period" in sql


def test_cumulative_is_a_running_total_resetting_each_window() -> None:
    sql, _ = _rendered(
        compile_query(QueryIntent(metric="spend_ytd", grain=Grain.MONTH), _registry())
    )
    assert "sum(leads.spend) AS value" in sql
    assert (
        "sum(anon_1.value) OVER (PARTITION BY date_trunc('year', anon_1.period) "
        "ORDER BY anon_1.period ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)"
    ) in sql


# --- guards ---------------------------------------------------------------------------


def test_filter_value_is_bound_never_interpolated() -> None:
    hostile = "Houston'; DROP TABLE v_leads; --"
    statement = compile_query(
        QueryIntent(metric="new_leads", filters={"region": hostile}), _registry()
    )
    sql, params = _rendered(statement)
    assert hostile not in sql
    assert params == {"metro_1": hostile}


def test_unknown_metric_raises() -> None:
    with pytest.raises(MetricNotDefinedError) as caught:
        compile_query(QueryIntent(metric="missing"), _registry())
    assert "new_leads" in caught.value.allowed


def test_unknown_dimension_raises() -> None:
    with pytest.raises(DimensionNotDefinedError) as caught:
        compile_query(QueryIntent(metric="new_leads", group_by=["missing"]), _registry())
    assert caught.value.field == "group_by"


def test_metric_mixing_entities_raises() -> None:
    with pytest.raises(MixedEntityError):
        compile_query(QueryIntent(metric="leads_per_case"), _registry())
