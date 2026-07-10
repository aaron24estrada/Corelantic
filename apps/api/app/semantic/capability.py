"""What the model will let you ask of a metric.

The registry bounds the questions that are answerable, and two rules do the bounding: a
dimension may slice a metric only if its entity joins to the metric's without fanning out
(a fan-out multiplies the fact rows and inflates every measure built on them), and only if
it does not slice the very column one of the metric's measures already filters on (the
predicate pins that column, so every other group aggregates to nothing).

Both rules live here once and are read two ways — as a *predicate* when an intent is
validated, and as a *projection* when the catalog publishes what is askable. Written twice
they would drift, and the catalog would advertise questions the compiler refuses.

Pure registry logic: no SQLAlchemy and no intent. ``query`` may depend on ``semantic``,
never the reverse (standards/fastapi.md).
"""

from enum import StrEnum

from app.semantic.errors import NoJoinPathError
from app.semantic.joins import find_join_path
from app.semantic.models import Dimension, Metric, SemanticRegistry
from app.semantic.resolve import measure_names, resolve_metric_entity


class DimensionRejection(StrEnum):
    """Why a dimension cannot slice a metric. Explanatory only — the repair is the same."""

    NO_JOIN_PATH = "no_join_path"
    FAN_OUT = "fan_out"
    FILTERED_MEASURE = "filtered_measure"


def is_joinable_without_fan_out(base: str, entity: str, registry: SemanticRegistry) -> bool:
    """Whether ``entity`` can be joined to ``base`` without multiplying the base's rows."""

    if entity == base:
        return True
    try:
        steps = find_join_path(base, entity, registry)
    except NoJoinPathError:
        return False
    return not any(step.fans_out for step in steps)


def filtered_columns(metric: Metric, registry: SemanticRegistry) -> set[tuple[str, str]]:
    """The (entity, column) pairs the metric's component measures already filter on."""

    pairs: set[tuple[str, str]] = set()
    for name in measure_names(metric):
        measure = registry.measure(name)
        if measure.filter is not None:
            pairs.add((measure.entity, measure.filter.column))
    return pairs


def rejection(
    metric: Metric, dimension: Dimension, registry: SemanticRegistry
) -> DimensionRejection | None:
    """Why ``dimension`` cannot slice ``metric``, or None when it can."""

    if (dimension.entity, dimension.column) in filtered_columns(metric, registry):
        return DimensionRejection.FILTERED_MEASURE

    base = resolve_metric_entity(metric, registry)
    if dimension.entity == base:
        return None
    try:
        steps = find_join_path(base, dimension.entity, registry)
    except NoJoinPathError:
        return DimensionRejection.NO_JOIN_PATH
    return DimensionRejection.FAN_OUT if any(step.fans_out for step in steps) else None


def groupable_dimensions(metric: Metric, registry: SemanticRegistry) -> list[str]:
    """Every dimension this metric may be grouped or filtered by, sorted."""

    return sorted(
        dimension.name
        for dimension in registry.dimensions.values()
        if rejection(metric, dimension, registry) is None
    )


def date_dimensions(metric: Metric, registry: SemanticRegistry) -> list[str]:
    """The date dimensions a time question about this metric may anchor on, sorted.

    A funnel metric lives on ``stages`` but is trended by the lead's intake date on ``cases``
    — reachable many-to-one, so joining it neither fans out nor changes the aggregate.
    """

    base = resolve_metric_entity(metric, registry)
    return sorted(
        dimension.name
        for dimension in registry.dimensions.values()
        if dimension.date_role is not None
        and is_joinable_without_fan_out(base, dimension.entity, registry)
    )
