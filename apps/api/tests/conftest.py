import os
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_registry
from app.core.config import ENV_PREFIX, Settings, get_settings
from app.main import create_app
from app.semantic.models import (
    Aggregation,
    Dimension,
    Entity,
    Measure,
    SemanticRegistry,
    SimpleMetric,
)

INTERNAL_KEY = "test-internal-key"


@pytest.fixture(scope="session", autouse=True)
def isolated_settings() -> Iterator[None]:
    """Settings read nothing from the machine the tests happen to run on.

    ``Settings`` loads from two ambient sources — ``apps/api/.env`` and every
    ``CORELANTIC_API_*`` process variable — so without this every test inherits whichever a
    developer or CI runner happens to have set. Tests asserting *unset* configuration then fail
    for people who followed the setup docs, and tests asserting a value pass only because that
    value was in someone's file. Both are the same bug wearing different faces (#48).

    Autouse, because hermeticity is the default a suite should not have to opt into. A test that
    genuinely wants an ambient value sets it explicitly, after this has cleared the ground.

    Session-scoped, and not merely autouse: pytest builds a module-scoped fixture *before* a
    function-scoped one, so several modules loaded their registry from an ambient
    ``semantic_dir`` before a function-scoped guard could strip it. That needs its own
    ``MonkeyPatch`` context, since the built-in ``monkeypatch`` fixture is function-scoped.
    """

    with pytest.MonkeyPatch.context() as patch:
        for name in [key for key in os.environ if key.startswith(ENV_PREFIX)]:
            patch.delenv(name)
        # pydantic-settings reads `env_file` from model_config at construction, not at class
        # definition, so overriding it here disables dotenv for any Settings() that does not
        # name a file itself. `Settings(_env_file=...)` still reads one — a test doing that is
        # asking for a file on purpose, and nothing here does.
        patch.setitem(Settings.model_config, "env_file", None)

        # Every cache downstream of the settings, not just the settings themselves: a registry
        # loaded from an ambient `semantic_dir` or `allowed_schemas` would outlive the patch
        # that was supposed to remove them.
        _clear_settings_caches()
        yield
        _clear_settings_caches()


def _clear_settings_caches() -> None:
    get_settings.cache_clear()
    get_registry.cache_clear()


@pytest.fixture
def registry() -> SemanticRegistry:
    return SemanticRegistry(
        entities={"cases": Entity(name="cases", label="Leads", source="gold_tspot.cases")},
        measures={
            "lead_count": Measure(name="lead_count", entity="cases", agg=Aggregation.COUNT),
        },
        metrics={
            "new_leads": SimpleMetric(
                name="new_leads",
                label="New leads",
                description="Count of new intake leads.",
                measure="lead_count",
            ),
        },
        dimensions={
            "channel": Dimension(
                name="channel", label="Channel", entity="cases", column="source_category"
            ),
            # Real column on the seeded fixture, so a date-ranged intent actually runs.
            "lead_date": Dimension(
                name="lead_date",
                label="Lead date",
                entity="cases",
                column="CreateDate",
                date_role="lead",
            ),
        },
    )


@pytest.fixture
def settings() -> Settings:
    return Settings(internal_api_key=INTERNAL_KEY)


@pytest.fixture
def client(registry: SemanticRegistry, settings: Settings) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_registry] = lambda: registry
    app.dependency_overrides[get_settings] = lambda: settings
    client = TestClient(app)
    client.headers["X-Internal-Api-Key"] = INTERNAL_KEY
    return client
