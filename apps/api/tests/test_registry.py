import pytest
from pydantic import ValidationError

from app.semantic.errors import (
    DuplicateJoinError,
    InvalidFormulaError,
    MixedEntityError,
    UnknownDimensionError,
    UnknownEntityError,
    UnknownMeasureError,
    UnknownMetricError,
)
from app.semantic.models import (
    Aggregation,
    DerivedMetric,
    MetricFormat,
    MetricType,
    RatioMetric,
    SimpleMetric,
)
from app.semantic.registry import build_registry, validate_registry


def _raw() -> dict[str, object]:
    return {
        "entities": {
            "leads": {"label": "Leads", "source": "analytics.v_leads"},
        },
        "measures": {
            "spend_total": {"entity": "leads", "agg": "sum", "column": "spend"},
            "lead_count": {"entity": "leads", "agg": "count"},
            "revenue_total": {"entity": "leads", "agg": "sum", "column": "revenue"},
        },
        "metrics": {
            # No `type` — defaults to simple.
            "new_leads": {
                "label": "New leads",
                "description": "Lead count.",
                "measure": "lead_count",
            },
            "marketing_spend": {
                "label": "Marketing spend",
                "description": "Total spend.",
                "measure": "spend_total",
                "format": "currency",
            },
            "cost_per_lead": {
                "type": "ratio",
                "label": "Cost per lead",
                "description": "Spend over leads.",
                "numerator": "spend_total",
                "denominator": "lead_count",
                "format": "currency",
            },
            "margin_pct": {
                "type": "derived",
                "label": "Margin %",
                "description": "Margin.",
                "measures": ["revenue_total", "spend_total"],
                "expression": "(revenue_total - spend_total) / revenue_total * 100",
            },
        },
        "dimensions": {
            "channel": {"label": "Channel", "entity": "leads", "column": "channel"},
        },
    }


def test_build_registry_injects_names_and_discriminates_types() -> None:
    registry = build_registry(_raw())

    new_leads = registry.metric("new_leads")
    assert isinstance(new_leads, SimpleMetric)
    assert new_leads.type is MetricType.SIMPLE  # defaulted
    assert new_leads.format is MetricFormat.NUMBER

    cost_per_lead = registry.metric("cost_per_lead")
    assert isinstance(cost_per_lead, RatioMetric)
    assert cost_per_lead.numerator == "spend_total"
    assert cost_per_lead.format is MetricFormat.CURRENCY

    margin = registry.metric("margin_pct")
    assert isinstance(margin, DerivedMetric)
    assert margin.measures == ["revenue_total", "spend_total"]

    assert registry.measure("lead_count").agg is Aggregation.COUNT
    assert registry.dimension("channel").column == "channel"


def test_validate_registry_accepts_resolvable_references() -> None:
    registry = build_registry(_raw())
    assert validate_registry(registry) is registry


def test_validate_registry_rejects_ratio_with_missing_measure() -> None:
    registry = build_registry(
        {
            "entities": {"leads": {"label": "Leads", "source": "analytics.v_leads"}},
            "measures": {"lead_count": {"entity": "leads", "agg": "count"}},
            "metrics": {
                "bad": {
                    "type": "ratio",
                    "label": "Bad",
                    "description": "x",
                    "numerator": "lead_count",
                    "denominator": "does_not_exist",
                },
            },
        }
    )
    with pytest.raises(UnknownMeasureError):
        validate_registry(registry)


def test_validate_registry_rejects_derived_with_undeclared_measure_in_formula() -> None:
    registry = build_registry(
        {
            "entities": {"leads": {"label": "Leads", "source": "analytics.v_leads"}},
            "measures": {
                "lead_count": {"entity": "leads", "agg": "count"},
                "spend_total": {"entity": "leads", "agg": "sum", "column": "spend"},
            },
            "metrics": {
                "bad": {
                    "type": "derived",
                    "label": "Bad",
                    "description": "x",
                    "measures": ["lead_count"],
                    "expression": "lead_count + spend_total",  # spend_total not declared
                },
            },
        }
    )
    with pytest.raises(InvalidFormulaError):
        validate_registry(registry)


def test_build_registry_rejects_unknown_fields() -> None:
    # A ratio that forgot `type: ratio` defaults to simple; its numerator/denominator are
    # then unknown fields and must fail loudly rather than be silently dropped.
    with pytest.raises(ValidationError):
        build_registry(
            {
                "metrics": {
                    "cost_per_lead": {
                        "label": "Cost per lead",
                        "description": "x",
                        "numerator": "spend_total",
                        "denominator": "lead_count",
                    },
                },
            }
        )


def test_validate_registry_rejects_metric_mixing_entities() -> None:
    registry = build_registry(
        {
            "entities": {
                "leads": {"label": "Leads", "source": "analytics.v_leads"},
                "cases": {"label": "Cases", "source": "analytics.v_cases"},
            },
            "measures": {
                "lead_count": {"entity": "leads", "agg": "count"},
                "case_count": {"entity": "cases", "agg": "count"},
            },
            "metrics": {
                "leads_per_case": {
                    "type": "ratio",
                    "label": "Leads per case",
                    "description": "x",
                    "numerator": "lead_count",
                    "denominator": "case_count",
                },
            },
        }
    )
    with pytest.raises(MixedEntityError):
        validate_registry(registry)


def test_validate_registry_rejects_two_join_edges_to_the_same_target() -> None:
    registry = build_registry(
        {
            "entities": {
                "leads": {
                    "label": "Leads",
                    "source": "analytics.v_leads",
                    "joins": [
                        {"to": "geo", "left": "lead_id", "right": "lead_id"},
                        {"to": "geo", "left": "other_id", "right": "id"},
                    ],
                },
                "geo": {"label": "Geo", "source": "analytics.v_geo"},
            },
        }
    )
    with pytest.raises(DuplicateJoinError):
        validate_registry(registry)


def test_validate_registry_rejects_join_edge_to_missing_entity() -> None:
    registry = build_registry(
        {
            "entities": {
                "leads": {
                    "label": "Leads",
                    "source": "analytics.v_leads",
                    "joins": [{"to": "ghost", "left": "lead_id", "right": "lead_id"}],
                },
            },
        }
    )
    with pytest.raises(UnknownEntityError):
        validate_registry(registry)


def test_validate_registry_rejects_dimension_with_missing_entity() -> None:
    registry = build_registry(
        {"dimensions": {"channel": {"label": "Channel", "entity": "ghost", "column": "channel"}}}
    )
    with pytest.raises(UnknownEntityError):
        validate_registry(registry)


def test_validate_registry_rejects_measure_with_missing_entity() -> None:
    registry = build_registry({"measures": {"lead_count": {"entity": "ghost", "agg": "count"}}})
    with pytest.raises(UnknownEntityError):
        validate_registry(registry)


def test_unknown_lookups_raise() -> None:
    registry = build_registry({})
    with pytest.raises(UnknownEntityError):
        registry.entity("missing")
    with pytest.raises(UnknownMeasureError):
        registry.measure("missing")
    with pytest.raises(UnknownMetricError):
        registry.metric("missing")
    with pytest.raises(UnknownDimensionError):
        registry.dimension("missing")
