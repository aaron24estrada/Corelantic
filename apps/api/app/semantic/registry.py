"""Load the semantic registry from YAML.

Each YAML file contributes metrics and dimensions keyed by name; the key is the
identifier, so it is injected as the model's ``name``. Loading is deliberately simple
and pure enough to unit-test: ``build_registry`` takes parsed data, ``load_registry``
adds only the file IO around it.
"""

from pathlib import Path
from typing import Any

import yaml

from app.semantic.models import Dimension, Metric, SemanticRegistry


def build_registry(raw: dict[str, Any]) -> SemanticRegistry:
    raw_metrics: dict[str, dict[str, Any]] = raw.get("metrics") or {}
    raw_dimensions: dict[str, dict[str, Any]] = raw.get("dimensions") or {}
    metrics = {name: Metric(name=name, **body) for name, body in raw_metrics.items()}
    dimensions = {name: Dimension(name=name, **body) for name, body in raw_dimensions.items()}
    return SemanticRegistry(metrics=metrics, dimensions=dimensions)


def load_registry(directory: Path) -> SemanticRegistry:
    metrics: dict[str, Metric] = {}
    dimensions: dict[str, Dimension] = {}
    for path in sorted(directory.glob("*.yaml")):
        raw: dict[str, Any] = yaml.safe_load(path.read_text()) or {}
        registry = build_registry(raw)
        metrics.update(registry.metrics)
        dimensions.update(registry.dimensions)
    return SemanticRegistry(metrics=metrics, dimensions=dimensions)
