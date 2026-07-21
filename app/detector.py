import json
from dataclasses import dataclass
from hashlib import sha256

import numpy as np
from sklearn.ensemble import IsolationForest

from app.models import EnergyReading

DETECTOR_NAME = "IsolationForest"
DETECTOR_VERSION = "1.1.0"
FEATURE_SCHEMA_VERSION = "energy-telemetry-v1"
FEATURE_NAMES = (
    "energy_kwh",
    "voltage",
    "temperature_c",
    "energy_delta_kwh",
    "hour_sin",
    "hour_cos",
)
MODEL_PARAMETERS = {
    "n_estimators": 250,
    "random_state": 42,
}


@dataclass(frozen=True)
class Detection:
    reading: EnergyReading
    score: float
    reason: str


def _feature_matrix(readings: list[EnergyReading]) -> np.ndarray:
    energy = np.array([item.energy_kwh for item in readings], dtype=float)
    delta = np.abs(np.diff(energy, prepend=energy[0]))
    hour = np.array([item.observed_at.hour for item in readings], dtype=float)

    return np.column_stack(
        [
            energy,
            np.array([item.voltage for item in readings], dtype=float),
            np.array([item.temperature_c for item in readings], dtype=float),
            delta,
            np.sin(2 * np.pi * hour / 24),
            np.cos(2 * np.pi * hour / 24),
        ]
    )


def _explain(reading: EnergyReading, readings: list[EnergyReading]) -> str:
    energy_values = np.array([item.energy_kwh for item in readings], dtype=float)
    voltage_values = np.array([item.voltage for item in readings], dtype=float)
    temperature_values = np.array([item.temperature_c for item in readings], dtype=float)

    deviations = {
        "energy consumption": abs(reading.energy_kwh - energy_values.mean())
        / max(energy_values.std(), 1e-6),
        "voltage": abs(reading.voltage - voltage_values.mean()) / max(voltage_values.std(), 1e-6),
        "temperature": abs(reading.temperature_c - temperature_values.mean())
        / max(temperature_values.std(), 1e-6),
    }
    dominant_feature = max(deviations, key=deviations.get)
    return f"Unusual {dominant_feature} compared with this device's selected time window."


def detect_anomalies(readings: list[EnergyReading], contamination: float = 0.1) -> list[Detection]:
    if not readings:
        return []

    matrix = _feature_matrix(readings)
    model = IsolationForest(
        n_estimators=MODEL_PARAMETERS["n_estimators"],
        contamination=contamination,
        random_state=MODEL_PARAMETERS["random_state"],
        n_jobs=-1,
    )
    labels = model.fit_predict(matrix)
    scores = -model.decision_function(matrix)

    detections = [
        Detection(reading=item, score=round(float(score), 6), reason=_explain(item, readings))
        for item, label, score in zip(readings, labels, scores, strict=True)
        if label == -1
    ]
    return sorted(detections, key=lambda result: result.score, reverse=True)


def analysis_fingerprint(readings: list[EnergyReading], contamination: float) -> str:
    """Return a reproducible fingerprint for the data and detector configuration."""
    payload = {
        "detector": DETECTOR_NAME,
        "detector_version": DETECTOR_VERSION,
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "features": FEATURE_NAMES,
        "parameters": {**MODEL_PARAMETERS, "contamination": contamination},
        "readings": [
            {
                "device_id": item.device_id,
                "observed_at": item.observed_at.isoformat(),
                "energy_kwh": item.energy_kwh,
                "voltage": item.voltage,
                "temperature_c": item.temperature_c,
            }
            for item in readings
        ],
    }
    canonical_payload = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return sha256(canonical_payload.encode()).hexdigest()
