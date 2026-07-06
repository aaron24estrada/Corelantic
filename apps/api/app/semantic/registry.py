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

from app.semantic.errors import (
    AmbiguousTermError,
    DuplicateJoinError,
    DuplicateNameError,
    MalformedRegistryError,
)
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


class _UniqueKeyLoader(yaml.SafeLoader):
    """A SafeLoader that rejects duplicate mapping keys instead of keeping the last.

    Plain ``yaml.safe_load`` silently drops all but the last of two identical keys, so a
    definition repeated *within* one file would vanish before the cross-file merge could
    see it. This makes that a load error too.
    """


def _no_duplicate_keys(loader: _UniqueKeyLoader, node: yaml.MappingNode) -> dict[Any, Any]:
    mapping: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=True)
        if key in mapping:
            raise DuplicateNameError("key", str(key))
        mapping[key] = loader.construct_object(value_node, deep=True)
    return mapping


_UniqueKeyLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _no_duplicate_keys)


def _section(raw: dict[str, Any], key: str) -> dict[str, dict[str, Any]]:
    value = raw.get(key)
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise MalformedRegistryError(f"{key!r} must be a mapping, got {type(value).__name__}")
    return value


def _build_metric(name: str, body: dict[str, Any]) -> Metric:
    return METRIC_ADAPTER.validate_python({"type": MetricType.SIMPLE, **body, "name": name})


def build_registry(raw: dict[str, Any]) -> SemanticRegistry:
    if not isinstance(raw, dict):
        raise MalformedRegistryError(f"a file must be a mapping, got {type(raw).__name__}")
    return SemanticRegistry(
        entities={n: Entity(name=n, **b) for n, b in _section(raw, "entities").items()},
        dimensions={n: Dimension(name=n, **b) for n, b in _section(raw, "dimensions").items()},
        measures={n: Measure(name=n, **b) for n, b in _section(raw, "measures").items()},
        metrics={n: _build_metric(n, b) for n, b in _section(raw, "metrics").items()},
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
        targets: set[str] = set()
        for edge in entity.joins:
            registry.entity(edge.to)  # a join edge must point at a real entity
            if edge.to in targets:  # one relationship per entity pair (no named roles yet)
                raise DuplicateJoinError(entity.name, edge.to)
            targets.add(edge.to)
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
        build_registry(yaml.load(path.read_text(), Loader=_UniqueKeyLoader) or {})
        for path in sorted(directory.glob("*.yaml"))
    ]
    return validate_registry(merge_registries(registries))
