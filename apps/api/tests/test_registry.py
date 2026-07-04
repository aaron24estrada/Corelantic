import pytest

from app.semantic.errors import (
    UnknownDimensionError,
    UnknownEntityError,
    UnknownMeasureError,
    UnknownMetricError,
)
from app.semantic.models import MetricFormat
from app.semantic.registry import build_registry, validate_registry


def _raw() -> dict[str, object]:
    return {
        "entities": {
            "leads": {"label": "Leads", "source": "analytics.v_leads"},
        },
        "measures": {
            "spend_total": {"label": "Spend total", "entity": "leads", "expression": "sum(spend)"},
            "lead_count": {"label": "Lead count", "entity": "leads", "expression": "count(*)"},
        },
        "metrics": {
            "marketing_spend": {
                "label": "Marketing spend",
                "description": "Total spend.",
                "measure": "spend_total",
                "format": "currency",
            },
            "new_leads": {
                "label": "New leads",
                "description": "Lead count.",
                "measure": "lead_count",
            },
        },
        "dimensions": {
            "channel": {"label": "Channel", "entity": "leads", "column": "channel"},
        },
    }


def test_build_registry_injects_names_and_defaults() -> None:
    registry = build_registry(_raw())

    assert registry.entity("leads").source == "analytics.v_leads"
    assert registry.measure("lead_count").expression == "count(*)"
    assert registry.metric("marketing_spend").measure == "spend_total"
    assert registry.metric("marketing_spend").format is MetricFormat.CURRENCY
    assert registry.metric("new_leads").format is MetricFormat.NUMBER
    assert registry.dimension("channel").column == "channel"


def test_validate_registry_accepts_resolvable_references() -> None:
    # Returns the same registry when every reference resolves.
    registry = build_registry(_raw())
    assert validate_registry(registry) is registry


def test_validate_registry_rejects_metric_with_missing_measure() -> None:
    registry = build_registry(
        {
            "entities": {"leads": {"label": "Leads", "source": "analytics.v_leads"}},
            "metrics": {
                "orphan": {"label": "Orphan", "description": "x", "measure": "does_not_exist"},
            },
        }
    )
    with pytest.raises(UnknownMeasureError):
        validate_registry(registry)


def test_validate_registry_rejects_dimension_with_missing_entity() -> None:
    registry = build_registry(
        {"dimensions": {"channel": {"label": "Channel", "entity": "ghost", "column": "channel"}}}
    )
    with pytest.raises(UnknownEntityError):
        validate_registry(registry)


def test_validate_registry_rejects_measure_with_missing_entity() -> None:
    registry = build_registry(
        {
            "measures": {
                "lead_count": {"label": "Lead count", "entity": "ghost", "expression": "count(*)"}
            }
        }
    )
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
