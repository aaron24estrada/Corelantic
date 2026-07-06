"""Load the semantic registry from YAML.

Each YAML file contributes entities, dimensions, measures, and metrics keyed by name;
the key is the identifier, so it is injected as the model's ``name``. The pieces stay
pure enough to unit-test: ``build_registry`` constructs one file's data, ``merge_registries``
combines files (erroring on a name defined twice rather than silently overwriting),
``validate_registry`` checks references resolve and synonyms stay unambiguous, and
``load_registry`` adds only the file IO around them.

A metric's ``type`` selects its variant (defaulting to ``simple`` when omitted, so plain
one-measure definitions stay terse). References and synonyms are validated after the
cross-file merge, so a definition in one file may point at an entity in another.
"""

from pathlib import Path
from typing import Any

import yaml

from app.semantic.errors import AmbiguousTermError, DuplicateNameError
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
    terms,
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


def _merge_collection[T](kind: str, into: dict[str, T], incoming: dict[str, T]) -> None:
    for name, value in incoming.items():
        if name in into:
            raise DuplicateNameError(kind, name)
        into[name] = value


def merge_registries(registries: list[SemanticRegistry]) -> SemanticRegistry:
    """Combine per-file registries, erroring on a name defined in more than one file."""

    entities: dict[str, Entity] = {}
    dimensions: dict[str, Dimension] = {}
    measures: dict[str, Measure] = {}
    metrics: dict[str, Metric] = {}
    for registry in registries:
        _merge_collection("entity", entities, registry.entities)
        _merge_collection("dimension", dimensions, registry.dimensions)
        _merge_collection("measure", measures, registry.measures)
        _merge_collection("metric", metrics, registry.metrics)
    return SemanticRegistry(
        entities=entities, dimensions=dimensions, measures=measures, metrics=metrics
    )


def _check_unique_terms(kind: str, items: dict[str, Any]) -> None:
    """No name or synonym may resolve to two definitions, or matching is ambiguous."""

    owner: dict[str, str] = {}
    for item in items.values():
        for term in terms(item.name, item.synonyms):
            if term in owner and owner[term] != item.name:
                raise AmbiguousTermError(kind, term, sorted([owner[term], item.name]))
            owner[term] = item.name


def validate_registry(registry: SemanticRegistry) -> SemanticRegistry:
    """Raise if any reference dangles or a synonym is ambiguous; return the registry.

    Fail loud at load: a dimension/measure pointing at a missing entity, a metric at a
    missing (or cross-entity) measure, or a synonym that matches two definitions is an
    authoring bug we surface now rather than at query time. This is the schema-bounded
    guarantee from docs/concepts.md §3.
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
    _check_unique_terms("metric", registry.metrics)
    _check_unique_terms("dimension", registry.dimensions)
    return registry


def load_registry(directory: Path) -> SemanticRegistry:
    registries = [
        build_registry(yaml.safe_load(path.read_text()) or {})
        for path in sorted(directory.glob("*.yaml"))
    ]
    return validate_registry(merge_registries(registries))
