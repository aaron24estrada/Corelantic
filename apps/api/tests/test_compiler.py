import pytest

from app.query.compiler import compile_query
from app.query.errors import CrossSourceError
from app.query.intent import QueryIntent
from app.semantic.errors import UnknownDimensionError, UnknownMetricError
from app.semantic.models import Dimension, Metric, SemanticRegistry


def _registry() -> SemanticRegistry:
    return SemanticRegistry(
        metrics={
            "new_leads": Metric(
                name="new_leads",
                label="New leads",
                description="Lead count.",
                source="analytics.v_leads",
                expression="count(*)",
            ),
        },
        dimensions={
            "channel": Dimension(
                name="channel", label="Channel", source="analytics.v_leads", column="channel"
            ),
            "region": Dimension(
                name="region", label="Region", source="analytics.v_leads", column="metro"
            ),
            "attorney": Dimension(
                name="attorney", label="Attorney", source="analytics.v_cases", column="attorney"
            ),
        },
    )


def test_compiles_group_by_and_filter_to_parameterized_sql() -> None:
    intent = QueryIntent(metric="new_leads", group_by=["channel"], filters={"region": "Houston"})

    compiled = compile_query(intent, _registry())

    assert compiled.sql == (
        "SELECT channel AS channel, count(*) AS new_leads "
        "FROM analytics.v_leads WHERE metro = :f0 GROUP BY channel"
    )
    assert compiled.params == {"f0": "Houston"}


def test_bare_metric_has_no_where_or_group_by() -> None:
    compiled = compile_query(QueryIntent(metric="new_leads"), _registry())
    assert compiled.sql == "SELECT count(*) AS new_leads FROM analytics.v_leads"
    assert compiled.params == {}


def test_unknown_metric_raises() -> None:
    with pytest.raises(UnknownMetricError):
        compile_query(QueryIntent(metric="missing"), _registry())


def test_unknown_dimension_raises() -> None:
    with pytest.raises(UnknownDimensionError):
        compile_query(QueryIntent(metric="new_leads", group_by=["missing"]), _registry())


def test_cross_source_dimension_raises() -> None:
    with pytest.raises(CrossSourceError):
        compile_query(QueryIntent(metric="new_leads", group_by=["attorney"]), _registry())
