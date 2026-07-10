"""Describe a query's answer: which column is what, and how to read it.

The column list mirrors the compiler's select order exactly — period, then group-bys, then the
value and whatever the time modifier adds. It is derived from the resolved intent and the
registry, never from the returned rows, so an empty result still describes its own shape and
an empty chart still draws its axes.

Pure: no database, no FastAPI. Tested against the compiler's output so the two cannot drift.
"""

from app.adapters.data.base import Row
from app.query.validate import ResolvedIntent
from app.schemas.query import Column, ColumnRole, ResultSet
from app.semantic.models import MetricFormat, SemanticRegistry

_DELTA_FORMAT = {
    # A relative change is always a percentage, whatever the metric is measured in.
    "pct": MetricFormat.PERCENT,
}


def _delta_format(kind: str, metric_format: MetricFormat) -> MetricFormat:
    if kind in _DELTA_FORMAT:
        return _DELTA_FORMAT[kind]
    # An absolute change carries the metric's own unit — except for a rate, where the
    # difference between 20% and 24% is four *points*, not four percent.
    if metric_format is MetricFormat.PERCENT:
        return MetricFormat.PERCENT_POINT
    return metric_format


def describe_columns(resolved: ResolvedIntent, registry: SemanticRegistry) -> list[Column]:
    intent = resolved.intent
    metric = registry.metric(intent.metric)
    columns: list[Column] = []

    if intent.grain is not None:
        columns.append(Column(name="period", role=ColumnRole.PERIOD, label="Period"))
    for name in intent.group_by:
        dimension = registry.dimension(name)
        columns.append(Column(name=name, role=ColumnRole.DIMENSION, label=dimension.label))
    columns.append(
        Column(
            name=metric.name,
            role=ColumnRole.METRIC,
            label=metric.label,
            format=metric.format,
        )
    )

    if intent.compare is not None:
        assert intent.compare.kind is not None  # validate_intent resolved it
        columns.append(
            Column(
                name="previous",
                role=ColumnRole.PREVIOUS,
                label=f"Previous {metric.label.lower()}",
                format=metric.format,
            )
        )
        columns.append(
            Column(
                name="delta",
                role=ColumnRole.DELTA,
                label="Change",
                format=_delta_format(intent.compare.kind, metric.format),
            )
        )
    return columns


def build_result(
    resolved: ResolvedIntent, registry: SemanticRegistry, rows: list[Row]
) -> ResultSet:
    return ResultSet(
        columns=describe_columns(resolved, registry),
        rows=rows,
        resolved_intent=resolved.intent,
    )
