from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient


def _readings(count: int = 20) -> list[dict]:
    start = datetime(2026, 7, 1, tzinfo=UTC)
    readings = []
    for index in range(count):
        readings.append(
            {
                "device_id": "factory-line-a",
                "observed_at": (start + timedelta(hours=index)).isoformat(),
                "energy_kwh": 180.0 if index == 13 else 42.0 + (index % 3),
                "voltage": 230.0 + (index % 2),
                "temperature_c": 72.0 if index == 13 else 24.0 + (index % 2),
            }
        )
    return readings


def test_full_ingestion_and_analysis_flow(client: TestClient) -> None:
    ingest = client.post("/api/v1/readings/batch", json={"readings": _readings()})
    assert ingest.status_code == 201
    assert len(ingest.json()) == 20

    analysis = client.post(
        "/api/v1/analysis/anomalies",
        json={"device_id": "factory-line-a", "contamination": 0.1},
    )
    assert analysis.status_code == 200
    body = analysis.json()
    assert body["sample_size"] == 20
    assert body["anomalies_found"] == 2
    assert any(result["reading"]["energy_kwh"] == 180.0 for result in body["anomalies"])

    dashboard = client.get("/api/v1/dashboard/devices")
    assert dashboard.status_code == 200
    assert dashboard.json()[0]["readings"] == 20


def test_duplicate_reading_returns_conflict(client: TestClient) -> None:
    payload = {"readings": _readings(1)}
    assert client.post("/api/v1/readings/batch", json=payload).status_code == 201
    duplicate = client.post("/api/v1/readings/batch", json=payload)
    assert duplicate.status_code == 409


def test_analysis_requires_enough_data(client: TestClient) -> None:
    client.post("/api/v1/readings/batch", json={"readings": _readings(5)})
    response = client.post(
        "/api/v1/analysis/anomalies", json={"device_id": "factory-line-a"}
    )
    assert response.status_code == 422
    assert "At least 12" in response.json()["detail"]


def test_health_checks_database(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
