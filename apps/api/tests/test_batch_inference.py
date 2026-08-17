import asyncio
from collections.abc import Iterator
from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from sensemu_api.batch_inference_schemas import BatchInferenceRunCreate, BatchInferenceRunResponse
from sensemu_api.db import Base, models
from sensemu_api.db.session import get_session
from sensemu_api.main import create_app
from sensemu_api.routes import batch_inference as batch_inference_routes
from sensemu_api.storage import get_storage
from sensemu_api.training_dispatch import get_training_dispatcher


class MemoryStorage:
    bucket = "sensemu-batch-test"

    def __init__(self) -> None:
        self.json_objects: dict[str, dict] = {}
        self.byte_objects: dict[str, bytes] = {}

    def put_json(self, key: str, payload: dict) -> str:
        self.json_objects[key] = payload
        return self.uri_for(key)

    def get_json(self, uri: str) -> dict:
        return self.json_objects[uri.removeprefix(f"s3://{self.bucket}/")]

    def get_bytes(self, uri: str) -> bytes:
        return self.byte_objects[uri.removeprefix(f"s3://{self.bucket}/")]

    def uri_for(self, key: str) -> str:
        return f"s3://{self.bucket}/{key}"


class FakeDispatcher:
    def __init__(self) -> None:
        self.batch_submissions: list[tuple[str, str]] = []

    def submit(self, workspace_id: UUID, run_id: UUID) -> None:
        del workspace_id, run_id

    def submit_acceptance(self, workspace_id: UUID, run_id: UUID) -> None:
        del workspace_id, run_id

    def submit_batch_inference(self, workspace_id: UUID, run_id: UUID) -> None:
        self.batch_submissions.append((str(workspace_id), str(run_id)))


def _client() -> tuple[TestClient, sessionmaker[Session], MemoryStorage, FakeDispatcher]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    storage = MemoryStorage()
    dispatcher = FakeDispatcher()

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
    application.dependency_overrides[get_training_dispatcher] = lambda: dispatcher
    return TestClient(application), sessions, storage, dispatcher


def _seed_batch_ready_project(
    client: TestClient,
    sessions: sessionmaker[Session],
    storage: MemoryStorage,
) -> tuple[dict, dict, dict, dict[str, str]]:
    workspace = client.post(
        "/api/v1/workspaces",
        json={"slug": "batch-space", "name": "批量推理空间"},
    ).json()
    headers = {"X-Workspace-ID": workspace["id"]}
    project = client.post(
        "/api/v1/projects",
        headers=headers,
        json={
            "slug": "ppe-batch",
            "name": "PPE 批量推理",
            "task_type": "object-detection",
        },
    ).json()
    version_id = uuid4()
    asset_ids = [uuid4(), uuid4()]
    manifest_key = "frozen-datasets/ppe-batch-v1.json"
    storage.put_json(
        manifest_key,
        {
            "assets": [
                {
                    "asset_id": str(asset_ids[0]),
                    "uri": "s3://sensemu-batch-test/inputs/one.png",
                    "media_type": "image/png",
                    "split": "test",
                },
                {
                    "asset_id": str(asset_ids[1]),
                    "uri": "s3://sensemu-batch-test/inputs/two.png",
                    "media_type": "image/png",
                    "split": "test",
                },
            ]
        },
    )
    with sessions() as session:
        dataset = models.Dataset(project_id=UUID(project["id"]), name="现场帧")
        session.add(dataset)
        session.flush()
        version = models.DatasetVersion(
            id=version_id,
            dataset_id=dataset.id,
            version_number=1,
            status="frozen",
            manifest_uri=storage.uri_for(manifest_key),
            asset_count=2,
            class_map={"0": "person", "1": "hardhat"},
            frozen_at=datetime.now(UTC),
        )
        run = models.Run(
            project_id=UUID(project["id"]),
            dataset_version_id=version_id,
            run_type="model.train",
            status="succeeded",
            engine="ultralytics",
            executor="docker",
            idempotency_key="seed-training-run",
            recipe={},
        )
        session.add_all([version, run])
        session.flush()
        model = models.Model(
            project_id=UUID(project["id"]),
            name="PPE 检测模型",
            task_type="object-detection",
        )
        session.add(model)
        session.flush()
        model_version = models.ModelVersion(
            model_id=model.id,
            run_id=run.id,
            version_number=1,
            status="approved",
            artifact_uri="s3://sensemu-batch-test/models/ppe.pt",
            metrics={"metrics/mAP50(B)": 0.9},
        )
        session.add(model_version)
        session.flush()
        deployment = models.Deployment(
            workspace_id=UUID(workspace["id"]),
            model_version_id=model_version.id,
            name="PPE 生产服务",
            endpoint_slug="ppe-batch-service",
            environment="production",
            status="published",
            api_key_prefix="smu_live_batch",
            api_key_hash="test-only",
            published_at=datetime.now(UTC),
        )
        session.add(deployment)
        session.commit()
        return workspace, project, {"id": str(version.id), "deployment_id": str(deployment.id)}, headers


