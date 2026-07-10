"""The catalog is a projection of the rules the validator enforces.

If the two ever disagreed, the catalog would advertise questions the compiler refuses — or
hide ones it would answer — and a planner reading it would learn a vocabulary that does not
exist. These tests assert they cannot.
"""

from pathlib import Path
from typing import Any

import pytest

from app.query.compiler import compile_query
from app.query.errors import IntentError
from app.query.intent import Accumulation, Comparison, QueryIntent
from app.query.time import Grain, RelativeRange
from app.semantic.registry import load_registry
from app.services.catalog import build_catalog


@pytest.fixture(scope="module")
def registry() -> Any:
    return load_registry(Path("semantic"), allowed_schemas={"gold_tspot"})


@pytest.fixture(scope="module")
def catalog(registry: Any) -> Any:
    return build_catalog(registry)


def test_every_metric_is_published(catalog: Any, registry: Any) -> None:
    assert {metric.name for metric in catalog.metrics} == set(registry.metrics)


def test_every_dimension_is_published(catalog: Any, registry: Any) -> None:
    assert {dimension.name for dimension in catalog.dimensions} == set(registry.dimensions)


def test_a_filtered_measures_own_column_is_not_advertised(catalog: Any) -> None:
    # voucher_rate filters on the stage column, so "voucher rate by stage" is meaningless.
    voucher_rate = next(m for m in catalog.metrics if m.name == "voucher_rate")
    assert "stage_name" not in voucher_rate.groupable_dimensions


def test_an_unrelated_entitys_dimensions_are_not_advertised(catalog: Any) -> None:
    # zoom_calls declares no join to the lead tables, on purpose.
    total_calls = next(m for m in catalog.metrics if m.name == "total_calls")
    assert "channel" not in total_calls.groupable_dimensions
    assert total_calls.date_dimensions == ["call_date"]


def test_a_rate_is_not_advertised_as_accumulable(catalog: Any) -> None:
    voucher_rate = next(m for m in catalog.metrics if m.name == "voucher_rate")
    assert voucher_rate.supports.compare is True
    assert voucher_rate.supports.accumulate is False


def test_revenue_is_advertised_as_accumulable_because_it_declares_additive(catalog: Any) -> None:
    revenue = next(m for m in catalog.metrics if m.name == "revenue")
    assert revenue.supports.accumulate is True


def test_the_accumulation_reset_table_is_the_calendar_not_an_ordering(catalog: Any) -> None:
    # A week straddles a month boundary, so a weekly bucket cannot reset monthly.
    assert catalog.accumulation_resets[Grain.WEEK] == [Grain.YEAR]
    assert Grain.MONTH in catalog.accumulation_resets[Grain.DAY]
    assert catalog.accumulation_resets[Grain.YEAR] == []


def test_the_closed_enums_are_published(catalog: Any) -> None:
    # A planner can only pick a window we implement.
    assert set(catalog.grains) == set(Grain)
    assert RelativeRange.LAST_90_DAYS in catalog.relative_ranges


def test_a_closed_dimension_publishes_its_members(catalog: Any) -> None:
    channel = next(d for d in catalog.dimensions if d.name == "channel")
    assert channel.members  # the agent must filter on exact values, not invent them


def test_a_date_dimension_publishes_its_role(catalog: Any) -> None:
    lead_date = next(d for d in catalog.dimensions if d.name == "lead_date")
    assert lead_date.date_role == "lead"


def test_everything_the_catalog_advertises_actually_compiles(catalog: Any, registry: Any) -> None:
    """The anti-drift guarantee, from the catalog's side rather than the validator's.

    Every groupable dimension must compile; every supported modifier must compile; and a
    modifier the catalog withholds must be refused. A planner that obeys the catalog can never
    be told 422.
    """

    checked = 0
    for metric in catalog.metrics:
        for name in metric.groupable_dimensions:
            compile_query(QueryIntent(metric=metric.name, group_by=[name]), registry)
            checked += 1

        anchored = {"metric": metric.name, "grain": Grain.WEEK}
        if len(metric.date_dimensions) > 1:
            anchored["date_dimension"] = metric.date_dimensions[0]

        if metric.supports.compare:
            compile_query(QueryIntent(**anchored, compare=Comparison()), registry)
        if metric.supports.accumulate:
            compile_query(
                QueryIntent(**anchored, accumulate=Accumulation(reset=Grain.YEAR)), registry
            )
        else:
            with pytest.raises(IntentError):
                compile_query(
                    QueryIntent(**anchored, accumulate=Accumulation(reset=Grain.YEAR)), registry
                )
        checked += 1

    assert checked > 100
