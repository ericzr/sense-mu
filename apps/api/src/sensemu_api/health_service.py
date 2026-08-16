from datetime import UTC, datetime, timedelta

from botocore.exceptions import ClientError
from sqlalchemy import and_, func, or_, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from sensemu_api.config import Settings
from sensemu_api.db.models import Run, UsageReservation, WebhookDelivery
from sensemu_api.schemas import (
    OperationalIndicator,
    OperationalResponse,
    ReadinessDependency,
    ReadinessResponse,
)
from sensemu_api.storage import Storage


def _database_dependency(session: Session) -> ReadinessDependency:
    try:
        session.execute(text("SELECT 1"))
    except SQLAlchemyError:
        return ReadinessDependency(
            name="database",
            status="unavailable",
            detail="数据库连接不可用",
        )
    return ReadinessDependency(
        name="database",
        status="ready",
        detail="数据库查询正常",
    )


def _storage_dependency(storage: Storage) -> ReadinessDependency:
    try:
        storage.check_ready()
    except (ClientError, OSError, ValueError):
        return ReadinessDependency(
            name="object_storage",
            status="unavailable",
            detail="对象存储不可用",
        )
    return ReadinessDependency(
        name="object_storage",
        status="ready",
        detail="对象存储访问正常",
    )


def readiness(
    session: Session,
    storage: Storage,
    settings: Settings,
) -> ReadinessResponse:
    dependencies = [_database_dependency(session), _storage_dependency(storage)]
    is_ready = all(item.status == "ready" for item in dependencies)
    return ReadinessResponse(
        status="ready" if is_ready else "not_ready",
        service="sensemu-api",
        environment=settings.environment,
        dependencies=dependencies,
    )


def _count(session: Session, statement: object) -> int:
    return int(session.scalar(statement) or 0)  # type: ignore[arg-type]


def operational_health(
    session: Session,
    settings: Settings,
    *,
    now: datetime | None = None,
) -> OperationalResponse:
    observed_at = now or datetime.now(UTC)
    queue_cutoff = observed_at - timedelta(
        seconds=settings.operational_training_queue_alert_seconds
    )
    lease_cutoff = observed_at - timedelta(
        seconds=settings.training_execution_lease_timeout_seconds
    )
    webhook_cutoff = observed_at - timedelta(
        seconds=settings.operational_webhook_delivery_alert_seconds
    )
    reservation_cutoff = observed_at - timedelta(
        seconds=settings.inference_reservation_timeout_seconds
    )
    try:
        queued_runs = _count(
            session,
            select(func.count(Run.id)).where(
                Run.status == "queued",
                Run.created_at < queue_cutoff,
            ),
        )
        stale_training_leases = _count(
            session,
            select(func.count(Run.id)).where(
                Run.status.in_({"preparing", "running", "cancel_requested"}),
                or_(
                    Run.heartbeat_at < lease_cutoff,
                    and_(
                        Run.heartbeat_at.is_(None),
                        Run.claimed_at < lease_cutoff,
                    ),
                ),
            ),
        )
        unhealthy_webhook_deliveries = _count(
            session,
            select(func.count(WebhookDelivery.id)).where(
                or_(
                    WebhookDelivery.status == "failed",
                    and_(
                        WebhookDelivery.status.in_({"pending", "retrying"}),
                        WebhookDelivery.next_attempt_at < webhook_cutoff,
                    ),
                    and_(
                        WebhookDelivery.status == "delivering",
                        WebhookDelivery.claimed_at < lease_cutoff,
                    ),
                )
            ),
        )
        stale_reservations = _count(
            session,
            select(func.count(UsageReservation.id)).where(
                UsageReservation.status == "pending",
                UsageReservation.created_at < reservation_cutoff,
            ),
        )
    except SQLAlchemyError:
        return OperationalResponse(
            status="unavailable",
            service="sensemu-api",
            environment=settings.environment,
            generated_at=observed_at,
            indicators=[],
        )

    indicators = [
        OperationalIndicator(
            name="training_queue",
            status="attention" if queued_runs else "healthy",
            observed_count=queued_runs,
            threshold_seconds=settings.operational_training_queue_alert_seconds,
            detail="超过等待阈值的训练任务数",
        ),
        OperationalIndicator(
            name="stale_training_lease",
            status="attention" if stale_training_leases else "healthy",
            observed_count=stale_training_leases,
            threshold_seconds=settings.training_execution_lease_timeout_seconds,
            detail="超过执行租约阈值且未续期的训练任务数",
        ),
        OperationalIndicator(
            name="webhook_delivery",
            status="attention" if unhealthy_webhook_deliveries else "healthy",
            observed_count=unhealthy_webhook_deliveries,
            threshold_seconds=settings.operational_webhook_delivery_alert_seconds,
            detail="失败或超过投递阈值的 Webhook 数",
        ),
        OperationalIndicator(
            name="stale_usage_reservation",
            status="attention" if stale_reservations else "healthy",
            observed_count=stale_reservations,
            threshold_seconds=settings.inference_reservation_timeout_seconds,
            detail="超过额度预留阈值且尚未结算的请求数",
        ),
    ]
    return OperationalResponse(
        status="attention" if any(item.observed_count for item in indicators) else "healthy",
        service="sensemu-api",
        environment=settings.environment,
        generated_at=observed_at,
        indicators=indicators,
    )
