from datetime import UTC, datetime, timedelta

from app.detector import detect_anomalies
from app.models import EnergyReading


def test_detector_is_deterministic_and_finds_large_spike() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    readings = [
        EnergyReading(
            id=index + 1,
            device_id="pump-a",
            observed_at=start + timedelta(hours=index),
            energy_kwh=250.0 if index == 16 else 50.0 + (index % 4),
            voltage=230.0,
            temperature_c=80.0 if index == 16 else 25.0,
        )
        for index in range(24)
    ]

    first = detect_anomalies(readings, contamination=0.08)
    second = detect_anomalies(readings, contamination=0.08)

    assert [item.reading.id for item in first] == [item.reading.id for item in second]
    assert any(item.reading.energy_kwh == 250.0 for item in first)
    assert all(item.reason for item in first)
