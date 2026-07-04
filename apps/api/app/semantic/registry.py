"""Load the semantic registry from YAML.

Each YAML file contributes entities, dimensions, measures, and metrics keyed by name;
the key is the identifier, so it is injected as the model's ``name``. Loading stays
simple and pure enough to unit-test: ``build_registry`` constructs from parsed data,
``validate_registry`` checks the references between the four types resolve, and
``load_registry`` adds only the file IO around them.

References are validated after the cross-file merge, not per file, so a dimension in
one file may point at an entity defined in another.
"""

from pathlib import Path
from typing import Any

import yaml

from app.semantic.models import Dimension, Entity, Measure, Metric, SemanticRegistry


def build_registry(raw: dict[str, Any]) -> SemanticRegistry:
    raw_entities: dict[str, dict[str, Any]] = raw.get("entities") or {}
    raw_dimensions: dict[str, dict[str, Any]] = raw.get("dimensions") or {}
    raw_measures: dict[str, dict[str, Any]] = raw.get("measures") or {}
    raw_metrics: dict[str, dict[str, Any]] = raw.get("metrics") or {}
    return SemanticRegistry(
        entities={name: Entity(name=name, **body) for name, body in raw_entities.items()},
        dimensions={name: Dimension(name=name, **body) for name, body in raw_dimensions.items()},
        measures={name: Measure(name=name, **body) for name, body in raw_measures.items()},
        metrics={name: Metric(name=name, **body) for name, body in raw_metrics.items()},
    )


def validate_registry(registry: SemanticRegistry) -> SemanticRegistry:
    """Raise if any reference between the four types dangles; return the registry.

    Fail loud at load: a metric pointing at a missing measure, or a dimension/measure at
    a missing entity, is an authoring bug we surface now rather than at query time. This
    is the schema-bounded guarantee the compiler and agent rely on (docs/concepts.md §3).
    """

    for dimension in registry.dimensions.values():
        registry.entity(dimension.entity)
    for measure in registry.measures.values():
        registry.entity(measure.entity)
    for metric in registry.metrics.values():
        registry.measure(metric.measure)
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
