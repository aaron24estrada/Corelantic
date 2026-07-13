"""A chart spec is a pure function of (chart request, resolved intent, result set).

So these tests need no browser and no database: they hand `build_chart_spec` rows of the shape
the compiler produces and assert on the drawing that comes back. The load-bearing property is
that a series' colour belongs to the *entity* it names and not to its rank, because the moment
D5 cross-filters a trend down to two channels, the two that remain must keep their colours.
"""

from datetime import date
from pathlib import Path
from typing import Any

import pytest

from app.query.intent import Comparison, QueryIntent
from app.query.rows import Row
from app.query.time import Grain
from app.query.validate import validate_intent
from app.schemas.chart import PALETTE_SLOTS, ChartRequest, ChartType, SeriesRole
from app.semantic.capability import groupable_dimensions
from app.semantic.registry import load_registry
from app.services.chart import build_chart_spec
from app.services.chart_errors import PivotNotSupportedError, UnsupportedChartTypeError
from app.services.result import build_result

LINE = ChartRequest(type=ChartType.LINE)
BAR = ChartRequest(type=ChartType.BAR)


@pytest.fixture(scope="module")
def registry() -> Any:
    return load_registry(Path("semantic"), allowed_schemas={"gold_tspot"})


def spec(chart: ChartRequest, intent: QueryIntent, rows: list[Row], registry: Any) -> Any:
    resolved = validate_intent(intent, registry, today=date(2026, 7, 10))
    return build_chart_spec(chart, resolved, build_result(resolved, registry, rows), registry)


# --- shape -------------------------------------------------------------------------------


def test_a_trend_is_one_series_in_the_first_palette_slot(registry: Any) -> None:
    intent = QueryIntent(metric="new_leads", grain=Grain.WEEK)
    rows: list[Row] = [
        {"period": date(2026, 6, 1), "new_leads": 400},
        {"period": date(2026, 6, 8), "new_leads": 480},
    ]
    drawn = spec(LINE, intent, rows, registry)

    assert drawn.categories == ["2026-06-01", "2026-06-08"]
    assert [s.name for s in drawn.series] == ["New leads"]
    assert drawn.series[0].data == [400.0, 480.0]
    assert drawn.series[0].palette_index == 0
    assert drawn.y.format is registry.metric("new_leads").format


def test_a_comparison_series_repeats_its_primarys_colour(registry: Any) -> None:
    # `previous` is the same entity in an earlier window, so it is told apart by stroke, never
    # by hue — spending a second categorical slot on it would imply a second thing.
    intent = QueryIntent(metric="new_leads", grain=Grain.WEEK, compare=Comparison())
    rows: list[Row] = [
        {"period": date(2026, 6, 1), "new_leads": 400, "previous": None, "delta": None},
        {"period": date(2026, 6, 8), "new_leads": 480, "previous": 400, "delta": 0.2},
    ]
    drawn = spec(LINE, intent, rows, registry)

    assert [s.role for s in drawn.series] == [SeriesRole.PRIMARY, SeriesRole.COMPARISON]
    assert {s.palette_index for s in drawn.series} == {0}
    # The first bucket has nothing before it. That is a gap in the line, not a drop to zero.
    assert drawn.series[1].data == [None, 400.0]


def test_delta_is_never_plotted(registry: Any) -> None:
    # A count of 400 and a change of +0.2 share no scale. A second y-axis is the most common
    # way to lie with a chart, so the delta stays a number on a tile.
    intent = QueryIntent(metric="new_leads", grain=Grain.WEEK, compare=Comparison())
    rows: list[Row] = [
        {"period": date(2026, 6, 8), "new_leads": 480, "previous": 400, "delta": 0.2}
    ]
    drawn = spec(LINE, intent, rows, registry)

    assert len(drawn.series) == 2
    assert all(0.2 not in (s.data or []) for s in drawn.series)


def test_an_empty_result_still_describes_its_axes(registry: Any) -> None:
    drawn = spec(LINE, QueryIntent(metric="new_leads", grain=Grain.WEEK), [], registry)
    assert drawn.categories == []
    assert drawn.series[0].data == []
    assert drawn.y.label == "New leads"


def test_a_missing_bucket_is_a_gap_and_never_a_zero(registry: Any) -> None:
    intent = QueryIntent(metric="voucher_rate", grain=Grain.WEEK)
    rows: list[Row] = [
        {"period": date(2026, 6, 1), "voucher_rate": 0.24},
        {"period": date(2026, 6, 8), "voucher_rate": None},
    ]
    drawn = spec(LINE, intent, rows, registry)
    assert drawn.series[0].data == [0.24, None]


# --- nominal bars ------------------------------------------------------------------------


def test_a_null_dimension_value_is_the_blank_bucket_not_an_empty_label(registry: Any) -> None:
    # ~38% of KRW's leads have no geo row, and their dashboard shows them as "(Blank)". Rendering
    # that as "" draws the biggest bar on the chart with no label. See docs/data-model.md.
    intent = QueryIntent(metric="new_leads", group_by=["channel"])
    rows: list[Row] = [
        {"channel": None, "new_leads": 33000},
        {"channel": "CTV", "new_leads": 20131},
    ]
    drawn = spec(BAR, intent, rows, registry)

    assert "(Blank)" in drawn.categories
    assert "" not in drawn.categories


