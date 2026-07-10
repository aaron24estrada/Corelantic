"""Validate a query intent against the registry, and resolve what it left implicit.

This is the gate the compiler stands behind. After ``validate_intent`` every name in the
intent is defined, every dimension is one the metric can actually be sliced by, and the date
dimension a time question needs has been chosen. The compiler keeps its own registry lookups
— a failure *there* means the registry disagrees with itself, which is our bug and a 500,
not the caller's mistake and a 422.

Resolution happens once, here. The compiler never re-derives the date dimension, so the two
cannot disagree about which date a trend is anchored on.
"""

from dataclasses import dataclass

from app.query.errors import (
    DateDimensionError,
    DimensionNotDefinedError,
    IncompatibleDimensionError,
    MetricNotDefinedError,
)
from app.query.intent import QueryIntent
from app.semantic.capability import (
    DimensionRejection,
    date_dimensions,
    groupable_dimensions,
    rejection,
)
from app.semantic.models import ComparisonMetric, CumulativeMetric, Dimension, SemanticRegistry

_REJECTION_REASONS = {
    DimensionRejection.NO_JOIN_PATH: "the entities are not related in the model",
    DimensionRejection.FAN_OUT: "the join is one-to-many and would inflate the metric",
    DimensionRejection.FILTERED_MEASURE: (
        "the metric's own measure already filters on that column, so every other group "
        "would aggregate to nothing"
    ),
}


@dataclass(frozen=True)
class ResolvedIntent:
    """A validated intent plus the date dimension it implied but did not name."""

    intent: QueryIntent
    date_dimension: Dimension | None


def validate_intent(intent: QueryIntent, registry: SemanticRegistry) -> ResolvedIntent:
    if intent.metric not in registry.metrics:
        raise MetricNotDefinedError(intent.metric, allowed=sorted(registry.metrics))
    metric = registry.metric(intent.metric)

    groupable = groupable_dimensions(metric, registry)
    for field, names in (("group_by", intent.group_by), ("filters", list(intent.filters))):
        for name in names:
            _check_sliceable(metric.name, name, field, groupable, registry)

    return ResolvedIntent(intent=intent, date_dimension=_resolve_date_dimension(intent, registry))


def _check_sliceable(
    metric_name: str,
    dimension_name: str,
    field: str,
    groupable: list[str],
    registry: SemanticRegistry,
) -> None:
    if dimension_name not in registry.dimensions:
        raise DimensionNotDefinedError(dimension_name, field=field, allowed=groupable)
    if dimension_name in groupable:
        return
    reason = rejection(registry.metric(metric_name), registry.dimension(dimension_name), registry)
    assert reason is not None  # not groupable, so `rejection` named a cause
    raise IncompatibleDimensionError(
        metric_name,
        dimension_name,
        _REJECTION_REASONS[reason],
        field=field,
        allowed=groupable,
    )


def _resolve_date_dimension(intent: QueryIntent, registry: SemanticRegistry) -> Dimension | None:
    """The one date to bucket and range on, or None when the intent asks nothing of time."""

    metric = registry.metric(intent.metric)
    is_temporal = isinstance(metric, (ComparisonMetric, CumulativeMetric))
    if not (is_temporal or intent.grain is not None or intent.date_range is not None):
        return None

    reachable = date_dimensions(metric, registry)

    if intent.date_dimension is not None:
        named = intent.date_dimension
        if named not in registry.dimensions:
            raise DateDimensionError(f"Unknown dimension {named!r}.", allowed=reachable)
        if named not in reachable:
            dimension = registry.dimension(named)
            reason = (
                f"{named!r} is not a date dimension"
                if dimension.date_role is None
                else f"{named!r} is on {dimension.entity!r}, which is not safely joinable"
            )
            raise DateDimensionError(f"Cannot anchor on {reason}.", allowed=reachable)
        return registry.dimension(named)

    if not reachable:
        raise DateDimensionError(
            f"No date dimension is reachable from metric {metric.name!r}.", allowed=[]
        )
    if len(reachable) > 1:
        # Never guess between date roles (lead vs referral vs stage): which one a question
        # means changes the answer, so the intent must say.
        raise DateDimensionError(
            f"Metric {metric.name!r} has several date dimensions; name one.", allowed=reachable
        )
    return registry.dimension(reachable[0])
