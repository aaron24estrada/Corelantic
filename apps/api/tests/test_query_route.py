"""The deterministic query surface: an intent in, a described ResultSet out."""

from typing import Any, cast

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.adapters.data.fixture import FixtureDataSource
from app.api.dependencies import get_data_source
from tests.conftest import INTERNAL_KEY


def _with_fixture(client: TestClient) -> FastAPI:
    app = cast(FastAPI, client.app)
    app.dependency_overrides[get_data_source] = lambda: FixtureDataSource(leads=100, seed=1)
    return app


def _post(client: TestClient, intent: dict[str, Any]) -> Any:
    app = _with_fixture(client)
    try:
        return client.post("/api/v1/query", json=intent)
    finally:
        del app.dependency_overrides[get_data_source]


def test_a_bare_intent_returns_rows_and_their_column_schema(client: TestClient) -> None:
    response = _post(client, {"metric": "new_leads"})
    assert response.status_code == 200
    body = response.json()

    assert body["rows"] == [{"new_leads": 100}]
    assert body["columns"] == [
        {"name": "new_leads", "role": "metric", "label": "New leads", "format": "number"}
    ]
    # Auth still guards the data path.
    assert client.headers["X-Internal-Api-Key"] == INTERNAL_KEY


def test_the_response_echoes_the_intent_it_actually_ran(client: TestClient) -> None:
    # The window a chart is drawn from is the window its caption can claim.
    response = _post(client, {"metric": "new_leads", "date_range": "last_30_days"})
    assert response.status_code == 200
    resolved = response.json()["resolved_intent"]

    assert isinstance(resolved["date_range"], dict)  # resolved to explicit dates, not a token
    assert resolved["date_range"]["start"] < resolved["date_range"]["end"]
    assert resolved["date_dimension"] == "lead_date"


def test_an_intent_the_model_cannot_answer_is_422_with_the_alternatives(
    client: TestClient,
) -> None:
    response = _post(client, {"metric": "new_leads", "group_by": ["nonsense"]})
    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "unknown_dimension"
    assert body["field"] == "group_by"
    assert body["allowed"] == ["channel", "lead_date"]


def test_an_unknown_metric_in_the_body_is_422_not_404(client: TestClient) -> None:
    response = _post(client, {"metric": "nope"})
    assert response.status_code == 422
    assert response.json()["code"] == "unknown_metric"
    assert response.json()["allowed"] == ["new_leads"]


def test_an_invented_relative_range_is_rejected_by_the_schema(client: TestClient) -> None:
    # RelativeRange is a closed enum, so FastAPI refuses the body before we see it.
    response = _post(client, {"metric": "new_leads", "date_range": "since_the_dawn_of_time"})
    assert response.status_code == 422


def test_the_query_route_requires_the_internal_secret(client: TestClient) -> None:
    app = _with_fixture(client)
    try:
        response = client.post(
            "/api/v1/query", json={"metric": "new_leads"}, headers={"X-Internal-Api-Key": "wrong"}
        )
        assert response.status_code == 401
    finally:
        del app.dependency_overrides[get_data_source]
