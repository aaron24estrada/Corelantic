from fastapi.testclient import TestClient


def test_the_catalog_publishes_the_vocabulary(client: TestClient) -> None:
    response = client.get("/api/v1/catalog")
    assert response.status_code == 200
    body = response.json()

    assert [metric["name"] for metric in body["metrics"]] == ["new_leads"]
    assert {dimension["name"] for dimension in body["dimensions"]} == {"channel", "lead_date"}
    assert "week" in body["grains"]
    assert "last_90_days" in body["relative_ranges"]


def test_the_catalog_says_what_each_metric_admits(client: TestClient) -> None:
    metric = client.get("/api/v1/catalog").json()["metrics"][0]

    assert metric["groupable_dimensions"] == ["channel", "lead_date"]
    assert metric["date_dimensions"] == ["lead_date"]
    # A count sums across periods, so a running total of it means something.
    assert metric["supports"] == {"compare": True, "accumulate": True}


def test_the_catalog_publishes_the_calendar_nesting_rule(client: TestClient) -> None:
    rules = {
        rule["grain"]: rule["resets"]
        for rule in client.get("/api/v1/catalog").json()["accumulation_resets"]
    }

    # A week straddles a month boundary, so weekly buckets cannot reset monthly.
    assert rules["week"] == ["year"]
    assert "month" in rules["day"]


def test_the_metrics_route_is_gone(client: TestClient) -> None:
    # It listed a subset of what the catalog publishes. One way to do one thing.
    assert client.get("/api/v1/metrics").status_code == 404
