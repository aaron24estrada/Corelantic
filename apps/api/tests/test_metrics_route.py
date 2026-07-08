from typing import cast

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.adapters.data.fixture import FixtureDataSource
from app.api.dependencies import get_data_source
from tests.conftest import INTERNAL_KEY


def test_list_metrics_returns_registry_metrics(client: TestClient) -> None:
    response = client.get("/api/v1/metrics")
    assert response.status_code == 200
    names = [metric["name"] for metric in response.json()["metrics"]]
    assert names == ["new_leads"]


def test_get_metric_is_unavailable_until_data_source_configured(client: TestClient) -> None:
    # The default (azure_sql) is not provisioned yet (docs O-1), so the read is a clean 503.
    response = client.get("/api/v1/metrics/new_leads")
    assert response.status_code == 503


def test_get_metric_returns_data_from_the_fixture_source(client: TestClient) -> None:
    # With the fixture source wired in, the same route returns real rows instead of 503.
    source = FixtureDataSource(leads=100, seed=1)
    app = cast(FastAPI, client.app)
    app.dependency_overrides[get_data_source] = lambda: source
    try:
        response = client.get("/api/v1/metrics/new_leads")
        assert response.status_code == 200
        assert response.json() == {"name": "new_leads", "rows": [{"new_leads": 100}]}
    finally:
        del app.dependency_overrides[get_data_source]
    # Auth still applies to the data path.
    assert client.headers["X-Internal-Api-Key"] == INTERNAL_KEY
