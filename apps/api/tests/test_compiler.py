from typing import Any

import pytest
from sqlalchemy import Select

from app.query.compiler import compile_query
from app.query.errors import CrossEntityError
from app.query.intent import QueryIntent
from app.semantic.errors import UnknownDimensionError, UnknownMetricError
from app.semantic.models import Dimension, Entity, Measure, Metric, SemanticRegistry


def _registry() -> SemanticRegistry:
    return SemanticRegistry(
        entities={
            "leads": Entity(name="leads", label="Leads", source="analytics.v_leads"),
            "cases": Entity(name="cases", label="Cases", source="analytics.v_cases"),
        },
        measures={
            "lead_count": Measure(name="lead_count", entity="leads", expression="count(*)"),
        },
        metrics={
            "new_leads": Metric(
                name="new_leads",
                label="New leads",
                description="Lead count.",
                measure="lead_count",
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


def test_compiles_group_by_and_filter_to_a_select() -> None:
    intent = QueryIntent(metric="new_leads", group_by=["channel"], filters={"region": "Houston"})

    sql, params = _rendered(compile_query(intent, _registry()))

    assert sql == (
        "SELECT channel AS channel, count(*) AS new_leads "
        "FROM analytics.v_leads WHERE metro = :metro_1 GROUP BY channel"
    )
    assert params == {"metro_1": "Houston"}


def test_bare_metric_has_no_where_or_group_by() -> None:
    sql, params = _rendered(compile_query(QueryIntent(metric="new_leads"), _registry()))
    assert sql == "SELECT count(*) AS new_leads FROM analytics.v_leads"
    assert params == {}


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
