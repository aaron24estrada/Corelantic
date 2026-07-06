"""Load the semantic registry from YAML.

Each YAML file contributes entities, dimensions, measures, and metrics keyed by name;
the key is the identifier, so it is injected as the model's ``name``. Loading stays
simple and pure enough to unit-test: ``build_registry`` constructs from parsed data,
``validate_registry`` checks the references between the types resolve, and
``load_registry`` adds only the file IO around them.

A metric's ``type`` selects its variant (defaulting to ``simple`` when omitted, so plain
one-measure definitions stay terse). References are validated after the cross-file merge,
not per file, so a dimension or measure in one file may point at an entity in another.
"""

from pathlib import Path
from typing import Any

import yaml

from app.semantic.formula import validate_formula
from app.semantic.models import (
    METRIC_ADAPTER,
    DerivedMetric,
    Dimension,
    Entity,
    Measure,
    Metric,
    MetricType,
    SemanticRegistry,
)
from app.semantic.resolve import resolve_metric_entity


def _build_metric(name: str, body: dict[str, Any]) -> Metric:
    return METRIC_ADAPTER.validate_python({"type": MetricType.SIMPLE, **body, "name": name})


def build_registry(raw: dict[str, Any]) -> SemanticRegistry:
    raw_entities: dict[str, dict[str, Any]] = raw.get("entities") or {}
    raw_dimensions: dict[str, dict[str, Any]] = raw.get("dimensions") or {}
    raw_measures: dict[str, dict[str, Any]] = raw.get("measures") or {}
    raw_metrics: dict[str, dict[str, Any]] = raw.get("metrics") or {}
    return SemanticRegistry(
        entities={name: Entity(name=name, **body) for name, body in raw_entities.items()},
        dimensions={name: Dimension(name=name, **body) for name, body in raw_dimensions.items()},
        measures={name: Measure(name=name, **body) for name, body in raw_measures.items()},
        metrics={name: _build_metric(name, body) for name, body in raw_metrics.items()},
    )


def validate_registry(registry: SemanticRegistry) -> SemanticRegistry:
    """Raise if any reference between the types dangles; return the registry.

    Fail loud at load: a dimension/measure pointing at a missing entity, or a metric at a
    missing (or cross-entity) measure, is an authoring bug we surface now rather than at
    query time. This is the schema-bounded guarantee from docs/concepts.md §3.
    """

    for entity in registry.entities.values():
        for edge in entity.joins:
            registry.entity(edge.to)  # a join edge must point at a real entity
    for dimension in registry.dimensions.values():
        registry.entity(dimension.entity)
    for measure in registry.measures.values():
        registry.entity(measure.entity)
    for metric in registry.metrics.values():
        # Resolves every component measure and confirms they share one entity.
        resolve_metric_entity(metric, registry)
        if isinstance(metric, DerivedMetric):
            # Formula must parse and reference only the metric's declared measures.
            validate_formula(metric.expression, set(metric.measures))
    return registry


def load_registry(directory: Path) -> SemanticRegistry:
    entities: dict[str, Entity] = {}
    dimensions: dict[str, Dimension] = {}
    measures: dict[str, Measure] = {}
    metrics: dict[str, Metric] = {}
    for path in sorted(directory.glob("*.yaml")):
        raw: dict[str, Any] = yaml.safe_load(path.read_text()) or {}
        registry = build_registry(raw)
        entities.update(registry.entities)
        dimensions.update(registry.dimensions)
        measures.update(registry.measures)
        metrics.update(registry.metrics)
    return validate_registry(
        SemanticRegistry(
            entities=entities, dimensions=dimensions, measures=measures, metrics=metrics
        )
    )
