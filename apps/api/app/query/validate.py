"""Validate a query intent against the registry, and resolve what it left implicit.

This is the gate the compiler stands behind. After ``validate_intent`` every name in the
intent is defined, every dimension is one the metric can actually be sliced by, the date
dimension a time question needs has been chosen, a relative window has become explicit dates,
and a comparison knows whether it reports points or percent. The compiler keeps its own
registry lookups — a failure *there* means the registry disagrees with itself, which is our
bug and a 500, not the caller's mistake and a 422.

Resolution happens once, here, and the resolved intent is what both the compiler and the API
response see. So the window a chart is drawn from is the window its caption claims, and the
validator and the compiler cannot disagree about which date a trend is anchored on.
"""

from dataclasses import dataclass
from datetime import date

from app.query.errors import (
    AccumulationResetError,
    CompareWithAccumulateError,
    DateDimensionError,
    DimensionNotDefinedError,
    GrainRequiredError,
    IncompatibleDimensionError,
    MetricNotDefinedError,
    NotAdditiveError,
)
from app.query.intent import Comparison, QueryIntent
from app.query.time import DateRange, Grain, RelativeRange, nesting_grains, nests_in, resolve_range
from app.semantic.capability import (
    DimensionRejection,
    date_dimensions,
    groupable_dimensions,
    is_additive,
    rejection,
)
from app.semantic.models import Dimension, Metric, MetricFormat, SemanticRegistry

_REJECTION_REASONS = {
    DimensionRejection.NO_JOIN_PATH: "the entities are not related in the model",
    DimensionRejection.FAN_OUT: "the join is one-to-many and would inflate the metric",
    DimensionRejection.FILTERED_MEASURE: (
        "the metric's own measure already filters on that column, so every other group "
        "would aggregate to nothing"
    ),
}

_GRAINS = sorted(grain.value for grain in Grain)


@dataclass(frozen=True)
class ResolvedIntent:
    """A canonical intent — nothing implicit left — with what it resolved to, already typed.

    ``intent.date_range`` still carries the request's union type for echoing back to the
    caller; ``date_range`` here is the explicit window the compiler binds.
    """

    intent: QueryIntent
    date_dimension: Dimension | None
    date_range: DateRange | None


def validate_intent(
    intent: QueryIntent, registry: SemanticRegistry, *, today: date | None = None
) -> ResolvedIntent:
    if intent.metric not in registry.metrics:
        raise MetricNotDefinedError(intent.metric, allowed=sorted(registry.metrics))
    metric = registry.metric(intent.metric)

    groupable = groupable_dimensions(metric, registry)
    for field, names in (("group_by", intent.group_by), ("filters", list(intent.filters))):
        for name in names:
            _check_sliceable(metric, name, field, groupable, registry)

    _check_time_modifiers(intent, metric, registry)

    date_dimension = _resolve_date_dimension(intent, registry)
    date_range = _resolve_date_range(intent.date_range, today)
    canonical = intent.model_copy(
        update={
            "date_range": date_range,
            "date_dimension": date_dimension.name if date_dimension is not None else None,
            "compare": _resolve_comparison(intent.compare, metric),
        }
    )
    return ResolvedIntent(intent=canonical, date_dimension=date_dimension, date_range=date_range)


def _check_sliceable(
    metric: Metric,
    dimension_name: str,
    field: str,
    groupable: list[str],
    registry: SemanticRegistry,
) -> None:
    if dimension_name not in registry.dimensions:
        raise DimensionNotDefinedError(dimension_name, field=field, allowed=groupable)
    # `rejection` is the truth, not membership of `groupable` — which is only its projection.
    # Asking it directly means there is no state in which we know a dimension is rejected but
    # not why, so no assertion to strip away under -O.
    reason = rejection(metric, registry.dimension(dimension_name), registry)
    if reason is None:
        return
    raise IncompatibleDimensionError(
        metric.name,
        dimension_name,
        _REJECTION_REASONS[reason],
        field=field,
        allowed=groupable,
    )


def _check_time_modifiers(intent: QueryIntent, metric: Metric, registry: SemanticRegistry) -> None:
    if intent.compare is not None and intent.accumulate is not None:
        raise CompareWithAccumulateError()

    if intent.compare is not None and intent.grain is None:
        raise GrainRequiredError("compare", allowed=_GRAINS)

    if intent.accumulate is None:
        return
    if intent.grain is None:
        raise GrainRequiredError("accumulate", allowed=_GRAINS)
    if not is_additive(metric, registry):
        raise NotAdditiveError(
            metric.name,
            allowed=sorted(m.name for m in registry.metrics.values() if is_additive(m, registry)),
        )
    reset = intent.accumulate.reset
    if not nests_in(intent.grain, reset):
        raise AccumulationResetError(
            intent.grain.value, reset.value, allowed=nesting_grains(intent.grain)
        )


def _resolve_comparison(compare: Comparison | None, metric: Metric) -> Comparison | None:
    """Pin down whether a comparison reports percent or points, so nobody has to guess later."""

    if compare is None:
        return None
    if compare.kind is not None:
        return compare
    # A rate that moves 20% -> 24% rose four *points*. Reporting the relative change of a
    # ratio is defensible arithmetic and a misleading headline, so percent metrics default
    # to the absolute one.
    if metric.format is MetricFormat.PERCENT:
        return Comparison(kind="change")
    return Comparison(kind="pct")


def _resolve_date_range(
    date_range: DateRange | RelativeRange | None, today: date | None
) -> DateRange | None:
    if not isinstance(date_range, RelativeRange):
        return date_range
    if today is None:
        # A caller reached the validator with a relative window and no reference date. The
        # boundary owns the clock; a default here would silently make two visuals on one
        # dashboard load disagree across midnight.
        raise ValueError("a relative date range needs a reference date")
    return resolve_range(date_range, today)


def _resolve_date_dimension(intent: QueryIntent, registry: SemanticRegistry) -> Dimension | None:
    """The one date to bucket and range on, or None when the intent asks nothing of time."""

    metric = registry.metric(intent.metric)
    reachable = date_dimensions(metric, registry)

    # A named date dimension is checked even when nothing will use it. Every field of an
    # intent is validated against the registry (standards/principles.md); accepting a name we
    # do not define, because this particular request happens to ignore it, teaches a planner
    # that the name is valid.
    named = _validate_named_date_dimension(intent.date_dimension, reachable, registry)

    if intent.grain is None and intent.date_range is None:
        # Returning `named` here would join its entity in for a column nothing selects.
        return None
    if named is not None:
        return named

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


def _validate_named_date_dimension(
    named: str | None, reachable: list[str], registry: SemanticRegistry
) -> Dimension | None:
    if named is None:
        return None
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
