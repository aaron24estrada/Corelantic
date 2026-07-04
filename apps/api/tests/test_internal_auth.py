from fastapi.testclient import TestClient

from app.api.dependencies import get_registry
from app.core.config import Settings, get_settings
from app.main import create_app
from app.semantic.models import SemanticRegistry


def _app(registry: SemanticRegistry, settings: Settings) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_registry] = lambda: registry
    app.dependency_overrides[get_settings] = lambda: settings
    return TestClient(app)


def test_missing_key_is_unauthorized(registry: SemanticRegistry, settings: Settings) -> None:
    client = _app(registry, settings)  # no X-Internal-Api-Key header
    assert client.get("/api/v1/metrics").status_code == 401


def test_wrong_key_is_unauthorized(registry: SemanticRegistry, settings: Settings) -> None:
    client = _app(registry, settings)
    client.headers["X-Internal-Api-Key"] = "not-the-key"
    assert client.get("/api/v1/metrics").status_code == 401


def test_unconfigured_key_is_unavailable(registry: SemanticRegistry) -> None:
    # Fail-closed: with no secret configured, the guarded route is unavailable, not open.
    client = _app(registry, Settings(internal_api_key=None))
    assert client.get("/api/v1/metrics").status_code == 503


def test_health_is_open_without_a_key(registry: SemanticRegistry, settings: Settings) -> None:
    client = _app(registry, settings)  # no header
    assert client.get("/api/v1/health").status_code == 200
