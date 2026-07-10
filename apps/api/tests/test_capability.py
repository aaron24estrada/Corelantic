"""What the registry says is askable, and whether the compiler agrees."""

from pathlib import Path
from typing import Any

import pytest

from app.query.compiler import compile_query
from app.query.errors import DateDimensionError, IncompatibleDimensionError
from app.query.intent import QueryIntent
from app.semantic.capability import (
    DimensionRejection,
    date_dimensions,
    groupable_dimensions,
    is_joinable_without_fan_out,
    rejection,
)
from app.semantic.registry import load_registry


@pytest.fixture(scope="module")
def registry() -> Any:
    return load_registry(Path("semantic"), allowed_schemas={"gold_tspot"})


def test_groupable_dimensions_excludes_a_fan_out_join(registry: Any) -> None:
    # cases → stages is one-to-many; grouping leads by stage would inflate the count.
    assert "stage_name" not in groupable_dimensions(registry.metric("new_leads"), registry)


def test_groupable_dimensions_excludes_an_unrelated_entity(registry: Any) -> None:
    # zoom_calls declares no join to the lead tables, on purpose.
    assert "channel" not in groupable_dimensions(registry.metric("total_calls"), registry)


@pytest.mark.parametrize(
    ("metric", "excluded"),
    [
        ("voucher_rate", "stage_name"),
        ("inbound_calls", "call_direction"),
        ("outbound_calls", "call_direction"),
    ],
)
def test_a_filtered_measure_cannot_be_sliced_by_the_column_it_filters(
    registry: Any, metric: str, excluded: str
) -> None:
    # The measure's predicate pins that column, so every other group aggregates to nothing.
    assert (
        rejection(registry.metric(metric), registry.dimension(excluded), registry)
        is DimensionRejection.FILTERED_MEASURE
    )
    assert excluded not in groupable_dimensions(registry.metric(metric), registry)


def test_groupable_dimensions_keeps_a_safely_joined_dimension(registry: Any) -> None:
    # stages → cases is many-to-one in reverse, so vouchers by channel neither fans out
    # nor changes the aggregate.
    assert "channel" in groupable_dimensions(registry.metric("vouchers"), registry)


def test_date_dimensions_reach_across_a_fan_out_free_join(registry: Any) -> None:
    # A funnel metric lives on stages but is trended by the lead's intake date on cases.
    assert date_dimensions(registry.metric("vouchers"), registry) == ["lead_date"]


def test_a_call_metric_cannot_anchor_on_a_lead_date(registry: Any) -> None:
    assert date_dimensions(registry.metric("total_calls"), registry) == ["call_date"]


def test_an_entity_is_joinable_to_itself(registry: Any) -> None:
    assert is_joinable_without_fan_out("cases", "cases", registry)


@pytest.mark.parametrize(
    "named",
    [
        "bogus",  # not in the registry at all
        "channel",  # a real dimension, but not a date
        "call_date",  # a real date, but on an entity cases cannot reach
    ],
)
def test_a_named_date_dimension_is_checked_even_when_nothing_uses_it(
    registry: Any, named: str
) -> None:
    # No grain and no date range, so the anchor goes unused — but accepting a name we do not
    # define would teach a planner that the name is valid.
    with pytest.raises(DateDimensionError):
        compile_query(QueryIntent(metric="new_leads", date_dimension=named), registry)


def test_an_unused_date_dimension_does_not_join_its_entity(registry: Any) -> None:
    # `vouchers` can anchor on lead_date, but with no grain or range there is nothing to
    # anchor; joining cases in for a column nothing selects would be waste.
    statement = compile_query(QueryIntent(metric="vouchers", date_dimension="lead_date"), registry)
    assert "cases" not in str(statement.compile()).lower()


def test_every_metric_agrees_with_what_the_catalog_advertises(registry: Any) -> None:
    """The anti-drift guarantee.

    `groupable_dimensions` is the projection the catalog publishes and the predicate
    `validate_intent` enforces. If they ever disagreed, the catalog would advertise
    questions the compiler refuses — or hide ones it would answer. Assert they cannot.

    The rejection must be `IncompatibleDimensionError` specifically: a laxer assertion would
    pass when a metric happened to fail for some unrelated reason, and prove nothing.
    """

    checked = 0
    for metric in registry.metrics.values():
        groupable = set(groupable_dimensions(metric, registry))
        for name in registry.dimensions:
            # Both slicing paths, because a filter is bounded by the same rule as a group-by.
            for intent in (
                QueryIntent(metric=metric.name, group_by=[name]),
                QueryIntent(metric=metric.name, filters={name: "any"}),
            ):
                if name in groupable:
                    compile_query(intent, registry)  # must not raise
                else:
                    with pytest.raises(IncompatibleDimensionError):
                        compile_query(intent, registry)
                checked += 1

    # A silent drop to zero pairs would make this test vacuously green.
    assert checked == 2 * len(registry.metrics) * len(registry.dimensions)
    assert checked > 600
