from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from sensemu_api.db import Base
from sensemu_api.db.models import Run, UsageReservation, WebhookDelivery
from sensemu_api.db.session import get_session
from sensemu_api.main import app, create_app
from sensemu_api.storage import get_storage

client = TestClient(app)


def test_live_health() -> None:
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json()["service"] == "sensemu-api"


class ReadyStorage:
    def check_ready(self) -> None:
        return None


class UnavailableStorage:
    def check_ready(self) -> None:
        raise OSError("storage unavailable")


def _readiness_client(storage: object) -> TestClient:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    testing_session = sessionmaker(bind=engine, expire_on_commit=False)
    Base.metadata.create_all(engine)

    def override_session() -> Iterator[Session]:
        with testing_session() as session:
            yield session

    application = create_app()
    application.dependency_overrides[get_session] = override_session
    application.dependency_overrides[get_storage] = lambda: storage
    return TestClient(application)


def test_readiness_reports_database_and_object_storage() -> None:
    response = _readiness_client(ReadyStorage()).get("/health/ready")

    assert response.status_code == 200
    assert response.json()["status"] == "ready"
    assert response.json()["dependencies"] == [
        {"name": "database", "status": "ready", "detail": "数据库查询正常"},
        {"name": "object_storage", "status": "ready", "detail": "对象存储访问正常"},
    ]


def test_readiness_fails_closed_when_object_storage_is_unavailable() -> None:
    response = _readiness_client(UnavailableStorage()).get("/health/ready")

    assert response.status_code == 503
    assert response.json()["status"] == "not_ready"
    assert response.json()["dependencies"][1] == {
        "name": "object_storage",
        "status": "unavailable",
        "detail": "对象存储不可用",
    }


def test_operational_health_reports_healthy_empty_control_plane() -> None:
    response = _readiness_client(ReadyStorage()).get("/health/operational")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "healthy"
    assert {indicator["name"] for indicator in payload["indicators"]} == {
        "training_queue",
        "stale_training_lease",
        "webhook_delivery",
        "stale_usage_reservation",
    }
    assert all(indicator["observed_count"] == 0 for indicator in payload["indicators"])


def test_operational_health_surfaces_aggregate_attention_without_ids() -> None:
    client = _readiness_client(ReadyStorage())
    application = client.app
    override_session = application.dependency_overrides[get_session]
    now = datetime.now(UTC)
    with next(override_session()) as session:
        session.add_all(
            [
                Run(
                    project_id=uuid4(),
                    dataset_version_id=uuid4(),
                    status="queued",
                    engine="ultralytics",
                    executor="docker",
                    idempotency_key="stale-queue",
                    created_at=now - timedelta(minutes=11),
                ),
                Run(
                    project_id=uuid4(),
                    dataset_version_id=uuid4(),
                    status="running",
                    engine="ultralytics",
                    executor="docker",
                    idempotency_key="stale-lease",
                    claimed_at=now - timedelta(minutes=3),
                ),
                WebhookDelivery(
                    vision_event_id=uuid4(),
                    workflow_spec_id=uuid4(),
                    target_url="https://example.com/events",
                    status="failed",
                    next_attempt_at=now,
                ),
                UsageReservation(
                    subscription_id=uuid4(),
                    deployment_id=uuid4(),
                    request_id="stale-reservation",
                    units=1,
                    status="pending",
                    created_at=now - timedelta(minutes=4),
                ),
            ]
        )
        session.commit()

    response = client.get("/health/operational")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "attention"
    assert all(indicator["observed_count"] == 1 for indicator in payload["indicators"])
    assert "stale-queue" not in str(payload)
    assert "stale-reservation" not in str(payload)


def test_overview_requires_workspace_context() -> None:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    testing_session = sessionmaker(bind=engine, expire_on_commit=False)
    Base.metadata.create_all(engine)

    def override_session() -> Iterator[Session]:
        with testing_session() as session:
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise

    application = create_app()
    application.dependency_overrides[get_session] = override_session
    response = TestClient(application).get("/api/v1/overview")
    assert response.status_code == 422
