"""The HTTP error contract.

The first route to raise an IntentError is POST /query (PR B); until it exists these drive
the handlers in main.py directly, because a handler nothing exercises is a handler that is
wrong. What matters is the *status* and the *body shape*: 422 with `allowed` is what lets a
caller repair an intent, and a 500 must never say why.
"""

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.adapters.factory import ProviderNotConfiguredError
from app.main import create_app
from app.query.errors import IncompatibleDimensionError, MetricNotDefinedError
from app.semantic.errors import UnknownMetricError


def _client_raising(exc: Exception) -> TestClient:
    app: FastAPI = create_app()

    @app.get("/api/v1/_raise")
    async def _raise() -> None:
        raise exc

    return TestClient(app, raise_server_exceptions=False)


def test_an_incompatible_dimension_is_422_and_names_the_alternatives() -> None:
    response = _client_raising(
        IncompatibleDimensionError(
            "new_leads",
            "stage_name",
            "the join is one-to-many and would inflate the metric",
            field="group_by",
            allowed=["channel", "state"],
        )
    ).get("/api/v1/_raise")

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "incompatible_dimension"
    assert body["field"] == "group_by"
    assert body["allowed"] == ["channel", "state"]
    assert "inflate" in body["detail"]


def test_an_unknown_metric_in_an_intent_is_422_not_404() -> None:
    # Nothing is missing at that URL; the *body* named vocabulary we do not define.
    response = _client_raising(MetricNotDefinedError("nope", allowed=["new_leads"])).get(
        "/api/v1/_raise"
    )

    assert response.status_code == 422
    assert response.json()["code"] == "unknown_metric"
    assert response.json()["allowed"] == ["new_leads"]


def test_a_semantic_error_escaping_validation_is_a_500_not_a_404() -> None:
    # It used to be 404. But after validate_intent, a raw SemanticError means the registry
    # disagrees with itself — our bug, not the caller's, and the client learns nothing.
    response = _client_raising(UnknownMetricError("nope")).get("/api/v1/_raise")

    assert response.status_code == 500
    assert response.json()["detail"] == "Internal server error."
    assert "nope" not in response.text


def test_an_unconfigured_provider_is_503() -> None:
    response = _client_raising(ProviderNotConfiguredError("no key")).get("/api/v1/_raise")
    assert response.status_code == 503


def test_a_schema_level_rejection_wears_the_same_error_body() -> None:
    # FastAPI's own 422 is a list of pydantic errors — a second shape on the status code that
    # already carries ours. A client that must narrow `detail` before showing it cannot have one
    # ErrorState, so the schema-level rejection is normalised into ErrorResponse too.
    class Payload(BaseModel):
        count: int

    app: FastAPI = create_app()

    @app.post("/api/v1/_body")
    async def _endpoint(payload: Payload) -> None: ...

    response = TestClient(app).post("/api/v1/_body", json={"count": "not a number"})

    assert response.status_code == 422
    body = response.json()
    assert isinstance(body["detail"], str)
    assert body["code"] == "invalid_request"
    assert set(body) == {"detail", "code", "field", "allowed"}


def test_an_unexpected_error_leaks_nothing() -> None:
    response = _client_raising(RuntimeError("connection string = secret")).get("/api/v1/_raise")

    assert response.status_code == 500
    assert response.json() == {
        "detail": "Internal server error.",
        "code": None,
        "field": None,
        "allowed": None,
    }
