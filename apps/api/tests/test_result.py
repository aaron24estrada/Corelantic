"""The column schema must describe the rows the compiler actually produces.

`describe_columns` is derived from the intent, never from the returned rows, so an empty
result still describes its own shape. That only holds if it agrees with the compiler's select
order — so these tests compare it against the compiled statement rather than against a list
someone typed out.
"""

from pathlib import Path
from typing import Any

import pytest

from app.query.compiler import compile_resolved
from app.query.intent import Accumulation, Comparison, QueryIntent
from app.query.time import Grain
from app.query.validate import validate_intent
from app.schemas.query import ColumnRole
from app.semantic.models import MetricFormat
from app.semantic.registry import load_registry
from app.services.result import describe_columns


@pytest.fixture(scope="module")
def registry() -> Any:
    return load_registry(Path("semantic"), allowed_schemas={"gold_tspot"})


def _columns_and_selected(intent: QueryIntent, registry: Any) -> tuple[list[Any], list[str]]:
    resolved = validate_intent(intent, registry)
    columns = describe_columns(resolved, registry)
    selected = [c.name for c in compile_resolved(resolved, registry).selected_columns]
    return columns, selected


@pytest.mark.parametrize(
    "intent",
    [
        QueryIntent(metric="new_leads"),
        QueryIntent(metric="new_leads", group_by=["channel"]),
        QueryIntent(metric="new_leads", grain=Grain.WEEK),
        QueryIntent(metric="new_leads", grain=Grain.WEEK, group_by=["channel", "state"]),
        QueryIntent(metric="new_leads", grain=Grain.WEEK, compare=Comparison()),
        QueryIntent(metric="voucher_rate", grain=Grain.MONTH, compare=Comparison()),
        QueryIntent(metric="revenue", grain=Grain.MONTH, accumulate=Accumulation(reset=Grain.YEAR)),
    ],
)
def test_the_columns_match_the_compiled_select_order(intent: QueryIntent, registry: Any) -> None:
    columns, selected = _columns_and_selected(intent, registry)
    assert [c.name for c in columns] == selected


def test_a_comparison_describes_its_value_previous_and_delta(registry: Any) -> None:
    intent = QueryIntent(metric="new_leads", grain=Grain.WEEK, compare=Comparison())
    columns, _ = _columns_and_selected(intent, registry)

    assert [c.role for c in columns] == [
        ColumnRole.PERIOD,
        ColumnRole.METRIC,
        ColumnRole.PREVIOUS,
        ColumnRole.DELTA,
    ]
    # A relative change is a percentage whatever the metric counts.
    assert columns[-1].format is MetricFormat.PERCENT


def test_the_delta_of_a_rate_is_in_points_not_percent(registry: Any) -> None:
    # 20% -> 24% is +4 points. Labelling that "+20%" is true of the ratio and misleading
    # about the business, so the column says which one it is.
    intent = QueryIntent(metric="voucher_rate", grain=Grain.WEEK, compare=Comparison())
    columns, _ = _columns_and_selected(intent, registry)

    assert columns[1].format is MetricFormat.PERCENT
    assert columns[-1].format is MetricFormat.PERCENT_POINT


def test_an_explicit_relative_change_of_a_rate_stays_a_percent(registry: Any) -> None:
    intent = QueryIntent(metric="voucher_rate", grain=Grain.WEEK, compare=Comparison(kind="pct"))
    columns, _ = _columns_and_selected(intent, registry)
    assert columns[-1].format is MetricFormat.PERCENT


def test_a_dimension_column_carries_its_registry_label(registry: Any) -> None:
    intent = QueryIntent(metric="new_leads", group_by=["channel"])
    columns, _ = _columns_and_selected(intent, registry)

    assert columns[0].role is ColumnRole.DIMENSION
    assert columns[0].label == registry.dimension("channel").label
    assert columns[0].format is None
