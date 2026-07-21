from contextlib import asynccontextmanager
from datetime import datetime
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import Base, engine, get_db
from app.schemas import (
    AnalysisRequest,
    AnalysisResponse,
    DeviceSummary,
    HealthResponse,
    ReadingBatch,
    ReadingResponse,
)
from app.service import (
    DuplicateReadingError,
    InsufficientDataError,
    analyse_device,
    create_readings,
    device_summaries,
    list_readings,
)

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    summary="Energy telemetry and anomaly detection API",
    description=(
        "Stores time-series energy readings and detects operational anomalies "
        "with a deterministic Isolation Forest model."
    ),
    lifespan=lifespan,
)

DbSession = Annotated[Session, Depends(get_db)]


@app.get("/health", response_model=HealthResponse, tags=["operations"])
def health(session: DbSession) -> HealthResponse:
    session.execute(text("SELECT 1"))
    return HealthResponse(status="ok", service=settings.app_name)


@app.post(
    "/api/v1/readings/batch",
    response_model=list[ReadingResponse],
    status_code=status.HTTP_201_CREATED,
    tags=["telemetry"],
)
def ingest_readings(payload: ReadingBatch, session: DbSession) -> list[ReadingResponse]:
    try:
        entities = create_readings(session, payload.readings)
    except DuplicateReadingError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return [ReadingResponse.model_validate(entity) for entity in entities]


@app.get("/api/v1/readings", response_model=list[ReadingResponse], tags=["telemetry"])
def get_readings(
    session: DbSession,
    device_id: str | None = None,
    start_at: datetime | None = None,
    end_at: datetime | None = None,
    limit: int = Query(default=200, ge=1, le=5_000),
) -> list[ReadingResponse]:
    return [
        ReadingResponse.model_validate(entity)
        for entity in list_readings(session, device_id, start_at, end_at, limit)
    ]


@app.post(
    "/api/v1/analysis/anomalies",
    response_model=AnalysisResponse,
    tags=["analytics"],
)
def analyse(payload: AnalysisRequest, session: DbSession) -> AnalysisResponse:
    try:
        return analyse_device(session, payload, settings.minimum_analysis_points)
    except InsufficientDataError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc


@app.get(
    "/api/v1/dashboard/devices",
    response_model=list[DeviceSummary],
    tags=["analytics"],
)
def dashboard(session: DbSession) -> list[DeviceSummary]:
    return device_summaries(session)
