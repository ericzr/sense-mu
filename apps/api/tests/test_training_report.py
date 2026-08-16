from collections.abc import Iterator
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from sensemu_api.db import Base, models
from sensemu_api.db.session import get_session
from sensemu_api.main import create_app
from sensemu_api.storage import get_storage
from sensemu_api.training_service import (
    MAX_TRAINING_CLASS_METRICS_BYTES,
    MAX_TRAINING_REPORT_BYTES,
    MAX_TRAINING_VISUALIZATION_BYTES,
    PNG_SIGNATURE,
)


class ReportStorage:
    bucket = "sensemu-report-test"

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def uri_for(self, key: str) -> str:
        return f"s3://{self.bucket}/{key}"

    def get_bytes(self, uri: str) -> bytes:
        key = uri.removeprefix(f"s3://{self.bucket}/")
        try:
            return self.objects[key]
        except KeyError as error:
            raise FileNotFoundError(key) from error


def report_client() -> tuple[TestClient, sessionmaker[Session], ReportStorage]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    storage = ReportStorage()

    def override_session() -> Iterator[Session]:
        with sessions() as session:
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise

    application = create_app()
    application.dependency_overrides[get_session] = override_session
    application.dependency_overrides[get_storage] = lambda: storage
    return TestClient(application), sessions, storage


def seed_succeeded_run(
    client: TestClient,
    sessions: sessionmaker[Session],
) -> tuple[UUID, str, dict[str, str]]:
    suffix = uuid4().hex[:10]
    workspace = client.post(
        "/api/v1/workspaces",
        json={"slug": f"report-{suffix}", "name": "训练报告测试"},
    ).json()
    headers = {"X-Workspace-ID": workspace["id"]}
    project = client.post(
        "/api/v1/projects",
        headers=headers,
        json={
            "slug": f"report-project-{suffix}",
            "name": "报告项目",
            "task_type": "object-detection",
        },
    ).json()
    artifact_prefix = f"workspaces/{workspace['id']}/projects/{project['id']}/runs/{uuid4()}"
    with sessions() as session:
        dataset = models.Dataset(project_id=UUID(project["id"]), name="报告数据集")
        session.add(dataset)
        session.flush()
        version = models.DatasetVersion(
            dataset_id=dataset.id,
            version_number=1,
            status="frozen",
            manifest_uri="s3://sensemu-report-test/manifests/version.json",
        )
        session.add(version)
        session.flush()
        run = models.Run(
            project_id=UUID(project["id"]),
            dataset_version_id=version.id,
            status="succeeded",
            engine="ultralytics-yolo",
            executor="docker",
            idempotency_key=f"report-{suffix}",
            artifact_prefix=artifact_prefix,
            progress=100,
        )
        session.add(run)
        session.commit()
        return run.id, artifact_prefix, headers


def test_training_report_returns_404_when_artifact_is_missing() -> None:
    client, sessions, _storage = report_client()
    run_id, _artifact_prefix, headers = seed_succeeded_run(client, sessions)

    response = client.get(f"/api/v1/training-runs/{run_id}/report", headers=headers)

    assert response.status_code == 404
    assert response.json()["detail"] == "训练报告尚不可用"


def test_training_report_rejects_invalid_encoding() -> None:
    client, sessions, storage = report_client()
    run_id, artifact_prefix, headers = seed_succeeded_run(client, sessions)
    storage.objects[f"{artifact_prefix}/metrics/results.csv"] = b"\xff\xfe\xfa"

    response = client.get(f"/api/v1/training-runs/{run_id}/report", headers=headers)

    assert response.status_code == 422
    assert response.json()["detail"] == "训练报告格式无效"


def test_training_report_rejects_oversized_artifact() -> None:
    client, sessions, storage = report_client()
    run_id, artifact_prefix, headers = seed_succeeded_run(client, sessions)
    storage.objects[f"{artifact_prefix}/metrics/results.csv"] = b"x" * (
        MAX_TRAINING_REPORT_BYTES + 1
    )

    response = client.get(f"/api/v1/training-runs/{run_id}/report", headers=headers)

    assert response.status_code == 422
    assert response.json()["detail"] == "训练报告过大，暂不支持在页面中读取"


