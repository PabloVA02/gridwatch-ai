from datetime import UTC, datetime

from sqlalchemy import JSON, Float, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, UTCDateTime


class EnergyReading(Base):
    __tablename__ = "energy_readings"
    __table_args__ = (
        UniqueConstraint("device_id", "observed_at", name="uq_reading_device_time"),
        Index("ix_reading_device_time", "device_id", "observed_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    device_id: Mapped[str] = mapped_column(String(80), index=True)
    observed_at: Mapped[datetime] = mapped_column(UTCDateTime())
    energy_kwh: Mapped[float] = mapped_column(Float)
    voltage: Mapped[float] = mapped_column(Float)
    temperature_c: Mapped[float] = mapped_column(Float)


class AnalysisRun(Base):
    __tablename__ = "analysis_runs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(36), unique=True, index=True)
    device_id: Mapped[str] = mapped_column(String(80), index=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=lambda: datetime.now(UTC))
    detector_name: Mapped[str] = mapped_column(String(80))
    detector_version: Mapped[str] = mapped_column(String(30))
    detector_parameters: Mapped[dict[str, int | float]] = mapped_column(JSON)
    feature_schema_version: Mapped[str] = mapped_column(String(50))
    dataset_fingerprint: Mapped[str] = mapped_column(String(64), index=True)
    sample_size: Mapped[int]
    contamination: Mapped[float] = mapped_column(Float)
    anomalies_found: Mapped[int]
