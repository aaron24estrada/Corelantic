"""The catalog is a projection of the rules the validator enforces.

If the two ever disagreed, the catalog would advertise questions the compiler refuses — or
hide ones it would answer — and a planner reading it would learn a vocabulary that does not
exist. These tests assert they cannot.
"""

from datetime import date
from pathlib import Path
from typing import Any

import pytest

from app.query.compiler import compile_query
from app.query.errors import (
    AccumulationResetError,
    CompareWithAccumulateError,
    DateGroupByError,
    NotAdditiveError,
    PartialAccumulationError,
)
from app.query.intent import Accumulation, Comparison, QueryIntent
from app.query.time import DateRange, Grain, RelativeRange
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


def _resets(catalog: Any, grain: Grain) -> list[Grain]:
    return next(rule.resets for rule in catalog.accumulation_resets if rule.grain is grain)


def test_the_accumulation_reset_table_is_the_calendar_not_an_ordering(catalog: Any) -> None:
    # A week straddles a month boundary, so a weekly bucket cannot reset monthly.
    assert _resets(catalog, Grain.WEEK) == [Grain.YEAR]
    assert Grain.MONTH in _resets(catalog, Grain.DAY)
    assert _resets(catalog, Grain.YEAR) == []


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

    Every dimension it advertises must group *and* filter; every modifier it says a metric
    supports must compile; every modifier it withholds must be refused.

    This bounds the **vocabulary**, not the shape of a request — see the tests below for the
    three refusals a catalog-obedient planner can still earn.
    """

    checked = 0
    for metric in catalog.metrics:
        for name in metric.groupable_dimensions:
            # Advertised for both slicing paths, because one rule governs both.
            compile_query(QueryIntent(metric=metric.name, group_by=[name]), registry)
            compile_query(QueryIntent(metric=metric.name, filters={name: "any"}), registry)
            checked += 2

        anchored: dict[str, Any] = {"metric": metric.name, "grain": Grain.WEEK}
        if len(metric.date_dimensions) > 1:
            anchored["date_dimension"] = metric.date_dimensions[0]

        if metric.supports.compare:
            compile_query(QueryIntent(**anchored, compare=Comparison()), registry)
        if metric.supports.accumulate:
            # Every grain nests in a year, so YEAR is always a legal reset here.
            compile_query(
                QueryIntent(**anchored, accumulate=Accumulation(reset=Grain.YEAR)), registry
            )
        else:
            with pytest.raises(NotAdditiveError):
                compile_query(
                    QueryIntent(**anchored, accumulate=Accumulation(reset=Grain.YEAR)), registry
                )
        checked += 1

    assert checked > 100


def test_every_reset_the_catalog_advertises_compiles(catalog: Any, registry: Any) -> None:
    # accumulation_resets is the only place the grain/reset rule is published, so it has to be
    # exactly what validate_intent accepts — not a superset, and not a subset.
    metric = next(m for m in catalog.metrics if m.supports.accumulate)
    for rule in catalog.accumulation_resets:
        grain, resets = rule.grain, rule.resets
        for reset in resets:
            compile_query(
                QueryIntent(metric=metric.name, grain=grain, accumulate=Accumulation(reset=reset)),
                registry,
            )
        for rejected in set(Grain) - set(resets):
            with pytest.raises(AccumulationResetError):
                compile_query(
                    QueryIntent(
                        metric=metric.name, grain=grain, accumulate=Accumulation(reset=rejected)
                    ),
                    registry,
                )


# --- what the catalog cannot bound ----------------------------------------------------
#
# Three refusals remain reachable from catalog-only vocabulary. Each is a property of the
# *request*, not of the model, so no per-metric field could express it — and each 422 names
# its own repair. Asserted here so the boundary is recorded rather than assumed.


def test_bucketing_a_date_and_grouping_by_it_is_still_refused(registry: Any) -> None:
    # `lead_date` is legitimately groupable; it just cannot also be the thing being bucketed.
    with pytest.raises(DateGroupByError):
        compile_query(
            QueryIntent(metric="new_leads", grain=Grain.WEEK, group_by=["lead_date"]), registry
        )


def test_compare_and_accumulate_together_are_still_refused(registry: Any) -> None:
    with pytest.raises(CompareWithAccumulateError):
        compile_query(
            QueryIntent(
                metric="new_leads",
                grain=Grain.WEEK,
                compare=Comparison(),
                accumulate=Accumulation(reset=Grain.YEAR),
            ),
            registry,
        )


def test_a_running_total_starting_mid_period_is_still_refused(registry: Any) -> None:
    with pytest.raises(PartialAccumulationError):
        compile_query(
            QueryIntent(
                metric="new_leads",
                grain=Grain.MONTH,
                accumulate=Accumulation(reset=Grain.YEAR),
                date_range=DateRange(start=date(2026, 6, 1)),
            ),
            registry,
        )
