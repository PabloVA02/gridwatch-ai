from dataclasses import dataclass

import numpy as np
from sklearn.ensemble import IsolationForest

from app.models import EnergyReading


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


def detect_anomalies(
    readings: list[EnergyReading], contamination: float = 0.1
) -> list[Detection]:
    if not readings:
        return []

    matrix = _feature_matrix(readings)
    model = IsolationForest(
        n_estimators=250,
        contamination=contamination,
        random_state=42,
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
