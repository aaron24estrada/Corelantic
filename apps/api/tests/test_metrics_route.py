from fastapi.testclient import TestClient


def test_list_metrics_returns_registry_metrics(client: TestClient) -> None:
    response = client.get("/api/v1/metrics")
    assert response.status_code == 200
    names = [metric["name"] for metric in response.json()["metrics"]]
    assert names == ["new_leads"]


def test_reading_a_metric_by_path_is_gone(client: TestClient) -> None:
    # GET /metrics/{name} was POST /query with an empty intent. One way to do one thing.
    assert client.get("/api/v1/metrics/new_leads").status_code == 404
