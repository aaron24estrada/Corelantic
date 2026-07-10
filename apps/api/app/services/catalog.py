"""Publish what the model will let you ask.

Every field here is a *projection* of the same predicates ``app/query/validate.py`` enforces,
read out of ``app/semantic/capability.py``. That is the point: written twice, the catalog would
eventually advertise a question the compiler refuses, or hide one it would answer.

Pure: no database, no FastAPI. Recomputed per request — the whole thing takes about 3ms for 25
metrics over 14 dimensions, which is not worth a cache until something says otherwise.
"""

from app.query.time import Grain, RelativeRange, nesting_grains
from app.schemas.catalog import (
    AccumulationRule,
    CatalogDimension,
    CatalogMetric,
    CatalogResponse,
    MetricCapabilities,
)
from app.semantic.capability import date_dimensions, groupable_dimensions, is_additive
from app.semantic.models import Metric, SemanticRegistry


def _capabilities(metric: Metric, registry: SemanticRegistry, has_date: bool) -> MetricCapabilities:
    # Both modifiers require a grain, and a grain requires a date to bucket. A metric on an
    # entity with no reachable date can be counted and sliced, never trended.
    return MetricCapabilities(
        compare=has_date,
        accumulate=has_date and is_additive(metric, registry),
    )


def _metric(metric: Metric, registry: SemanticRegistry) -> CatalogMetric:
    dates = date_dimensions(metric, registry)
    return CatalogMetric(
        name=metric.name,
        label=metric.label,
        description=metric.description,
        type=metric.type,
        format=metric.format,
        synonyms=list(metric.synonyms),
        groupable_dimensions=groupable_dimensions(metric, registry),
        date_dimensions=dates,
        supports=_capabilities(metric, registry, has_date=bool(dates)),
    )


def build_catalog(registry: SemanticRegistry) -> CatalogResponse:
    return CatalogResponse(
        metrics=[_metric(metric, registry) for metric in registry.metrics.values()],
        dimensions=[
            CatalogDimension(
                name=dimension.name,
                label=dimension.label,
                date_role=dimension.date_role,
                members=list(dimension.members),
                synonyms=list(dimension.synonyms),
            )
            for dimension in registry.dimensions.values()
        ],
        grains=list(Grain),
        relative_ranges=list(RelativeRange),
        accumulation_resets=[
            AccumulationRule(grain=grain, resets=[Grain(value) for value in nesting_grains(grain)])
            for grain in Grain
        ],
    )
