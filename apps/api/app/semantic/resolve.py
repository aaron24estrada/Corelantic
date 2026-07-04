"""Resolve a metric to its component measures and single entity.

Pure registry logic — no SQL, no SQLAlchemy — so both the loader (``validate_registry``,
at load) and the compiler (at query time) share one definition of "which measures back
this metric" and "do they agree on an entity". Keeping it here respects the one-way
dependency flow: ``query`` may depend on ``semantic``, never the reverse.
"""

from typing import assert_never

from app.semantic.errors import MixedEntityError
from app.semantic.models import (
    ComparisonMetric,
    CumulativeMetric,
    DerivedMetric,
    Metric,
    RatioMetric,
    SemanticRegistry,
    SimpleMetric,
)


def measure_names(metric: Metric) -> list[str]:
    """The measures a metric is built from, whatever its type."""

    if isinstance(metric, SimpleMetric):
        return [metric.measure]
    if isinstance(metric, RatioMetric):
        return [metric.numerator, metric.denominator]
    if isinstance(metric, DerivedMetric):
        return list(metric.measures)
    if isinstance(metric, (CumulativeMetric, ComparisonMetric)):
        return [metric.measure]
    assert_never(metric)


def resolve_metric_entity(metric: Metric, registry: SemanticRegistry) -> str:
    """The single entity every component measure lives on.

    Resolves each component measure (raising ``UnknownMeasureError`` for a dangling
    reference) and confirms they agree on one entity (``MixedEntityError`` otherwise).
    """

    entities = {registry.measure(name).entity for name in measure_names(metric)}
    if len(entities) != 1:
        raise MixedEntityError(metric.name, sorted(entities))
    return entities.pop()
