import pytest

from app.semantic.errors import UnknownDimensionError, UnknownMetricError
from app.semantic.models import MetricFormat
from app.semantic.registry import build_registry


def test_build_registry_injects_names_and_defaults() -> None:
    registry = build_registry(
        {
            "metrics": {
                "marketing_spend": {
                    "label": "Marketing spend",
                    "description": "Total spend.",
                    "source": "analytics.v_leads",
                    "expression": "sum(spend)",
                    "format": "currency",
                },
                "new_leads": {
                    "label": "New leads",
                    "description": "Lead count.",
                    "source": "analytics.v_leads",
                    "expression": "count(*)",
                },
            },
            "dimensions": {
                "channel": {
                    "label": "Channel",
                    "source": "analytics.v_leads",
                    "column": "channel",
                },
            },
        }
    )

    assert registry.metric("marketing_spend").format is MetricFormat.CURRENCY
    assert registry.metric("new_leads").format is MetricFormat.NUMBER
    assert registry.dimension("channel").column == "channel"


def test_unknown_metric_and_dimension_raise() -> None:
    registry = build_registry({})
    with pytest.raises(UnknownMetricError):
        registry.metric("missing")
    with pytest.raises(UnknownDimensionError):
        registry.dimension("missing")