def test_a_null_and_a_literal_blank_keep_their_own_values(registry: Any) -> None:
    # Both a NULL and a literal "(Blank)" string render to the same label, but they are two
    # distinct buckets. A label-keyed map would collapse them and silently drop one row's value;
    # position alignment keeps each row bound to its own number. Neither 5 nor 7 may vanish.
    intent = QueryIntent(metric="new_leads", group_by=["channel"])
    rows: list[Row] = [
        {"channel": None, "new_leads": 5},
        {"channel": "(Blank)", "new_leads": 7},
    ]
    drawn = spec(BAR, intent, rows, registry)

    assert drawn.categories == ["(Blank)", "(Blank)"]
    assert sorted(v for v in drawn.series[0].data if v is not None) == [5.0, 7.0]


def test_nominal_bars_are_one_series_and_take_the_declared_member_order(registry: Any) -> None:
    # Colouring bars by their value would spend the identity channel re-encoding what bar
    # length already shows, and would invent an order the data does not have.
    intent = QueryIntent(metric="new_leads", group_by=["channel"])
    rows: list[Row] = [
        {"channel": "Facebook", "new_leads": 10},
        {"channel": "CTV", "new_leads": 90},
    ]
    drawn = spec(BAR, intent, rows, registry)

    assert len(drawn.series) == 1
    assert drawn.series[0].palette_index == 0
    assert drawn.categories == ["CTV", "Facebook"]  # declared order, not descending by value
    assert drawn.series[0].data == [90.0, 10.0]


# --- colour follows the entity, not its rank ---------------------------------------------


def test_a_pivot_takes_its_colours_from_the_declared_member_order(registry: Any) -> None:
    intent = QueryIntent(metric="total_calls", grain=Grain.WEEK, group_by=["call_direction"])
    rows: list[Row] = [
        {"period": date(2026, 6, 1), "call_direction": "outbound", "total_calls": 7},
        {"period": date(2026, 6, 1), "call_direction": "inbound", "total_calls": 3},
    ]
    drawn = spec(LINE, intent, rows, registry)

    slots = {s.name: s.palette_index for s in drawn.series}
    assert slots == {"inbound": 0, "outbound": 1}  # registry order, though `outbound` led the rows


def test_filtering_a_pivot_does_not_repaint_the_survivors(registry: Any) -> None:
    """The property the whole colour rule exists for.

    Ranking by value, or indexing into the members *present in these rows*, both pass the test
    above and both fail this one: drop `inbound` and `outbound` slides into slot 0, silently
    changing colour under a reader who is watching the same chart.
    """
    both: list[Row] = [
        {"period": date(2026, 6, 1), "call_direction": "inbound", "total_calls": 3},
        {"period": date(2026, 6, 1), "call_direction": "outbound", "total_calls": 7},
    ]
    only_outbound: list[Row] = [
        {"period": date(2026, 6, 1), "call_direction": "outbound", "total_calls": 7},
    ]
    intent = QueryIntent(metric="total_calls", grain=Grain.WEEK, group_by=["call_direction"])

    unfiltered = spec(LINE, intent, both, registry)
    filtered = spec(LINE, intent, only_outbound, registry)

    outbound = next(s for s in unfiltered.series if s.name == "outbound")
    assert filtered.series[0].name == "outbound"
    assert filtered.series[0].palette_index == outbound.palette_index == 1


def test_no_dimension_in_the_registry_can_index_past_the_last_colour(registry: Any) -> None:
    """Swept over the real registry, so adding a ninth member to a dimension fails here first.

    Either a dimension fits the palette and pivots, or it is refused. There is no third case in
    which a series is drawn with `palette_index` 8 and the renderer reaches past its last hue.
    """
    checked = 0
    for name, dimension in registry.dimensions.items():
        metric = next(
            (m for m in registry.metrics.values() if name in groupable_dimensions(m, registry)),
            None,
        )
        if metric is None or not dimension.members:
            continue
        checked += 1
        member = dimension.members[0]
        intent = QueryIntent(metric=metric.name, grain=Grain.WEEK, group_by=[name])
        rows: list[Row] = [{"period": date(2026, 6, 1), name: member, metric.name: 1}]

        if len(dimension.members) > PALETTE_SLOTS:
            with pytest.raises(PivotNotSupportedError):
                spec(LINE, intent, rows, registry)
        else:
            drawn = spec(LINE, intent, rows, registry)
            assert all(s.palette_index < PALETTE_SLOTS for s in drawn.series)
    assert checked, "the sweep found no dimension with declared members — it is proving nothing"


# --- refusals ----------------------------------------------------------------------------