def test_training_visualization_returns_allowlisted_png() -> None:
    client, sessions, storage = report_client()
    run_id, artifact_prefix, headers = seed_succeeded_run(client, sessions)
    payload = PNG_SIGNATURE + b"real-training-visualization"
    storage.objects[f"{artifact_prefix}/metrics/confusion_matrix.png"] = payload

    response = client.get(
        f"/api/v1/training-runs/{run_id}/visualizations/confusion_matrix",
        headers=headers,
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.headers["cache-control"] == "private, max-age=300"
    assert response.content == payload


def test_training_visualization_is_unavailable_when_missing_or_not_allowlisted() -> None:
    client, sessions, _storage = report_client()
    run_id, _artifact_prefix, headers = seed_succeeded_run(client, sessions)

    missing = client.get(
        f"/api/v1/training-runs/{run_id}/visualizations/confusion_matrix",
        headers=headers,
    )
    unknown = client.get(
        f"/api/v1/training-runs/{run_id}/visualizations/model",
        headers=headers,
    )

    assert missing.status_code == 404
    assert unknown.status_code == 404
    assert missing.json()["detail"] == "训练评估图尚不可用"
    assert unknown.json()["detail"] == "训练评估图尚不可用"


def test_training_visualization_rejects_invalid_or_oversized_payload() -> None:
    client, sessions, storage = report_client()
    run_id, artifact_prefix, headers = seed_succeeded_run(client, sessions)
    key = f"{artifact_prefix}/metrics/confusion_matrix_normalized.png"
    storage.objects[key] = b"not-a-png"

    invalid = client.get(
        f"/api/v1/training-runs/{run_id}/visualizations/confusion_matrix_normalized",
        headers=headers,
    )

    storage.objects[key] = PNG_SIGNATURE + b"x" * MAX_TRAINING_VISUALIZATION_BYTES
    oversized = client.get(
        f"/api/v1/training-runs/{run_id}/visualizations/confusion_matrix_normalized",
        headers=headers,
    )

    assert invalid.status_code == 422
    assert invalid.json()["detail"] == "训练评估图格式无效"
    assert oversized.status_code == 422
    assert oversized.json()["detail"] == "训练评估图过大，暂不支持在页面中读取"


def test_training_class_metrics_returns_only_structured_real_artifact() -> None:
    client, sessions, storage = report_client()
    run_id, artifact_prefix, headers = seed_succeeded_run(client, sessions)
    storage.objects[f"{artifact_prefix}/metrics/class_metrics.json"] = b"""{
      "schema_version": 1,
      "classes": [
        {"id": 0, "name": "person", "precision": 0.91, "recall": 0.88, "map50": 0.92, "map50_95": 0.74}
      ]
    }"""

    response = client.get(f"/api/v1/training-runs/{run_id}/class-metrics", headers=headers)

    assert response.status_code == 200
    assert response.json() == {
        "run_id": str(run_id),
        "classes": [
            {
                "class_id": 0,
                "name": "person",
                "precision": 0.91,
                "recall": 0.88,
                "map50": 0.92,
                "map50_95": 0.74,
            }
        ],
    }


def test_training_class_metrics_rejects_invalid_or_oversized_artifact() -> None:
    client, sessions, storage = report_client()
    run_id, artifact_prefix, headers = seed_succeeded_run(client, sessions)
    key = f"{artifact_prefix}/metrics/class_metrics.json"
    storage.objects[key] = b'{"classes":[{"id":0,"name":"person","map50":"nan"}]}'

    invalid = client.get(f"/api/v1/training-runs/{run_id}/class-metrics", headers=headers)

    storage.objects[key] = b"x" * (MAX_TRAINING_CLASS_METRICS_BYTES + 1)
    oversized = client.get(f"/api/v1/training-runs/{run_id}/class-metrics", headers=headers)

    assert invalid.status_code == 422
    assert invalid.json()["detail"] == "类别指标报告格式无效"
    assert oversized.status_code == 422
    assert oversized.json()["detail"] == "类别指标报告过大，暂不支持在页面中读取"
