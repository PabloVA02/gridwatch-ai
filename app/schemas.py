from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ReadingCreate(BaseModel):
    device_id: str = Field(min_length=2, max_length=80, examples=["factory-line-a"])
    observed_at: datetime
    energy_kwh: float = Field(ge=0, le=1_000_000)
    voltage: float = Field(gt=0, le=1_000)
    temperature_c: float = Field(ge=-80, le=200)

    @field_validator("device_id")
    @classmethod
    def normalize_device_id(cls, value: str) -> str:
        return value.strip().lower()


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


class AnomalyResult(BaseModel):
    reading: ReadingResponse
    anomaly_score: float
    reason: str


class AnalysisResponse(BaseModel):
    device_id: str
    sample_size: int
    anomalies_found: int
    anomalies: list[AnomalyResult]


class DeviceSummary(BaseModel):
    device_id: str
    readings: int
    total_energy_kwh: float
    average_voltage: float
    average_temperature_c: float


class HealthResponse(BaseModel):
    status: str
    service: str
