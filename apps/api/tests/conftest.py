import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_registry
from app.main import create_app
from app.semantic.models import Dimension, Metric, SemanticRegistry


@pytest.fixture
def registry() -> SemanticRegistry:
    return SemanticRegistry(
        metrics={
            "new_leads": Metric(
                name="new_leads",
                label="New leads",
                description="Count of new intake leads.",
                source="analytics.v_leads",
                expression="count(*)",
            ),
        },
        dimensions={
            "channel": Dimension(
                name="channel",
                label="Channel",
                source="analytics.v_leads",
                column="channel",
            ),
            "region": Dimension(
                name="region",
                label="Region",
                source="analytics.v_leads",
                column="metro",
            ),
        },
    )


@pytest.fixture
def client(registry: SemanticRegistry) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_registry] = lambda: registry
    return TestClient(app)
