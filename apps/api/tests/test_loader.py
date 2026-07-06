from pathlib import Path

import pytest
from pydantic import ValidationError

from app.semantic.errors import (
    AmbiguousTermError,
    DuplicateNameError,
    MalformedRegistryError,
)
from app.semantic.models import SemanticRegistry, SimpleMetric
from app.semantic.registry import build_registry, load_registry, merge_registries
from scripts.validate_registry import validate


def _write(directory: Path, name: str, text: str) -> None:
    (directory / name).write_text(text)


# --- multi-file merge -----------------------------------------------------------------


def test_load_merges_definitions_across_files(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "facts.yaml",
        "entities:\n  leads:\n    label: Leads\n    source: v_leads\n"
        "measures:\n  lead_count:\n    entity: leads\n    agg: count\n",
    )
    _write(
        tmp_path,
        "metrics.yaml",
        "metrics:\n  new_leads:\n    label: New\n    description: x\n    measure: lead_count\n",
    )
    registry = load_registry(tmp_path)
    assert set(registry.entities) == {"leads"}
    metric = registry.metric("new_leads")
    assert isinstance(metric, SimpleMetric)
    assert metric.measure == "lead_count"


def test_duplicate_name_across_files_errors() -> None:
    first = build_registry({"entities": {"leads": {"label": "Leads", "source": "v_leads"}}})
    second = build_registry({"entities": {"leads": {"label": "Leads 2", "source": "v_other"}}})
    with pytest.raises(DuplicateNameError):
        merge_registries([first, second])


def test_duplicate_key_within_a_file_errors(tmp_path: Path) -> None:
    # pyyaml would silently keep the last; the loader rejects it.
    _write(
        tmp_path,
        "dupe.yaml",
        "measures:\n"
        "  lead_count:\n    entity: leads\n    agg: count\n"
        "  lead_count:\n    entity: leads\n    agg: sum\n    column: x\n",
    )
    with pytest.raises(DuplicateNameError):
        load_registry(tmp_path)


def test_malformed_section_shape_errors() -> None:
    with pytest.raises(MalformedRegistryError):
        build_registry({"metrics": []})  # a list, not a mapping


# --- synonym matching -----------------------------------------------------------------


def _registry_with_synonyms() -> SemanticRegistry:
    return build_registry(
        {
            "entities": {"leads": {"label": "Leads", "source": "v_leads"}},
            "measures": {"spend_total": {"entity": "leads", "agg": "sum", "column": "spend"}},
            "metrics": {
                "marketing_spend": {
                    "label": "Marketing spend",
                    "description": "x",
                    "measure": "spend_total",
                    "synonyms": ["spend", "ad spend"],
                },
            },
            "dimensions": {
                "region": {
                    "label": "Region",
                    "entity": "leads",
                    "column": "metro",
                    "synonyms": ["metro", "area"],
                },
            },
        }
    )


def test_match_resolves_name_and_synonyms_case_insensitively() -> None:
    registry = _registry_with_synonyms()
    assert registry.match_metric("marketing_spend") == "marketing_spend"
    assert registry.match_metric("Ad Spend") == "marketing_spend"
    assert registry.match_metric("unknown") is None
    assert registry.match_dimension("METRO") == "region"
    assert registry.match_metric("   ") is None  # blank input never matches


def test_blank_synonym_is_rejected() -> None:
    with pytest.raises(ValidationError):
        build_registry(
            {
                "entities": {"leads": {"label": "Leads", "source": "v_leads"}},
                "measures": {"lead_count": {"entity": "leads", "agg": "count"}},
                "metrics": {
                    "m": {
                        "label": "M",
                        "description": "x",
                        "measure": "lead_count",
                        "synonyms": ["  "],
                    },
                },
            }
        )


def test_validate_rejects_a_synonym_shared_by_two_metrics() -> None:
    from app.semantic.registry import validate_registry

    registry = build_registry(
        {
            "entities": {"leads": {"label": "Leads", "source": "v_leads"}},
            "measures": {
                "a": {"entity": "leads", "agg": "count"},
                "b": {"entity": "leads", "agg": "count"},
            },
            "metrics": {
                "first": {"label": "F", "description": "x", "measure": "a", "synonyms": ["dupe"]},
                "second": {"label": "S", "description": "x", "measure": "b", "synonyms": ["dupe"]},
            },
        }
    )
    with pytest.raises(AmbiguousTermError):
        validate_registry(registry)


# --- validate CLI ---------------------------------------------------------------------


def test_validate_cli_passes_on_a_good_registry(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "ok.yaml",
        "entities:\n  leads:\n    label: Leads\n    source: v_leads\n"
        "measures:\n  lead_count:\n    entity: leads\n    agg: count\n"
        "metrics:\n  new_leads:\n    label: New\n    description: x\n    measure: lead_count\n",
    )
    ok, message = validate(tmp_path)
    assert ok
    assert "1 entities" in message


def test_validate_cli_fails_on_a_dangling_reference(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "bad.yaml",
        "entities:\n  leads:\n    label: Leads\n    source: v_leads\n"
        "metrics:\n  broken:\n    label: B\n    description: x\n    measure: missing\n",
    )
    ok, message = validate(tmp_path)
    assert not ok
    assert message.startswith("✗")


def test_shipped_example_registry_is_valid() -> None:
    # The placeholder registry we ship must always load and validate (would raise otherwise).
    from app.core.config import get_settings

    registry = load_registry(get_settings().semantic_dir)
    assert registry.metrics
