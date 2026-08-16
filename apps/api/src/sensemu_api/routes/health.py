from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from sensemu_api.config import get_settings
from sensemu_api.db.session import get_session
from sensemu_api.health_service import operational_health, readiness
from sensemu_api.schemas import HealthResponse, OperationalResponse, ReadinessResponse
from sensemu_api.storage import Storage, get_storage

router = APIRouter(tags=["system"])
SessionDep = Annotated[Session, Depends(get_session)]
StorageDep = Annotated[Storage, Depends(get_storage)]


@router.get("/health/live", response_model=HealthResponse)
def live() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(service="sensemu-api", environment=settings.environment)


@router.get(
    "/health/ready",
    response_model=ReadinessResponse,
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ReadinessResponse}},
)
def ready(
    response: Response,
    session: SessionDep,
    storage: StorageDep,
) -> ReadinessResponse:
    settings = get_settings()
    report = readiness(session, storage, settings)
    if report.status != "ready":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return report


@router.get(
    "/health/operational",
    response_model=OperationalResponse,
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": OperationalResponse}},
)
def operational(
    response: Response,
    session: SessionDep,
) -> OperationalResponse:
    report = operational_health(session, get_settings())
    if report.status == "unavailable":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return report