def test_a_line_without_a_period_is_refused_and_offers_bar(registry: Any) -> None:
    intent = QueryIntent(metric="new_leads", group_by=["channel"])
    rows: list[Row] = [{"channel": "CTV", "new_leads": 90}]
    with pytest.raises(UnsupportedChartTypeError) as raised:
        spec(LINE, intent, rows, registry)
    assert raised.value.allowed == ["bar"]
    assert raised.value.field == "chart"


def test_bars_refuse_a_period_and_a_group_at_once(registry: Any) -> None:
    intent = QueryIntent(metric="total_calls", grain=Grain.WEEK, group_by=["call_direction"])
    rows: list[Row] = [{"period": date(2026, 6, 1), "call_direction": "inbound", "total_calls": 3}]
    with pytest.raises(UnsupportedChartTypeError) as raised:
        spec(BAR, intent, rows, registry)
    assert raised.value.allowed == ["line"]


def test_two_grouped_dimensions_have_no_single_categorical_axis(registry: Any) -> None:
    intent = QueryIntent(metric="new_leads", grain=Grain.WEEK, group_by=["channel", "state"])
    with pytest.raises(UnsupportedChartTypeError):
        spec(LINE, intent, [], registry)


def test_an_ungrouped_number_is_not_a_chart(registry: Any) -> None:
    with pytest.raises(UnsupportedChartTypeError):
        spec(BAR, QueryIntent(metric="new_leads"), [{"new_leads": 86973}], registry)


def test_a_dimension_with_more_members_than_colours_cannot_be_pivoted(registry: Any) -> None:
    # `channel` declares nine members and there are eight colours. Two series would share a hue.
    intent = QueryIntent(metric="new_leads", grain=Grain.WEEK, group_by=["channel"])
    rows: list[Row] = [{"period": date(2026, 6, 1), "channel": "CTV", "new_leads": 90}]
    with pytest.raises(PivotNotSupportedError) as raised:
        spec(LINE, intent, rows, registry)

    assert raised.value.field == "group_by"
    assert "channel" not in raised.value.allowed
    assert all(
        0 < len(registry.dimension(d).members) <= PALETTE_SLOTS for d in raised.value.allowed
    )


def test_a_null_member_in_a_pivot_is_refused_not_merged(registry: Any) -> None:
    # A NULL dimension value has no declared member, so it has no colour a filter cannot move.
    # Keying the pivot by the raw value (not the "(Blank)" label) means a NULL is refused even
    # if a dimension ever declared "(Blank)" as a real member — the two never collapse into one
    # series and lose a row, which a label-keyed pivot would do silently.
    intent = QueryIntent(metric="total_calls", grain=Grain.WEEK, group_by=["call_direction"])
    rows: list[Row] = [{"period": date(2026, 6, 1), "call_direction": None, "total_calls": 5}]
    with pytest.raises(PivotNotSupportedError):
        spec(LINE, intent, rows, registry)


def test_an_open_member_set_cannot_be_pivoted(registry: Any) -> None:
    # `state` declares no members, so no state has a colour that survives a filter.
    intent = QueryIntent(metric="new_leads", grain=Grain.WEEK, group_by=["state"])
    rows: list[Row] = [{"period": date(2026, 6, 1), "state": "TX", "new_leads": 90}]
    with pytest.raises(PivotNotSupportedError):
        spec(LINE, intent, rows, registry)


def test_a_value_the_registry_never_declared_is_surfaced_not_painted_grey(registry: Any) -> None:
    intent = QueryIntent(metric="total_calls", grain=Grain.WEEK, group_by=["call_direction"])
    rows: list[Row] = [
        {"period": date(2026, 6, 1), "call_direction": "inbound", "total_calls": 3},
        {"period": date(2026, 6, 1), "call_direction": "sideways", "total_calls": 1},
    ]
    with pytest.raises(PivotNotSupportedError, match="sideways"):
        spec(LINE, intent, rows, registry)


# --- the spec carries the rows' numbers, and only those ------------------------------------


def test_series_data_is_exactly_the_rows_pivoted(registry: Any) -> None:
    """The spec duplicates the numbers; nothing may be lost or invented in the copy.

    Clients render `series` and never reconcile it against `rows`, so this is the seam where
    the two are pinned together.
    """
    intent = QueryIntent(metric="total_calls", grain=Grain.WEEK, group_by=["call_result"])
    members = registry.dimension("call_result").members
    rows: list[Row] = [
        {"period": date(2026, 6, day), "call_result": member, "total_calls": index * 10 + day}
        for day in (1, 8)
        for index, member in enumerate(members)
    ]
    drawn = spec(LINE, intent, rows, registry)

    assert len(drawn.series) == len(members)
    assert [s.palette_index for s in drawn.series] == list(range(len(members)))
    for series in drawn.series:
        for category, value in zip(drawn.categories, series.data, strict=True):
            row = next(
                r
                for r in rows
                if r["call_result"] == series.name and r["period"].isoformat() == category  # type: ignore[union-attr]
            )
            assert value == float(row["total_calls"])  # type: ignore[arg-type]
