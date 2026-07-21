from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.detector import (
    DETECTOR_NAME,
    DETECTOR_VERSION,
    FEATURE_SCHEMA_VERSION,
    MODEL_PARAMETERS,
    analysis_fingerprint,
    detect_anomalies,
)
from app.models import AnalysisRun, EnergyReading
from app.monitoring import (
    DRIFT_PSI,
    MINIMUM_PSI_SAMPLE_SIZE,
    WARNING_PSI,
    measure_drift,
    measure_quality,
)
from app.schemas import (
    AnalysisRequest,
    AnalysisResponse,
    AnalysisRunResponse,
    AnomalyResult,
    DeviceSummary,
    DriftRequest,
    DriftResponse,
    FeatureDrift,
    ReadingCreate,
    ReadingResponse,
    WindowQuality,
)


class DuplicateReadingError(ValueError):
    pass


class InsufficientDataError(ValueError):
    pass


class MonitoringWindowError(ValueError):
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
    run = AnalysisRun(
        run_id=str(uuid4()),
        device_id=request.device_id.strip().lower(),
        detector_name=DETECTOR_NAME,
        detector_version=DETECTOR_VERSION,
        detector_parameters={**MODEL_PARAMETERS, "contamination": request.contamination},
        feature_schema_version=FEATURE_SCHEMA_VERSION,
        dataset_fingerprint=analysis_fingerprint(readings, request.contamination),
        sample_size=len(readings),
        contamination=request.contamination,
        anomalies_found=len(anomalies),
    )
    session.add(run)
    session.commit()
    session.refresh(run)
    return AnalysisResponse(
        device_id=request.device_id.strip().lower(),
        sample_size=len(readings),
        anomalies_found=len(anomalies),
        anomalies=anomalies,
        run=AnalysisRunResponse.model_validate(run),
    )


def get_analysis_run(session: Session, run_id: UUID) -> AnalysisRun | None:
    statement = select(AnalysisRun).where(AnalysisRun.run_id == str(run_id))
    return session.scalar(statement)


def _window_readings(
    session: Session,
    device_id: str,
    start_at: datetime,
    end_at: datetime,
    maximum_points: int,
) -> list[EnergyReading]:
    statement = (
        select(EnergyReading)
        .where(
            EnergyReading.device_id == device_id,
            EnergyReading.observed_at >= start_at,
            EnergyReading.observed_at < end_at,
        )
        .order_by(EnergyReading.observed_at)
        .limit(maximum_points + 1)
    )
    readings = list(session.scalars(statement))
    if len(readings) > maximum_points:
        raise MonitoringWindowError(f"A monitoring window cannot exceed {maximum_points} readings.")
    return readings


def monitor_device(
    session: Session,
    request: DriftRequest,
    minimum_points: int,
    maximum_points: int,
) -> DriftResponse:
    required_points = max(minimum_points, MINIMUM_PSI_SAMPLE_SIZE)
    reference = _window_readings(
        session,
        request.device_id,
        request.reference_start_at,
        request.reference_end_at,
        maximum_points,
    )
    current = _window_readings(
        session,
        request.device_id,
        request.current_start_at,
        request.current_end_at,
        maximum_points,
    )
    if len(reference) < required_points or len(current) < required_points:
        raise MonitoringWindowError(
            f"Each window requires at least {required_points} readings; "
            f"received {len(reference)} reference and {len(current)} current readings."
        )

    measurements = measure_drift(reference, current)
    reference_quality = measure_quality(
        reference,
        request.reference_start_at,
        request.reference_end_at,
        request.expected_interval_minutes,
    )
    current_quality = measure_quality(
        current,
        request.current_start_at,
        request.current_end_at,
        request.expected_interval_minutes,
    )
    highest_psi = max(item.psi for item in measurements)
    overall_status = (
        "drift"
        if highest_psi >= DRIFT_PSI
        else "warning"
        if highest_psi >= WARNING_PSI
        else "stable"
    )
    return DriftResponse(
        device_id=request.device_id,
        overall_status=overall_status,
        reference_quality=WindowQuality(**reference_quality.__dict__),
        current_quality=WindowQuality(**current_quality.__dict__),
        features=[FeatureDrift(**item.__dict__) for item in measurements],
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
