from fastapi.testclient import TestClient


def test_list_metrics_returns_registry_metrics(client: TestClient) -> None:
    response = client.get("/api/v1/metrics")
    assert response.status_code == 200
    names = [metric["name"] for metric in response.json()["metrics"]]
    assert names == ["new_leads"]


def test_get_metric_is_unavailable_until_data_source_configured(client: TestClient) -> None:
    # No data source is provisioned yet (docs O-1), so the read is a clean 503.
    response = client.get("/api/v1/metrics/new_leads")
    assert response.status_code == 503
