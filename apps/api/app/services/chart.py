"""Turn a result into a drawing: the pure function ``(chart, resolved intent, result) → ChartSpec``.

Pure — no database, no FastAPI, no chart library. Everything it needs is already decided:
``ResultSet.columns`` says which key is the period, which are dimensions, and which is the
value; the registry says what a dimension's members are. So this is testable without a browser
and without a database, and both surfaces reach one renderer through it — the dashboard by
naming a chart type, and (once E3 lands) the agent by having planned one.

Sibling of ``services/result.py``: that one describes the rows, this one draws them.

Two refusals live here, both the caller's mistake and both 422s, because both are properties of
the *question* rather than of the data — the same reasoning as ``query/errors.py``.
"""

from datetime import date, datetime
from decimal import Decimal

from app.query.rows import CellValue, Row
from app.query.validate import ResolvedIntent
from app.schemas.chart import (
    PALETTE_SLOTS,
    ChartAxis,
    ChartRequest,
    ChartSeries,
    ChartSpec,
    ChartType,
    SeriesRole,
)
from app.schemas.query import Column, ColumnRole, ResultSet
from app.semantic.capability import groupable_dimensions
from app.semantic.models import SemanticRegistry
from app.services.chart_errors import PivotNotSupportedError, UnsupportedChartTypeError

_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")

# A dimension value can be NULL and still be a real bucket: ~38% of KRW's leads have no `geo`
# row, and their dashboard shows them as "(Blank)". Rendering that as an empty string draws an
# unlabelled bar next to labelled ones, which is the biggest bar on the chart saying nothing.
# We take their name for it so the two dashboards can be compared. See docs/data-model.md.
_BLANK = "(Blank)"


def _numeric(value: CellValue) -> float | None:
    """A cell as a plottable number. A gap stays a gap; it never becomes a zero."""
    if value is None:
        return None
    if isinstance(value, bool):  # bool is an int; a plotted True is always a bug
        raise TypeError("a boolean cell cannot be plotted")
    if isinstance(value, Decimal | int | float):
        return float(value)
    raise TypeError(f"cannot plot a {type(value).__name__} cell")


def _category(value: CellValue) -> str:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return _BLANK if value is None else str(value)


def _day(value: date) -> str:
    return f"{value.day} {_MONTHS[value.month - 1]} {value.year}"


def _window(resolved: ResolvedIntent) -> str | None:
    """The window the chart truly covers, for the caption — not the window that was asked for."""
    window = resolved.date_range
    if window is None:
        return None
    if window.start is None:
        return f"to {_day(window.end)}" if window.end is not None else None
    if window.end is None:
        return f"from {_day(window.start)}"
    # An en dash, not a hyphen: this is a caption a reader sees, and RUF001 guards identifiers.
    return f"{_day(window.start)} – {_day(window.end)}"  # noqa: RUF001


def _pivot_slots(dimension: str, registry: SemanticRegistry, metric: str) -> dict[str, int]:
    """Member → colour slot, fixed by the model and not by this result.

    A pivot paints one series per member, so each member needs a slot that no filter can move.
    Ranking by value would repaint the survivors the moment D5 cross-filters one away, and
    sorting the members *present in these rows* does the same thing more quietly. The only
    stable key is the member's position in the registry's declared list — which is why a
    dimension must declare one, and why it cannot declare more members than there are slots.
    """
    members = registry.dimension(dimension).members
    if not members:
        raise PivotNotSupportedError(
            dimension=dimension,
            reason=(
                "it declares no closed member list, so no member has a colour a filter cannot move"
            ),
            allowed=_pivotable(metric, registry),
        )
    if len(members) > PALETTE_SLOTS:
        raise PivotNotSupportedError(
            dimension=dimension,
            reason=(
                f"it declares {len(members)} members and there are {PALETTE_SLOTS} colours, "
                f"so two series would have to share one"
            ),
            allowed=_pivotable(metric, registry),
        )
    return {member: index for index, member in enumerate(members)}


def _pivotable(metric: str, registry: SemanticRegistry) -> list[str]:
    """The dimensions this metric can be split into series by — the repair the 422 offers."""
    return [
        name
        for name in groupable_dimensions(registry.metric(metric), registry)
        if 0 < len(registry.dimension(name).members) <= PALETTE_SLOTS
    ]


def _column(columns: list[Column], role: ColumnRole) -> Column | None:
    return next((c for c in columns if c.role is role), None)


def build_chart_spec(
    chart: ChartRequest,
    resolved: ResolvedIntent,
    result: ResultSet,
    registry: SemanticRegistry,
) -> ChartSpec:
    columns = result.columns
    period = _column(columns, ColumnRole.PERIOD)
    dimensions = [c for c in columns if c.role is ColumnRole.DIMENSION]
    value = _column(columns, ColumnRole.METRIC)
    previous = _column(columns, ColumnRole.PREVIOUS)
    assert value is not None  # describe_columns always emits exactly one metric column

    # `delta` is never plotted. It shares no scale with the value it describes — a lead count of
    # 400 and a change of +0.04 on one axis is unreadable — and a second y-axis is the single
    # most common way to lie with a chart. A KPI tile reads `delta` from `rows` and prints it.

    if len(dimensions) > 1:
        raise UnsupportedChartTypeError(
            chart.type,
            reason=(
                f"it groups by {len(dimensions)} dimensions, and a chart has one categorical axis"
            ),
            allowed=[],
        )

    if chart.type is ChartType.LINE and period is None:
        raise UnsupportedChartTypeError(
            ChartType.LINE,
            reason="a line needs a period to run along; this result has no grain",
            allowed=[ChartType.BAR],
        )
    if chart.type is ChartType.BAR and period is not None and dimensions:
        raise UnsupportedChartTypeError(
            ChartType.BAR,
            reason="bars take one categorical axis, and this result has both a period and a group",
            allowed=[ChartType.LINE],
        )

    if period is not None and dimensions:
        return _pivoted(chart, resolved, result, registry, period, dimensions[0], value, previous)

    axis = period if period is not None else (dimensions[0] if dimensions else None)
    if axis is None:
        raise UnsupportedChartTypeError(
            chart.type,
            reason="a chart needs an axis, and this result is a single ungrouped number",
            allowed=[],
        )
    return _single(chart, resolved, result, registry, axis, value, previous)


