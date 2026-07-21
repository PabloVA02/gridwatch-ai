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
    assert body["run"]["detector_version"] == "1.1.0"
    assert body["run"]["detector_parameters"] == {
        "n_estimators": 250,
        "random_state": 42,
        "contamination": 0.1,
    }
    assert body["run"]["feature_schema_version"] == "energy-telemetry-v1"
    assert len(body["run"]["dataset_fingerprint"]) == 64

    recorded_run = client.get(f"/api/v1/analysis/runs/{body['run']['run_id']}")
    assert recorded_run.status_code == 200
    assert recorded_run.json()["dataset_fingerprint"] == body["run"]["dataset_fingerprint"]

    repeated_analysis = client.post(
        "/api/v1/analysis/anomalies",
        json={"device_id": "factory-line-a", "contamination": 0.1},
    )
    assert repeated_analysis.status_code == 200
    assert repeated_analysis.json()["run"]["run_id"] != body["run"]["run_id"]
    assert (
        repeated_analysis.json()["run"]["dataset_fingerprint"] == body["run"]["dataset_fingerprint"]
    )

    dashboard = client.get("/api/v1/dashboard/devices")
    assert dashboard.status_code == 200
    assert dashboard.json()[0]["readings"] == 20


def test_duplicate_reading_returns_conflict(client: TestClient) -> None:
    payload = {"readings": _readings(1)}
    assert client.post("/api/v1/readings/batch", json=payload).status_code == 201
    duplicate = client.post("/api/v1/readings/batch", json=payload)
    assert duplicate.status_code == 409


def test_equivalent_timezone_instants_are_normalized_before_deduplication(
    client: TestClient,
) -> None:
    first = _readings(1)[0]
    equivalent = {**first, "observed_at": "2026-07-01T02:00:00+02:00"}
    response = client.post("/api/v1/readings/batch", json={"readings": [first]})
    assert response.status_code == 201
    assert response.json()[0]["observed_at"].endswith("Z")
    duplicate = client.post("/api/v1/readings/batch", json={"readings": [equivalent]})
    assert duplicate.status_code == 409


def test_naive_timestamps_and_blank_device_ids_are_validation_errors(
    client: TestClient,
) -> None:
    invalid_reading = {
        **_readings(1)[0],
        "device_id": "   ",
        "observed_at": "2026-07-01T00:00:00",
    }
    response = client.post("/api/v1/readings/batch", json={"readings": [invalid_reading]})
    assert response.status_code == 422
    assert "non-whitespace" in response.text
    assert "timezone offset" in response.text

    analysis = client.post(
        "/api/v1/analysis/anomalies",
        json={"device_id": "  ", "start_at": "2026-07-01T00:00:00"},
    )
    assert analysis.status_code == 422


def test_naive_query_timestamp_returns_validation_error(client: TestClient) -> None:
    response = client.get("/api/v1/readings?start_at=2026-07-01T00:00:00")
    assert response.status_code == 422
    assert "timezone offset" in response.text


def test_analysis_requires_enough_data(client: TestClient) -> None:
    client.post("/api/v1/readings/batch", json={"readings": _readings(5)})
    response = client.post("/api/v1/analysis/anomalies", json={"device_id": "factory-line-a"})
    assert response.status_code == 422
    assert "At least 12" in response.json()["detail"]


def test_health_checks_database(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_unknown_analysis_run_returns_not_found(client: TestClient) -> None:
    response = client.get("/api/v1/analysis/runs/35c17c20-2c9a-4c14-93bf-b94b0366428e")
    assert response.status_code == 404
