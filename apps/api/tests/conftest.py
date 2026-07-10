import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_registry
from app.core.config import Settings, get_settings
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
