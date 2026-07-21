from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.detector import detect_anomalies
from app.models import EnergyReading
from app.schemas import (
    AnalysisRequest,
    AnalysisResponse,
    AnomalyResult,
    DeviceSummary,
    ReadingCreate,
    ReadingResponse,
)


class DuplicateReadingError(ValueError):
    pass


class InsufficientDataError(ValueError):
    pass


def create_readings(session: Session, readings: list[ReadingCreate]) -> list[EnergyReading]:
    entities = [EnergyReading(**reading.model_dump()) for reading in readings]
    session.add_all(entities)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise DuplicateReadingError(
            "A reading already exists for the same device and timestamp."
        ) from exc
    for entity in entities:
        session.refresh(entity)
    return entities


def list_readings(
    session: Session,
    device_id: str | None,
    start_at: datetime | None,
    end_at: datetime | None,
    limit: int,
) -> list[EnergyReading]:
    statement = select(EnergyReading)
    if device_id:
        statement = statement.where(EnergyReading.device_id == device_id.strip().lower())
    if start_at:
        statement = statement.where(EnergyReading.observed_at >= start_at)
    if end_at:
        statement = statement.where(EnergyReading.observed_at <= end_at)
    statement = statement.order_by(EnergyReading.observed_at.desc()).limit(limit)
    return list(session.scalars(statement))


def analyse_device(
    session: Session, request: AnalysisRequest, minimum_points: int
) -> AnalysisResponse:
    readings = list_readings(
        session,
        request.device_id,
        request.start_at,
        request.end_at,
        limit=10_000,
    )
    readings.reverse()
    if len(readings) < minimum_points:
        raise InsufficientDataError(
            f"At least {minimum_points} readings are required; received {len(readings)}."
        )

    detections = detect_anomalies(readings, request.contamination)
    anomalies = [
        AnomalyResult(
            reading=ReadingResponse.model_validate(item.reading),
            anomaly_score=item.score,
            reason=item.reason,
        )
        for item in detections
    ]
    return AnalysisResponse(
        device_id=request.device_id.strip().lower(),
        sample_size=len(readings),
        anomalies_found=len(anomalies),
        anomalies=anomalies,
    )


def device_summaries(session: Session) -> list[DeviceSummary]:
    statement = (
        select(
            EnergyReading.device_id,
            func.count(EnergyReading.id),
            func.sum(EnergyReading.energy_kwh),
            func.avg(EnergyReading.voltage),
            func.avg(EnergyReading.temperature_c),
        )
        .group_by(EnergyReading.device_id)
        .order_by(EnergyReading.device_id)
    )
    return [
        DeviceSummary(
            device_id=row[0],
            readings=row[1],
            total_energy_kwh=round(float(row[2]), 3),
            average_voltage=round(float(row[3]), 2),
            average_temperature_c=round(float(row[4]), 2),
        )
        for row in session.execute(statement)
    ]
