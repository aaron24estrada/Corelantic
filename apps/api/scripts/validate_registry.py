"""Validate the semantic registry: load every YAML file, merge, and check it.

Run ``make validate`` (or ``uv run python scripts/validate_registry.py``). Exits non-zero
with a clear message on any authoring error the loader can catch without a live database —
duplicate names, dangling entity/measure references, cross-entity metrics, bad derived
formulas, ambiguous synonyms, unknown fields. Checking columns against the *real* source
schema is deferred until the Azure SQL schema lands (docs O-1/O-2); this covers everything
knowable from the registry itself.
"""

import sys
from pathlib import Path

import yaml
from pydantic import ValidationError

from app.core.config import get_settings
from app.semantic.errors import SemanticError
from app.semantic.registry import load_registry


def validate(directory: Path, allowed_schemas: set[str] | None = None) -> tuple[bool, str]:
    try:
        registry = load_registry(directory, allowed_schemas)
    except (SemanticError, ValidationError, yaml.YAMLError, OSError) as error:
        return False, f"✗ {directory}: {error}"
    summary = (
        f"✓ {directory}: {len(registry.entities)} entities, {len(registry.measures)} measures, "
        f"{len(registry.dimensions)} dimensions, {len(registry.metrics)} metrics"
    )
    return True, summary


def main() -> int:
    settings = get_settings()
    # Same allow-list the app enforces, so `make validate` can't pass what the app rejects.
    ok, message = validate(settings.semantic_dir, settings.allowed_schemas)
    print(message)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