def test_batch_inference_is_frozen_traceable_and_downloadable() -> None:
    client, sessions, storage, dispatcher = _client()
    workspace, project, fixtures, headers = _seed_batch_ready_project(client, sessions, storage)
    payload = {
        "deployment_id": fixtures["deployment_id"],
        "dataset_version_id": fixtures["id"],
        "source_split": "test",
        "parameters": {"confidence": 0.4, "image_size": 640},
    }
    created = client.post(
        f"/api/v1/projects/{project['id']}/batch-inference-runs",
        headers={**headers, "Idempotency-Key": "batch-predict-request-001"},
        json=payload,
    )
    assert created.status_code == 201
    run = created.json()
    assert run["run_type"] == "inference.batch"
    assert run["status"] == "queued"
    assert run["recipe"]["source_split"] == "test"
    assert run["recipe"]["parameters"]["confidence"] == 0.4
    assert dispatcher.batch_submissions == [(workspace["id"], run["id"])]

    repeated = client.post(
        f"/api/v1/projects/{project['id']}/batch-inference-runs",
        headers={**headers, "Idempotency-Key": "batch-predict-request-001"},
        json=payload,
    )
    assert repeated.status_code == 201
    assert repeated.json()["id"] == run["id"]
    assert repeated.json()["reused"] is True

    worker_headers = {
        **headers,
        "X-SenseMu-Worker-Token": "sensemu-worker-local-only",
    }
    attempt_id = str(uuid4())
    claim = client.post(
        f"/api/v1/internal/training-runs/{run['id']}/execution:claim",
        headers=worker_headers,
        json={"attempt_id": attempt_id, "worker_id": "batch-test-worker"},
    )
    assert claim.status_code == 200
    assert claim.json()["job_spec"]["deployment"]["id"] == fixtures["deployment_id"]
    started = client.post(
        f"/api/v1/internal/training-runs/{run['id']}/events",
        headers=worker_headers,
        json={
            "attempt_id": attempt_id,
            "event_id": str(uuid4()),
            "event_type": "job.started",
            "occurred_at": datetime.now(UTC).isoformat(),
        },
    )
    assert started.status_code == 200

    prefix = run["artifact_prefix"]
    output_key = f"{prefix}/predictions.ndjson"
    report_key = f"{prefix}/report.json"
    storage.byte_objects[output_key] = b'{"asset_id":"one","prediction":{"detections":[]}}\n'
    completion = client.post(
        f"/api/v1/internal/batch-inference-runs/{run['id']}/complete",
        headers=worker_headers,
        json={
            "attempt_id": attempt_id,
            "event_id": str(uuid4()),
            "output_uri": storage.uri_for(output_key),
            "report_uri": storage.uri_for(report_key),
            "processed_asset_count": 2,
            "prediction_count": 1,
            "runtime": {"engine": "ultralytics", "inference_ms": 12.5},
            "occurred_at": datetime.now(UTC).isoformat(),
        },
    )
    assert completion.status_code == 200
    assert completion.json()["status"] == "succeeded"
    assert completion.json()["result"]["summary"]["processed_asset_count"] == 2
    assert completion.json()["result"]["output_uri"] == storage.uri_for(output_key)

    listed = client.get(
        f"/api/v1/projects/{project['id']}/batch-inference-runs",
        headers=headers,
    )
    assert listed.status_code == 200
    assert listed.json()[0]["result"]["summary"]["prediction_count"] == 1
    downloaded = client.get(
        f"/api/v1/batch-inference-runs/{run['id']}/output",
        headers=headers,
    )
    assert downloaded.status_code == 200
    assert downloaded.headers["content-type"].startswith("application/x-ndjson")
    assert downloaded.content == storage.byte_objects[output_key]


def test_batch_inference_commits_before_background_dispatch(monkeypatch) -> None:
    events: list[str] = []
    project_id = uuid4()
    run_id = uuid4()
    now = datetime.now(UTC)
    run = BatchInferenceRunResponse(
        id=run_id,
        project_id=project_id,
        dataset_version_id=uuid4(),
        run_type="inference.batch",
        status="queued",
        engine="ultralytics",
        executor="runtime",
        recipe={},
        progress=0,
        artifact_prefix=None,
        spec_uri=None,
        error_code=None,
        error_message=None,
        execution_attempt=0,
        claimed_at=None,
        heartbeat_at=None,
        started_at=None,
        finished_at=None,
        created_at=now,
        updated_at=now,
        result=None,
    )

    def fake_create(*_args, **_kwargs):
        events.append("create")
        return run, False

    monkeypatch.setattr(
        batch_inference_routes.batch_inference_service,
        "create_batch_inference_run",
        fake_create,
    )

    class SessionStub:
        def commit(self) -> None:
            events.append("commit")

    class DispatcherStub:
        def submit_batch_inference(self, _workspace_id: UUID, _run_id: UUID) -> None:
            events.append("dispatch")

    background_tasks = batch_inference_routes.BackgroundTasks()
    response = batch_inference_routes.create_batch_inference_run(
        project_id,
        BatchInferenceRunCreate(
            deployment_id=uuid4(),
            dataset_version_id=uuid4(),
        ),
        "batch-commit-order",
        uuid4(),
        SessionStub(),
        object(),
        background_tasks,
        DispatcherStub(),
    )

    assert response.status == "queued"
    asyncio.run(background_tasks())
    assert events == ["create", "commit", "dispatch"]
