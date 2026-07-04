import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_registry
from app.core.config import Settings, get_settings
from app.main import create_app
from app.semantic.models import Dimension, Entity, Measure, Metric, SemanticRegistry

INTERNAL_KEY = "test-internal-key"


@pytest.fixture
def registry() -> SemanticRegistry:
    return SemanticRegistry(
        entities={"leads": Entity(name="leads", label="Leads", source="analytics.v_leads")},
        measures={
            "lead_count": Measure(name="lead_count", entity="leads", expression="count(*)"),
        },
        metrics={
            "new_leads": Metric(
                name="new_leads",
                label="New leads",
                description="Count of new intake leads.",
                measure="lead_count",
            ),
        },
        dimensions={
            "channel": Dimension(name="channel", label="Channel", entity="leads", column="channel"),
            "region": Dimension(name="region", label="Region", entity="leads", column="metro"),
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
