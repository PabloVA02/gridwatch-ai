from dataclasses import dataclass
from datetime import datetime
from math import ceil

import numpy as np

from app.models import EnergyReading

WARNING_PSI = 0.10
DRIFT_PSI = 0.25
MINIMUM_PSI_SAMPLE_SIZE = 300


@dataclass(frozen=True)
class FeatureDriftMeasurement:
    feature: str
    psi: float
    status: str
    reference_mean: float
    current_mean: float


@dataclass(frozen=True)
class QualityMeasurement:
    observed_points: int
    expected_points: int
    covered_intervals: int
    completeness_ratio: float
    leading_missing_intervals: int
    internal_missing_intervals: int
    trailing_missing_intervals: int
    max_gap_minutes: float


def _status_for_psi(psi: float) -> str:
    if psi >= DRIFT_PSI:
        return "drift"
    if psi >= WARNING_PSI:
        return "warning"
    return "stable"


def population_stability_index(reference: np.ndarray, current: np.ndarray) -> float:
    """Compare distributions using reference-derived quantile buckets."""
    if reference.size < MINIMUM_PSI_SAMPLE_SIZE or current.size < MINIMUM_PSI_SAMPLE_SIZE:
        raise ValueError(f"PSI requires at least {MINIMUM_PSI_SAMPLE_SIZE} values in each sample.")

    quantiles = np.quantile(reference, np.linspace(0.0, 1.0, 6))[1:-1]
    internal_edges = np.unique(quantiles)
    if internal_edges.size < 2:
        centre = float(np.mean(reference))
        tolerance = max(abs(centre) * 0.01, 1e-6)
        internal_edges = np.array([centre - tolerance, centre + tolerance])

    edges = np.concatenate(([-np.inf], internal_edges, [np.inf]))
    reference_counts, _ = np.histogram(reference, bins=edges)
    current_counts, _ = np.histogram(current, bins=edges)

    pseudocount = 0.5
    reference_share = (reference_counts + pseudocount) / (
        reference_counts.sum() + pseudocount * reference_counts.size
    )
    current_share = (current_counts + pseudocount) / (
        current_counts.sum() + pseudocount * current_counts.size
    )
    psi = np.sum((current_share - reference_share) * np.log(current_share / reference_share))
    return round(float(psi), 6)


def _feature_values(readings: list[EnergyReading]) -> dict[str, np.ndarray]:
    energy = np.array([item.energy_kwh for item in readings], dtype=float)
    return {
        "energy_kwh": energy,
        "voltage": np.array([item.voltage for item in readings], dtype=float),
        "temperature_c": np.array([item.temperature_c for item in readings], dtype=float),
        "energy_delta_kwh": np.abs(np.diff(energy, prepend=energy[0])),
    }


def measure_drift(
    reference: list[EnergyReading], current: list[EnergyReading]
) -> list[FeatureDriftMeasurement]:
    reference_features = _feature_values(reference)
    current_features = _feature_values(current)
    measurements = []
    for feature, reference_values in reference_features.items():
        current_values = current_features[feature]
        psi = population_stability_index(reference_values, current_values)
        measurements.append(
            FeatureDriftMeasurement(
                feature=feature,
                psi=psi,
                status=_status_for_psi(psi),
                reference_mean=round(float(reference_values.mean()), 4),
                current_mean=round(float(current_values.mean()), 4),
            )
        )
    return measurements


def measure_quality(
    readings: list[EnergyReading],
    start_at: datetime,
    end_at: datetime,
    expected_interval_minutes: int,
) -> QualityMeasurement:
    expected_points = max(
        1, ceil((end_at - start_at).total_seconds() / (expected_interval_minutes * 60))
    )
    timestamps = sorted(
        item.observed_at for item in readings if start_at <= item.observed_at < end_at
    )
    interval_seconds = expected_interval_minutes * 60
    occupied_intervals = sorted(
        {
            min(
                int((timestamp - start_at).total_seconds() // interval_seconds),
                expected_points - 1,
            )
            for timestamp in timestamps
            if start_at <= timestamp < end_at
        }
    )
    internal_gaps_minutes = [
        (current - previous).total_seconds() / 60
        for previous, current in zip(timestamps, timestamps[1:], strict=False)
    ]
    boundary_gaps_minutes = (
        [
            (timestamps[0] - start_at).total_seconds() / 60,
            (end_at - timestamps[-1]).total_seconds() / 60,
        ]
        if timestamps
        else [(end_at - start_at).total_seconds() / 60]
    )
    leading_missing = occupied_intervals[0] if occupied_intervals else expected_points
    trailing_missing = expected_points - occupied_intervals[-1] - 1 if occupied_intervals else 0
    internal_missing = sum(
        max(current - previous - 1, 0)
        for previous, current in zip(occupied_intervals, occupied_intervals[1:], strict=False)
    )
    covered_intervals = len(occupied_intervals)
    return QualityMeasurement(
        observed_points=len(readings),
        expected_points=expected_points,
        covered_intervals=covered_intervals,
        completeness_ratio=round(covered_intervals / expected_points, 4),
        leading_missing_intervals=leading_missing,
        internal_missing_intervals=internal_missing,
        trailing_missing_intervals=trailing_missing,
        max_gap_minutes=round(max(internal_gaps_minutes + boundary_gaps_minutes), 2),
    )
