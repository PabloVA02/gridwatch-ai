from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def normalize_device_id(value: str) -> str:
    normalized = value.strip().lower()
    if len(normalized) < 2:
        raise ValueError("Device ID must contain at least 2 non-whitespace characters.")
    return normalized


def normalize_utc_datetime(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Datetime values must include a timezone offset.")
    return value.astimezone(UTC)


class ReadingCreate(BaseModel):
    device_id: str = Field(min_length=2, max_length=80, examples=["factory-line-a"])
    observed_at: datetime
    energy_kwh: float = Field(ge=0, le=1_000_000)
    voltage: float = Field(gt=0, le=1_000)
    temperature_c: float = Field(ge=-80, le=200)

    @field_validator("device_id")
    @classmethod
    def normalize_device_id(cls, value: str) -> str:
        return normalize_device_id(value)

    @field_validator("observed_at")
    @classmethod
    def normalize_observed_at(cls, value: datetime) -> datetime:
        return normalize_utc_datetime(value)


class ReadingBatch(BaseModel):
    readings: list[ReadingCreate] = Field(min_length=1, max_length=5_000)


class ReadingResponse(ReadingCreate):
    id: int
    model_config = ConfigDict(from_attributes=True)


class AnalysisRequest(BaseModel):
    device_id: str = Field(min_length=2, max_length=80)
    start_at: datetime | None = None
    end_at: datetime | None = None
    contamination: float = Field(default=0.1, gt=0, le=0.35)

    @field_validator("device_id")
    @classmethod
    def normalize_device_id(cls, value: str) -> str:
        return normalize_device_id(value)

    @field_validator("start_at", "end_at")
    @classmethod
    def normalize_window_time(cls, value: datetime | None) -> datetime | None:
        return normalize_utc_datetime(value) if value is not None else None

    @model_validator(mode="after")
    def validate_window(self) -> "AnalysisRequest":
        if self.start_at is not None and self.end_at is not None and self.start_at >= self.end_at:
            raise ValueError("The analysis window start must be before its end.")
        return self


class AnomalyResult(BaseModel):
    reading: ReadingResponse
    anomaly_score: float
    reason: str


class AnalysisRunResponse(BaseModel):
    run_id: str
    device_id: str
    created_at: datetime
    detector_name: str
    detector_version: str
    detector_parameters: dict[str, int | float]
    feature_schema_version: str
    dataset_fingerprint: str
    sample_size: int
    contamination: float
    anomalies_found: int

    model_config = ConfigDict(from_attributes=True)


class AnalysisResponse(BaseModel):
    device_id: str
    sample_size: int
    anomalies_found: int
    anomalies: list[AnomalyResult]
    run: AnalysisRunResponse


class DriftRequest(BaseModel):
    device_id: str = Field(min_length=2, max_length=80)
    reference_start_at: datetime
    reference_end_at: datetime
    current_start_at: datetime
    current_end_at: datetime
    expected_interval_minutes: int = Field(default=60, ge=1, le=1_440)

    @field_validator("device_id")
    @classmethod
    def normalize_device_id(cls, value: str) -> str:
        return normalize_device_id(value)

    @field_validator("reference_start_at", "reference_end_at", "current_start_at", "current_end_at")
    @classmethod
    def normalize_window_time(cls, value: datetime) -> datetime:
        return normalize_utc_datetime(value)

    @model_validator(mode="after")
    def validate_windows(self) -> "DriftRequest":
        if self.reference_start_at >= self.reference_end_at:
            raise ValueError("The reference window start must be before its end.")
        if self.current_start_at >= self.current_end_at:
            raise ValueError("The current window start must be before its end.")
        windows_overlap = (
            self.reference_start_at < self.current_end_at
            and self.current_start_at < self.reference_end_at
        )
        if windows_overlap:
            raise ValueError("Reference and current windows must not overlap.")
        return self


class FeatureDrift(BaseModel):
    feature: str
    psi: float
    status: Literal["stable", "warning", "drift"]
    reference_mean: float
    current_mean: float


class WindowQuality(BaseModel):
    observed_points: int
    expected_points: int
    covered_intervals: int
    completeness_ratio: float
    leading_missing_intervals: int
    internal_missing_intervals: int
    trailing_missing_intervals: int
    max_gap_minutes: float


class DriftResponse(BaseModel):
    device_id: str
    overall_status: Literal["stable", "warning", "drift"]
    reference_quality: WindowQuality
    current_quality: WindowQuality
    features: list[FeatureDrift]


class DeviceSummary(BaseModel):
    device_id: str
    readings: int
    total_energy_kwh: float
    average_voltage: float
    average_temperature_c: float


class HealthResponse(BaseModel):
    status: str
    service: str
