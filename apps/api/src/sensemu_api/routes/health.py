from collections.abc import Iterator
from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from redis import Redis
from sqlalchemy.orm import Session

from sensemu_api.config import get_settings
from sensemu_api.db.session import get_session
from sensemu_api.health_service import operational_health, readiness
from sensemu_api.schemas import HealthResponse, OperationalResponse, ReadinessResponse
from sensemu_api.storage import Storage, get_storage

router = APIRouter(tags=["system"])
SessionDep = Annotated[Session, Depends(get_session)]
StorageDep = Annotated[Storage, Depends(get_storage)]


def get_redis_client() -> Iterator[Redis]:
    settings = get_settings()
    client = Redis.from_url(
        settings.redis_url,
        socket_connect_timeout=2,
        socket_timeout=2,
    )
    try:
        yield client
    finally:
        client.close()


RedisDep = Annotated[Redis, Depends(get_redis_client)]


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
    redis_client: RedisDep,
) -> ReadinessResponse:
    settings = get_settings()
    report = readiness(session, storage, redis_client, settings)
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
