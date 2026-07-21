from datetime import UTC, datetime, timedelta

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.models import EnergyReading
from app.monitoring import MINIMUM_PSI_SAMPLE_SIZE, measure_quality, population_stability_index


def _monitoring_readings() -> list[dict]:
    start = datetime(2026, 7, 1, tzinfo=UTC)
    readings = []
    for index in range(640):
        if index == 355:
            continue
        shifted = index >= 320
        readings.append(
            {
                "device_id": "factory-line-a",
                "observed_at": (start + timedelta(hours=index)).isoformat(),
                "energy_kwh": (85.0 if shifted else 42.0) + (index % 3),
                "voltage": (238.0 if shifted else 230.0) + (index % 2),
                "temperature_c": (39.0 if shifted else 24.0) + (index % 2),
            }
        )
    return readings


def _monitoring_request() -> dict:
    start = datetime(2026, 7, 1, tzinfo=UTC)
    return {
        "device_id": " Factory-Line-A ",
        "reference_start_at": start.isoformat(),
        "reference_end_at": (start + timedelta(hours=320)).isoformat(),
        "current_start_at": (start + timedelta(hours=320)).isoformat(),
        "current_end_at": (start + timedelta(hours=640)).isoformat(),
        "expected_interval_minutes": 60,
    }


def test_monitoring_detects_drift_and_reports_data_gaps(client: TestClient) -> None:
    ingest = client.post("/api/v1/readings/batch", json={"readings": _monitoring_readings()})
    assert ingest.status_code == 201

    response = client.post("/api/v1/monitoring/drift", json=_monitoring_request())
    assert response.status_code == 200
    body = response.json()
    assert body["device_id"] == "factory-line-a"
    assert body["overall_status"] == "drift"
    assert body["reference_quality"]["completeness_ratio"] == 1.0
    assert body["current_quality"]["covered_intervals"] == 319
    assert body["current_quality"]["completeness_ratio"] == pytest.approx(319 / 320, abs=1e-4)
    assert body["current_quality"]["internal_missing_intervals"] == 1
    assert body["current_quality"]["max_gap_minutes"] == 120.0

    feature_results = {item["feature"]: item for item in body["features"]}
    assert feature_results["energy_kwh"]["status"] == "drift"
    assert feature_results["energy_kwh"]["current_mean"] > 80
    assert feature_results["temperature_c"]["status"] == "drift"


def test_monitoring_rejects_short_or_overlapping_windows(client: TestClient) -> None:
    client.post(
        "/api/v1/readings/batch",
        json={"readings": _monitoring_readings()[:5]},
    )
    short_window = client.post("/api/v1/monitoring/drift", json=_monitoring_request())
    assert short_window.status_code == 422
    assert "Each window requires at least 300" in short_window.json()["detail"]

    overlapping = _monitoring_request()
    overlapping["current_start_at"] = "2026-07-01T12:00:00Z"
    response = client.post("/api/v1/monitoring/drift", json=overlapping)
    assert response.status_code == 422
    assert "must not overlap" in response.text

    mixed_timezone = _monitoring_request()
    mixed_timezone["reference_start_at"] = "2026-07-01T00:00:00"
    response = client.post("/api/v1/monitoring/drift", json=mixed_timezone)
    assert response.status_code == 422
    assert "timezone offset" in response.text

    blank_device = _monitoring_request()
    blank_device["device_id"] = "   "
    response = client.post("/api/v1/monitoring/drift", json=blank_device)
    assert response.status_code == 422
    assert "non-whitespace" in response.text


def test_population_stability_index_handles_stable_constant_and_small_samples() -> None:
    reference = np.array([42.0] * MINIMUM_PSI_SAMPLE_SIZE)
    assert population_stability_index(reference, reference.copy()) == 0.0
    shifted = np.array([80.0] * MINIMUM_PSI_SAMPLE_SIZE)
    assert population_stability_index(reference, shifted) > 0.25
    with pytest.raises(ValueError, match="at least 300"):
        population_stability_index(np.array([]), reference)


def test_psi_stable_distribution_has_low_false_warning_rate() -> None:
    rng = np.random.default_rng(20260721)
    false_warnings = 0
    simulations = 250
    for _ in range(simulations):
        reference = rng.normal(size=MINIMUM_PSI_SAMPLE_SIZE)
        current = rng.normal(size=MINIMUM_PSI_SAMPLE_SIZE)
        false_warnings += population_stability_index(reference, current) >= 0.10
    assert false_warnings / simulations <= 0.05


def test_quality_measurement_reports_an_internal_gap() -> None:
    start = datetime(2026, 7, 1, tzinfo=UTC)
    readings = [
        EnergyReading(
            id=index + 1,
            device_id="pump-a",
            observed_at=start + timedelta(hours=index),
            energy_kwh=42.0,
            voltage=230.0,
            temperature_c=24.0,
        )
        for index in (0, 1, 3)
    ]
    quality = measure_quality(readings, start, start + timedelta(hours=4), 60)
    assert quality.observed_points == 3
    assert quality.expected_points == 4
    assert quality.covered_intervals == 3
    assert quality.completeness_ratio == 0.75
    assert quality.leading_missing_intervals == 0
    assert quality.internal_missing_intervals == 1
    assert quality.trailing_missing_intervals == 0
    assert quality.max_gap_minutes == 120.0


def test_quality_does_not_treat_concentrated_readings_as_full_coverage() -> None:
    start = datetime(2026, 7, 1, tzinfo=UTC)
    readings = [
        EnergyReading(
            id=index + 1,
            device_id="pump-a",
            observed_at=start + timedelta(minutes=index),
            energy_kwh=42.0,
            voltage=230.0,
            temperature_c=24.0,
        )
        for index in range(24)
    ]
    quality = measure_quality(readings, start, start + timedelta(hours=24), 60)
    assert quality.observed_points == 24
    assert quality.covered_intervals == 1
    assert quality.completeness_ratio == pytest.approx(1 / 24, abs=1e-4)
    assert quality.leading_missing_intervals == 0
    assert quality.trailing_missing_intervals == 23
    assert quality.max_gap_minutes == 24 * 60 - 23


def test_quality_maximum_gap_includes_window_boundaries() -> None:
    start = datetime(2026, 7, 1, tzinfo=UTC)
    readings = [
        EnergyReading(
            id=index + 1,
            device_id="pump-a",
            observed_at=start + timedelta(hours=index),
            energy_kwh=42.0,
            voltage=230.0,
            temperature_c=24.0,
        )
        for index in (2, 3)
    ]
    quality = measure_quality(readings, start, start + timedelta(hours=6), 60)
    assert quality.leading_missing_intervals == 2
    assert quality.trailing_missing_intervals == 2
    assert quality.max_gap_minutes == 180.0