def _plotted(value: Column, previous: Column | None) -> list[tuple[Column, SeriesRole]]:
    """The columns that become series. `delta` is deliberately not among them."""
    plotted = [(value, SeriesRole.PRIMARY)]
    if previous is not None:
        plotted.append((previous, SeriesRole.COMPARISON))
    return plotted


def _series(
    name: str, data: list[float | None], column: Column, role: SeriesRole, slot: int
) -> ChartSeries:
    assert column.format is not None  # a metric column always carries its format
    return ChartSeries(name=name, data=data, format=column.format, role=role, palette_index=slot)


def _spec(
    chart: ChartRequest,
    resolved: ResolvedIntent,
    value: Column,
    categories: list[str],
    x_label: str,
    series: list[ChartSeries],
) -> ChartSpec:
    return ChartSpec(
        type=chart.type,
        title=value.label,
        subtitle=_window(resolved),
        categories=categories,
        x=ChartAxis(label=x_label),
        y=ChartAxis(label=value.label, format=value.format),
        series=series,
    )


def _single(
    chart: ChartRequest,
    resolved: ResolvedIntent,
    result: ResultSet,
    registry: SemanticRegistry,
    axis: Column,
    value: Column,
    previous: Column | None,
) -> ChartSpec:
    """One series: a plain trend, or a nominal bar chart.

    Every bar takes slot 0. Colouring nominal bars by their value spends the identity channel
    re-encoding what bar length already shows, and invents an order the data does not have.
    """
    # One category per row, aligned by position — never keyed by the display label. Two distinct
    # cell values can share a label (a NULL and a literal "(Blank)", a `date` and a same-day
    # `datetime`), and a label-keyed map would collapse them and silently drop one row's value.
    # The compiler already emits one row per group, so row order is the honest order.
    rows = result.rows
    if axis.role is ColumnRole.DIMENSION:
        rows = _ordered(rows, axis.name, registry)

    categories = [_category(row.get(axis.name)) for row in rows]
    series = [
        _series(
            column.label,
            [_numeric(row.get(column.name)) for row in rows],
            column,
            role,
            slot=0,
        )
        for column, role in _plotted(value, previous)
    ]
    return _spec(chart, resolved, value, categories, axis.label, series)


def _ordered(rows: list[Row], dimension: str, registry: SemanticRegistry) -> list[Row]:
    """Rows in the model's declared member order, so two charts of one dimension agree.

    Sorting the *rows* rather than the labels keeps each row bound to its own value across the
    reorder — the bug the position-aligned build above exists to avoid. An undeclared member (or
    the NULL "(Blank)" bucket) sorts last, then by label.
    """
    members = registry.dimension(dimension).members
    if not members:
        return rows
    rank = {member: index for index, member in enumerate(members)}

    def key(row: Row) -> tuple[int, str]:
        label = _category(row.get(dimension))
        return rank.get(label, len(rank)), label

    return sorted(rows, key=key)


def _pivoted(
    chart: ChartRequest,
    resolved: ResolvedIntent,
    result: ResultSet,
    registry: SemanticRegistry,
    period: Column,
    dimension: Column,
    value: Column,
    previous: Column | None,
) -> ChartSpec:
    """One series per dimension member, each holding its colour across any filter."""
    slots = _pivot_slots(dimension.name, registry, resolved.intent.metric)

    # A member's identity is the raw cell value, never its display label. Keying by the label
    # would let a NULL (rendered "(Blank)") and a literal "(Blank)" string collapse into one
    # series and lose a row — the same trap `_single` avoids. A raw NULL is never a declared
    # member (members are strings), so it always falls into `unknown` and the pivot is refused:
    # a bucket the model does not name has no colour that survives a filter.
    unknown = {r.get(dimension.name) for r in result.rows if r.get(dimension.name) not in slots}
    if unknown:
        raise PivotNotSupportedError(
            dimension=dimension.name,
            reason=(
                f"the data holds {sorted(_category(v) for v in unknown)!r}, which its declared "
                f"members do not list, so those rows have no colour"
            ),
            allowed=_pivotable(resolved.intent.metric, registry),
        )

    # The period axis is a grain bucket — always a date, never NULL and never a string — so
    # distinct buckets never share a label. The compiler groups by (period, member), so within
    # one member each bucket appears once; this map is safe where `_single`'s was not.
    categories = sorted({_category(row.get(period.name)) for row in result.rows})
    order = {category: index for index, category in enumerate(categories)}

    present = [m for m in slots if any(r.get(dimension.name) == m for r in result.rows)]
    series = []
    for member in present:
        rows = [r for r in result.rows if r.get(dimension.name) == member]
        for column, role in _plotted(value, previous):
            data: list[float | None] = [None] * len(categories)
            for row in rows:
                data[order[_category(row.get(period.name))]] = _numeric(row.get(column.name))
            name = member if role is SeriesRole.PRIMARY else f"{member} (previous)"
            series.append(_series(name, data, column, role, slot=slots[member]))
    return _spec(chart, resolved, value, categories, period.label, series)
