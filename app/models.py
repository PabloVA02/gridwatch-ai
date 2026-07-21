from datetime import datetime

from sqlalchemy import DateTime, Float, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class EnergyReading(Base):
    __tablename__ = "energy_readings"
    __table_args__ = (
        UniqueConstraint("device_id", "observed_at", name="uq_reading_device_time"),
        Index("ix_reading_device_time", "device_id", "observed_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    device_id: Mapped[str] = mapped_column(String(80), index=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    energy_kwh: Mapped[float] = mapped_column(Float)
    voltage: Mapped[float] = mapped_column(Float)
    temperature_c: Mapped[float] = mapped_column(Float)
