import json
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from hmac import new as hmac_new
from io import BytesIO
from uuid import UUID, uuid4
from zipfile import ZIP_DEFLATED, ZipFile

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from sensemu_api.db import (
    Base,
    models,
)
from sensemu_api.db.session import get_session
from sensemu_api.main import app
from sensemu_api.storage import get_storage
from sensemu_api.training_dispatch import get_training_dispatcher
from sensemu_api.webhook_dispatch import get_webhook_dispatcher


class FakeStorage:
    bucket = "sensemu-test"

    def __init__(self) -> None:
        self.manifests: dict[str, dict] = {}
        self.objects: dict[str, bytes] = {}

    def presign_put(
        self,
        key: str,
        content_type: str,
        checksum_sha256: str,
        expires_in: int = 900,
    ) -> str:
        del checksum_sha256
        return f"https://uploads.example.test/{key}?expires={expires_in}&type={content_type}"

    def uri_for(self, key: str) -> str:
        return f"s3://{self.bucket}/{key}"

    def verify_object(self, key: str, byte_size: int, checksum_sha256: str) -> bool:
        del key, byte_size, checksum_sha256
        return True

    def put_json(self, key: str, payload: dict) -> str:
        self.manifests[key] = payload
        return f"s3://{self.bucket}/{key}"

    def get_json(self, uri: str) -> dict:
        return self.manifests[uri.removeprefix(f"s3://{self.bucket}/")]

    def get_bytes(self, uri: str) -> bytes:
        key = uri.removeprefix(f"s3://{self.bucket}/")
        return self.objects.get(key, b"0 0.5 0.5 0.2 0.2\n")

    def put_bytes(
        self,
        key: str,
        payload: bytes,
        content_type: str = "application/octet-stream",
    ) -> str:
        del content_type
        self.objects[key] = payload
        return self.uri_for(key)


class FakeDispatcher:
    def __init__(self) -> None:
        self.submissions: list[tuple[str, str]] = []
        self.acceptance_submissions: list[tuple[str, str]] = []

    def submit(self, workspace_id, run_id) -> None:
        self.submissions.append((str(workspace_id), str(run_id)))

    def submit_acceptance(self, workspace_id, run_id) -> None:
        self.acceptance_submissions.append((str(workspace_id), str(run_id)))


class FakeWebhookDispatcher:
    def __init__(self) -> None:
        self.submissions: list[str] = []

    def submit(self, delivery_id) -> None:
        self.submissions.append(str(delivery_id))


engine = create_engine(
    "sqlite+pysqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSession = sessionmaker(bind=engine, expire_on_commit=False)
Base.metadata.create_all(engine)
fake_storage = FakeStorage()
fake_dispatcher = FakeDispatcher()
fake_webhook_dispatcher = FakeWebhookDispatcher()


def override_session() -> Iterator[Session]:
    with TestingSession() as session:
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise


app.dependency_overrides[get_session] = override_session
app.dependency_overrides[get_storage] = lambda: fake_storage
app.dependency_overrides[get_training_dispatcher] = lambda: fake_dispatcher
app.dependency_overrides[get_webhook_dispatcher] = lambda: fake_webhook_dispatcher
client = TestClient(app)


def register_image(
    dataset_id: str,
    headers: dict[str, str],
    *,
    checksum: str,
    filename: str,
) -> dict:
    intent = client.post(
        f"/api/v1/datasets/{dataset_id}/uploads",
        headers=headers,
        json={
            "filename": filename,
            "content_type": "image/png",
            "byte_size": 2048,
            "checksum_sha256": checksum,
        },
    ).json()
    response = client.post(
        f"/api/v1/datasets/{dataset_id}/assets",
        headers=headers,
        json={
            "object_key": intent["object_key"],
            "media_type": "image/png",
            "checksum_sha256": checksum,
            "byte_size": 2048,
            "width": 640,
            "height": 640,
        },
    )
    assert response.status_code == 201
    return response.json()


def prepare_detection_item(
    dataset_id: str,
    asset: dict,
    headers: dict[str, str],
    *,
    split: str,
) -> dict:
    split_response = client.patch(
        f"/api/v1/datasets/{dataset_id}/items/{asset['id']}",
        headers=headers,
        json={"split": split},
    )
    assert split_response.status_code == 200

    annotation_checksum = asset["checksum_sha256"][0] * 64
    annotation_body = b"0 0.5 0.5 0.2 0.2\n"
    intent_response = client.post(
        f"/api/v1/datasets/{dataset_id}/items/{asset['id']}/annotation-uploads",
        headers=headers,
        json={
            "filename": f"{asset['id']}.txt",
            "byte_size": len(annotation_body),
            "checksum_sha256": annotation_checksum,
        },
    )
    assert intent_response.status_code == 201
    intent = intent_response.json()
    fake_storage.objects[intent["object_key"]] = annotation_body
    annotation_response = client.post(
        f"/api/v1/datasets/{dataset_id}/items/{asset['id']}/annotation",
        headers=headers,
        json={
            "object_key": intent["object_key"],
            "byte_size": len(annotation_body),
            "checksum_sha256": annotation_checksum,
        },
    )
    assert annotation_response.status_code == 200
    prepared = annotation_response.json()
    assert prepared["split"] == split
    assert prepared["annotation_uri"]
    return prepared


def create_sidebar_lifecycle_project(label: str) -> tuple[dict, dict, dict[str, str]]:
    suffix = uuid4().hex[:10]
    workspace_response = client.post(
        "/api/v1/workspaces",
        json={"slug": f"sidebar-{label}-{suffix}", "name": f"Sidebar {label}"},
    )
    assert workspace_response.status_code == 201
    workspace = workspace_response.json()
    headers = {"X-Workspace-ID": workspace["id"]}
    project_response = client.post(
        "/api/v1/projects",
        headers=headers,
        json={
            "slug": f"sidebar-project-{suffix}",
            "name": f"Sidebar {label} project",
            "task_type": "object-detection",
        },
    )
    assert project_response.status_code == 201
    return workspace, project_response.json(), headers


def test_sidebar_project_archive_honors_active_work_and_published_services() -> None:
    workspace, project, headers = create_sidebar_lifecycle_project("archive")
    dataset_response = client.post(
        f"/api/v1/projects/{project['id']}/datasets",
        headers=headers,
        json={"name": "archive_source"},
    )
    assert dataset_response.status_code == 201
    dataset = dataset_response.json()

    with TestingSession() as session:
        version = models.DatasetVersion(
            dataset_id=UUID(dataset["id"]),
            version_number=1,
            status="frozen",
            manifest_uri="s3://sensemu-test/archive/manifest.json",
            asset_count=0,
            class_map={},
        )
        session.add(version)
        session.flush()
        run = models.Run(
            project_id=UUID(project["id"]),
            dataset_version_id=version.id,
            run_type="training",
            status="running",
            engine="ultralytics",
            executor="docker",
            idempotency_key=f"archive-run-{uuid4().hex}",
            recipe={},
        )
        session.add(run)
        session.commit()

    blocked_run = client.post(f"/api/v1/projects/{project['id']}:archive", headers=headers)
    assert blocked_run.status_code == 409
    assert "运行中" in blocked_run.json()["detail"]

    with TestingSession() as session:
        stored_run = session.get(models.Run, run.id)
        assert stored_run is not None
        stored_run.status = "succeeded"
        model = models.Model(
            project_id=UUID(project["id"]),
            name="archive_model",
            task_type="object-detection",
        )
        session.add(model)
        session.flush()
        model_version = models.ModelVersion(
            model_id=model.id,
            run_id=stored_run.id,
            version_number=1,
            status="validation_passed",
            artifact_uri="s3://sensemu-test/archive/model.pt",
            metrics={},
        )
        session.add(model_version)
        session.flush()
        deployment = models.Deployment(
            workspace_id=UUID(workspace["id"]),
            model_version_id=model_version.id,
            name="archive_service",
            endpoint_slug=f"archive-service-{uuid4().hex[:8]}",
            environment="production",
            status="published",
        )
        session.add(deployment)
        session.commit()

    blocked_service = client.post(f"/api/v1/projects/{project['id']}:archive", headers=headers)
    assert blocked_service.status_code == 409
    assert "在线服务" in blocked_service.json()["detail"]

    with TestingSession() as session:
        stored_deployment = session.get(models.Deployment, deployment.id)
        assert stored_deployment is not None
        stored_deployment.status = "disabled"
        session.commit()

    archived = client.post(f"/api/v1/projects/{project['id']}:archive", headers=headers)
    assert archived.status_code == 200
    assert archived.json()["status"] == "paused"
    listed = client.get("/api/v1/projects", headers=headers)
    assert listed.status_code == 200
    assert project["id"] not in {item["id"] for item in listed.json()}


def test_sidebar_dataset_delete_only_allows_unlinked_drafts() -> None:
    workspace, project, headers = create_sidebar_lifecycle_project("dataset-delete")

    def create_dataset(name: str) -> dict:
        response = client.post(
            f"/api/v1/projects/{project['id']}/datasets",
            headers=headers,
            json={"name": name},
        )
        assert response.status_code == 201
        return response.json()

    deletable = create_dataset("draft_delete")
    frozen = create_dataset("frozen_delete")
    tasked = create_dataset("tasked_delete")
    extracted = create_dataset("extracted_delete")

    deleted = client.delete(f"/api/v1/datasets/{deletable['id']}", headers=headers)
    assert deleted.status_code == 204
    listed = client.get(f"/api/v1/projects/{project['id']}/datasets", headers=headers)
    assert deletable["id"] not in {item["id"] for item in listed.json()}

    with TestingSession() as session:
        session.add(models.DatasetVersion(
            dataset_id=UUID(frozen["id"]),
            version_number=1,
            status="frozen",
            manifest_uri="s3://sensemu-test/delete/frozen.json",
            asset_count=0,
            class_map={},
        ))
        owner = session.query(models.UserAccount).first()
        assert owner is not None
        session.add(models.AnnotationTask(
            dataset_id=UUID(tasked["id"]),
            name="protected_task",
            method="manual",
            asset_scope="all",
            status="annotating",
            assigned_to_user_id=owner.id,
            class_map={},
        ))
        asset = models.Asset(
            workspace_id=UUID(workspace["id"]),
            uri="s3://sensemu-test/delete/source.mp4",
            media_type="video/mp4",
            checksum_sha256=uuid4().hex + uuid4().hex,
            byte_size=512,
            width=None,
            height=None,
        )
        session.add(asset)
        session.flush()
        session.add(models.VideoExtractionJob(
            dataset_id=UUID(extracted["id"]),
            source_asset_id=asset.id,
            idempotency_key=f"delete-extraction-{uuid4().hex}",
            frame_interval_ms=1000,
            deduplicate=True,
            status="queued",
        ))
        session.commit()

    for dataset, message in [
        (frozen, "冻结数据版本"),
        (tasked, "标注任务"),
        (extracted, "视频抽帧任务"),
    ]:
        blocked = client.delete(f"/api/v1/datasets/{dataset['id']}", headers=headers)
        assert blocked.status_code == 409
        assert message in blocked.json()["detail"]


def test_project_can_pause_and_resume() -> None:
    workspace_response = client.post(
        "/api/v1/workspaces",
        json={"slug": "lifecycle-test", "name": "Lifecycle Test"},
    )
    assert workspace_response.status_code == 201
    workspace = workspace_response.json()
    headers = {"X-Workspace-ID": workspace["id"]}
    project_response = client.post(
        "/api/v1/projects",
        headers=headers,
        json={
            "slug": "paused-project",
            "name": "Paused project",
            "task_type": "object-detection",
        },
    )
    assert project_response.status_code == 201
    project = project_response.json()
    assert project["status"] == "active"

    pause_response = client.post(
        f"/api/v1/projects/{project['id']}:pause",
        headers=headers,
    )
    assert pause_response.status_code == 200
    assert pause_response.json()["status"] == "paused"

    blocked_training = client.post(
        f"/api/v1/projects/{project['id']}/training-runs",
        headers={**headers, "Idempotency-Key": "paused-project-run"},
        json={
            "dataset_version_id": str(uuid4()),
            "engine": "ultralytics",
            "executor": "docker",
            "recipe": {
                "model": "yolo26s.pt",
                "task": "detect",
                "epochs": 20,
                "image_size": 640,
                "batch_size": 8,
                "seed": 42,
            },
        },
    )
    assert blocked_training.status_code == 409
    assert blocked_training.json()["detail"] == "项目已暂停，请先继续项目"

    resume_response = client.post(
        f"/api/v1/projects/{project['id']}:resume",
        headers=headers,
    )
    assert resume_response.status_code == 200
    assert resume_response.json()["status"] == "active"


def test_dataset_ingestion_and_freeze_vertical_slice() -> None:
    workspace_response = client.post(
        "/api/v1/workspaces",
        json={"slug": "sensemu-test", "name": "SenseMu Test"},
    )
    assert workspace_response.status_code == 201
    workspace = workspace_response.json()
    headers = {"X-Workspace-ID": workspace["id"]}

    project_response = client.post(
        "/api/v1/projects",
        headers=headers,
        json={
            "slug": "ppe-safety",
            "name": "PPE safety detection",
            "task_type": "object-detection",
        },
    )
    assert project_response.status_code == 201
    project = project_response.json()

    dataset_response = client.post(
        f"/api/v1/projects/{project['id']}/datasets",
        headers=headers,
        json={"name": "ppe_site_a"},
    )
    assert dataset_response.status_code == 201
    dataset = dataset_response.json()

    checksum = "a" * 64
    intent_response = client.post(
        f"/api/v1/datasets/{dataset['id']}/uploads",
        headers=headers,
        json={
            "filename": "yard/camera 01.jpg",
            "content_type": "image/jpeg",
            "byte_size": 1024,
            "checksum_sha256": checksum,
        },
    )
    assert intent_response.status_code == 201
    intent = intent_response.json()
    assert intent["method"] == "PUT"
    assert "camera-01.jpg" in intent["object_key"]

    asset_payload = {
        "object_key": intent["object_key"],
        "media_type": "image/jpeg",
        "checksum_sha256": checksum,
        "byte_size": 1024,
        "width": 1920,
        "height": 1080,
    }
    asset_response = client.post(
        f"/api/v1/datasets/{dataset['id']}/assets",
        headers=headers,
        json=asset_payload,
    )
    assert asset_response.status_code == 201
    assert asset_response.json()["reused"] is False

    fake_storage.objects[intent["object_key"]] = b"jpeg-preview"
    asset_content_response = client.get(
        f"/api/v1/datasets/{dataset['id']}/assets/{asset_response.json()['id']}/content",
        headers=headers,
    )
    assert asset_content_response.status_code == 200
    assert asset_content_response.headers["content-type"] == "image/jpeg"
    assert asset_content_response.content == b"jpeg-preview"

    duplicate_response = client.post(
        f"/api/v1/datasets/{dataset['id']}/assets",
        headers=headers,
        json=asset_payload,
    )
    assert duplicate_response.status_code == 201
    assert duplicate_response.json()["reused"] is True

    incomplete_freeze = client.post(
        f"/api/v1/datasets/{dataset['id']}/versions:freeze",
        headers=headers,
        json={"class_map": {"0": "helmet", "1": "vest"}},
    )
    assert incomplete_freeze.status_code == 409

    first_asset = prepare_detection_item(
        dataset["id"],
        asset_response.json(),
        headers,
        split="train",
    )
    second_asset = register_image(
        dataset["id"],
        headers,
        checksum="b" * 64,
        filename="camera-02.png",
    )
    prepare_detection_item(dataset["id"], second_asset, headers, split="valid")

    freeze_response = client.post(
        f"/api/v1/datasets/{dataset['id']}/versions:freeze",
        headers=headers,
        json={"class_map": {"0": "helmet", "1": "vest"}},
    )
    assert freeze_response.status_code == 201
    version = freeze_response.json()
    assert version["version_number"] == 1
    assert version["status"] == "frozen"
    assert version["asset_count"] == 2
    assert fake_storage.manifests
    manifest = next(reversed(fake_storage.manifests.values()))
    assert {item["split"] for item in manifest["assets"]} == {"train", "valid"}
    assert all(item["annotation_uri"] for item in manifest["assets"])
    assert manifest["quality_report"]["split_counts"] == {
        "train": 1,
        "valid": 1,
        "test": 0,
    }
    assert first_asset["annotation_uri"]

    quality_response = client.get(
        f"/api/v1/dataset-versions/{version['id']}/quality-report",
        headers=headers,
    )
    assert quality_response.status_code == 200
    quality = quality_response.json()
    assert quality["dataset_version_id"] == version["id"]
    assert quality["annotation_coverage_percent"] == 100
    assert quality["class_distribution"] == [
        {
            "class_id": 0,
            "class_name": "helmet",
            "annotation_count": 2,
            "asset_count": 2,
        },
        {
            "class_id": 1,
            "class_name": "vest",
            "annotation_count": 0,
            "asset_count": 0,
        },
    ]

    dataset_list = client.get(
        f"/api/v1/projects/{project['id']}/datasets",
        headers=headers,
    )
    assert dataset_list.status_code == 200
    assert dataset_list.json()[0]["asset_count"] == 2
    assert dataset_list.json()[0]["version_count"] == 1


def test_workspace_context_prevents_cross_tenant_reads() -> None:
    other_workspace = client.post(
        "/api/v1/workspaces",
        json={"slug": "other-space", "name": "Other Space"},
    ).json()
    projects = client.get(
        "/api/v1/projects",
        headers={"X-Workspace-ID": other_workspace["id"]},
    )
    assert projects.status_code == 200
    assert projects.json() == []


def test_training_run_submission_is_persisted_idempotent_and_cancellable() -> None:
    workspace = client.post(
        "/api/v1/workspaces",
        json={"slug": "training-space", "name": "Training Space"},
    ).json()
    workspace_headers = {"X-Workspace-ID": workspace["id"]}
    project = client.post(
        "/api/v1/projects",
        headers=workspace_headers,
        json={
            "slug": "helmet-training",
            "name": "Helmet training",
            "task_type": "object-detection",
        },
    ).json()
    dataset = client.post(
        f"/api/v1/projects/{project['id']}/datasets",
        headers=workspace_headers,
        json={"name": "helmet_dataset"},
    ).json()

    train_asset = register_image(
        dataset["id"],
        workspace_headers,
        checksum="c" * 64,
        filename="helmet-train.png",
    )
    prepare_detection_item(dataset["id"], train_asset, workspace_headers, split="train")
    valid_asset = register_image(
        dataset["id"],
        workspace_headers,
        checksum="d" * 64,
        filename="helmet-valid.png",
    )
    prepare_detection_item(dataset["id"], valid_asset, workspace_headers, split="valid")
    version = client.post(
        f"/api/v1/datasets/{dataset['id']}/versions:freeze",
        headers=workspace_headers,
        json={"class_map": {"0": "helmet"}},
    ).json()

    idempotency_headers = {
        **workspace_headers,
        "Idempotency-Key": "training-test-request-001",
    }
    payload = {
        "dataset_version_id": version["id"],
        "engine": "ultralytics",
        "executor": "docker",
        "recipe": {
            "model": "yolo26s.pt",
            "task": "detect",
            "epochs": 20,
            "image_size": 640,
            "batch_size": 8,
            "seed": 42,
        },
    }
    created_response = client.post(
        f"/api/v1/projects/{project['id']}/training-runs",
        headers=idempotency_headers,
        json=payload,
    )
    assert created_response.status_code == 201
    created = created_response.json()
    assert created["status"] == "queued"
    assert created["progress"] == 0
    assert created["reused"] is False
    assert created["spec_uri"].endswith("/job-spec.json")
    assert fake_dispatcher.submissions[-1] == (workspace["id"], created["id"])

    duplicate = client.post(
        f"/api/v1/projects/{project['id']}/training-runs",
        headers=idempotency_headers,
        json=payload,
    )
    assert duplicate.status_code == 201
    assert duplicate.json()["id"] == created["id"]
    assert duplicate.json()["reused"] is True

    overview_response = client.get("/api/v1/overview", headers=workspace_headers)
    assert overview_response.status_code == 200
    overview = overview_response.json()
    assert overview["metrics"] == {
        "datasets": 1,
        "assets": 2,
        "training_jobs_running": 1,
        "model_versions_ready": 0,
        "inference_calls_month": 0,
    }
    assert overview["active_runs"][0]["run_id"] == created["id"]
    assert overview["active_runs"][0]["dataset_version_number"] == 1
    assert overview["recent_runs"][0]["model"] == "yolo26s.pt"

    conflicting_payload = {**payload, "recipe": {**payload["recipe"], "epochs": 21}}
    conflict_response = client.post(
        f"/api/v1/projects/{project['id']}/training-runs",
        headers=idempotency_headers,
        json=conflicting_payload,
    )
    assert conflict_response.status_code == 409

    events_response = client.get(
        f"/api/v1/training-runs/{created['id']}/events",
        headers=workspace_headers,
    )
    assert events_response.status_code == 200
    assert [event["event_type"] for event in events_response.json()] == ["job.queued"]

    cancelled = client.post(
        f"/api/v1/training-runs/{created['id']}:cancel",
        headers=workspace_headers,
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"

    events_after_cancel = client.get(
        f"/api/v1/training-runs/{created['id']}/events",
        headers=workspace_headers,
    ).json()
    assert [event["event_type"] for event in events_after_cancel] == [
        "job.queued",
        "job.cancelled",
    ]
    assert any(key.endswith("/job-spec.json") for key in fake_storage.manifests)

    worker_run_response = client.post(
        f"/api/v1/projects/{project['id']}/training-runs",
        headers={
            **workspace_headers,
            "Idempotency-Key": "training-test-request-002",
        },
        json=payload,
    )
    assert worker_run_response.status_code == 201
    worker_run = worker_run_response.json()
    redispatched = client.post(
        f"/api/v1/training-runs/{worker_run['id']}:dispatch",
        headers=workspace_headers,
    )
    assert redispatched.status_code == 200
    assert fake_dispatcher.submissions[-1] == (workspace["id"], worker_run["id"])
    worker_headers = {
        **workspace_headers,
        "X-SenseMu-Worker-Token": "sensemu-worker-local-only",
    }
    attempt_id = str(uuid4())
    execution = client.post(
        f"/api/v1/internal/training-runs/{worker_run['id']}/execution:claim",
        headers=worker_headers,
        json={"attempt_id": attempt_id, "worker_id": "test-worker"},
    )
    assert execution.status_code == 200
    assert execution.json()["attempt_id"] == attempt_id
    assert execution.json()["job_spec"]["dataset_version"]["id"] == version["id"]
    heartbeat = client.post(
        f"/api/v1/internal/training-runs/{worker_run['id']}/execution:heartbeat",
        headers=worker_headers,
        json={"attempt_id": attempt_id},
    )
    assert heartbeat.status_code == 200
    assert heartbeat.json()["heartbeat_at"]
    rejected_heartbeat = client.post(
        f"/api/v1/internal/training-runs/{worker_run['id']}/execution:heartbeat",
        headers=worker_headers,
        json={"attempt_id": str(uuid4())},
    )
    assert rejected_heartbeat.status_code == 409
    competing_claim = client.post(
        f"/api/v1/internal/training-runs/{worker_run['id']}/execution:claim",
        headers=worker_headers,
        json={"attempt_id": str(uuid4()), "worker_id": "competing-worker"},
    )
    assert competing_claim.status_code == 409
    rejected_dispatch = client.post(
        f"/api/v1/training-runs/{worker_run['id']}:dispatch",
        headers=workspace_headers,
    )
    assert rejected_dispatch.status_code == 409

    occurred_at = datetime.now(UTC).isoformat()
    started_event_id = str(uuid4())
    started = client.post(
        f"/api/v1/internal/training-runs/{worker_run['id']}/events",
        headers=worker_headers,
        json={
            "attempt_id": attempt_id,
            "event_id": started_event_id,
            "event_type": "job.started",
            "occurred_at": occurred_at,
        },
    )
    assert started.status_code == 200
    assert started.json()["status"] == "running"

    progress_event_id = str(uuid4())
    progress_payload = {
        "attempt_id": attempt_id,
        "event_id": progress_event_id,
        "event_type": "job.progressed",
        "progress": 40,
        "occurred_at": occurred_at,
    }
    progressed = client.post(
        f"/api/v1/internal/training-runs/{worker_run['id']}/events",
        headers=worker_headers,
        json=progress_payload,
    )
    assert progressed.status_code == 200
    assert progressed.json()["progress"] == 40
    repeated_progress = client.post(
        f"/api/v1/internal/training-runs/{worker_run['id']}/events",
        headers=worker_headers,
        json=progress_payload,
    )
    assert repeated_progress.status_code == 200
    assert repeated_progress.json()["progress"] == 40

    policy_response = client.post(
        f"/api/v1/projects/{project['id']}/evaluation-policies",
        headers=workspace_headers,
        json={
            "name": "Helmet quality gate",
            "rules": [
                {
                    "metric": "metrics/mAP50(B)",
                    "operator": ">=",
                    "threshold": 0.8,
                    "label": "mAP50 baseline",
                }
            ],
        },
    )
    assert policy_response.status_code == 201
    assert policy_response.json()["version_number"] == 1
    assert policy_response.json()["is_active"] is True

    artifact_uri = f"s3://{fake_storage.bucket}/{worker_run['artifact_prefix']}/model/best.pt"
    completion_payload = {
        "attempt_id": attempt_id,
        "event_id": str(uuid4()),
        "model_name": "Helmet detector",
        "artifact_uri": artifact_uri,
        "metrics": {"metrics/mAP50(B)": 0.82},
        "occurred_at": occurred_at,
    }
    completion = client.post(
        f"/api/v1/internal/training-runs/{worker_run['id']}/complete",
        headers=worker_headers,
        json=completion_payload,
    )
    assert completion.status_code == 200
    assert completion.json()["version_number"] == 1
    assert completion.json()["artifact_uri"] == artifact_uri
    assert completion.json()["status"] == "validation_passed"
    repeated_completion = client.post(
        f"/api/v1/internal/training-runs/{worker_run['id']}/complete",
        headers=worker_headers,
        json=completion_payload,
    )
    assert repeated_completion.status_code == 200
    assert repeated_completion.json()["id"] == completion.json()["id"]

    finished_run = client.get(
        f"/api/v1/training-runs/{worker_run['id']}",
        headers=workspace_headers,
    ).json()
    assert finished_run["status"] == "succeeded"
    assert finished_run["progress"] == 100

    fake_storage.objects[
        f"{worker_run['artifact_prefix']}/metrics/results.csv"
    ] = (
        b"epoch,train/box_loss,metrics/precision(B),metrics/mAP50(B)\n"
        b"0,1.24,0.61,0.52\n"
        b"1,0.81,0.76,0.82\n"
    )
    training_report = client.get(
        f"/api/v1/training-runs/{worker_run['id']}/report",
        headers=workspace_headers,
    )
    assert training_report.status_code == 200
    assert training_report.json() == {
        "run_id": worker_run["id"],
        "rows": [
            {
                "epoch": 0,
                "metrics": {
                    "train/box_loss": 1.24,
                    "metrics/precision(B)": 0.61,
                    "metrics/mAP50(B)": 0.52,
                },
            },
            {
                "epoch": 1,
                "metrics": {
                    "train/box_loss": 0.81,
                    "metrics/precision(B)": 0.76,
                    "metrics/mAP50(B)": 0.82,
                },
            },
        ],
    }
    unavailable_report = client.get(
        f"/api/v1/training-runs/{created['id']}/report",
        headers=workspace_headers,
    )
    assert unavailable_report.status_code == 404

    model_versions = client.get(
        f"/api/v1/projects/{project['id']}/model-versions",
        headers=workspace_headers,
    ).json()
    assert model_versions[0]["run_id"] == worker_run["id"]
    assert model_versions[0]["status"] == "validation_passed"

    evaluations = client.get(
        f"/api/v1/projects/{project['id']}/evaluations",
        headers=workspace_headers,
    )
    assert evaluations.status_code == 200
    first_evaluation = evaluations.json()[0]
    assert first_evaluation["verdict"] == "approved"
    assert first_evaluation["source"] == "training-validation"
    assert first_evaluation["rule_results"][0]["actual"] == 0.82
    assert first_evaluation["rule_results"][0]["passed"] is True
    evaluation_report = fake_storage.get_json(first_evaluation["report_uri"])
    assert evaluation_report["policy"]["version_number"] == 1
    assert evaluation_report["verdict"] == "approved"
    approved_overview = client.get("/api/v1/overview", headers=workspace_headers).json()
    assert approved_overview["metrics"]["model_versions_ready"] == 0

    stricter_policy = client.post(
        f"/api/v1/projects/{project['id']}/evaluation-policies",
        headers=workspace_headers,
        json={
            "name": "Helmet production gate",
            "rules": [
                {
                    "metric": "metrics/mAP50(B)",
                    "operator": ">=",
                    "threshold": 0.9,
                    "label": "production mAP50",
                }
            ],
        },
    )
    assert stricter_policy.status_code == 201
    assert stricter_policy.json()["version_number"] == 2
    policies = client.get(
        f"/api/v1/projects/{project['id']}/evaluation-policies",
        headers=workspace_headers,
    ).json()
    assert [policy["version_number"] for policy in policies] == [2, 1]
    assert [policy["is_active"] for policy in policies] == [True, False]

    reevaluated = client.post(
        f"/api/v1/model-versions/{completion.json()['id']}:evaluate",
        headers=workspace_headers,
    )
    assert reevaluated.status_code == 200
    assert reevaluated.json()["policy_version"] == 2
    assert reevaluated.json()["verdict"] == "rejected"
    assert reevaluated.json()["rule_results"][0]["passed"] is False
    model_versions_after_gate = client.get(
        f"/api/v1/projects/{project['id']}/model-versions",
        headers=workspace_headers,
    ).json()
    assert model_versions_after_gate[0]["status"] == "validation_failed"
    rejected_overview = client.get("/api/v1/overview", headers=workspace_headers).json()
    assert rejected_overview["metrics"]["model_versions_ready"] == 0
    blocked_deployment = client.post(
        f"/api/v1/projects/{project['id']}/deployments",
        headers=workspace_headers,
        json={
            "model_version_id": completion.json()["id"],
            "name": "Blocked service",
            "endpoint_slug": "blocked-service",
            "environment": "production",
        },
    )
    assert blocked_deployment.status_code == 409

    release_policy = client.post(
        f"/api/v1/projects/{project['id']}/evaluation-policies",
        headers=workspace_headers,
        json={
            "name": "Helmet release gate",
            "rules": [
                {
                    "metric": "metrics/mAP50(B)",
                    "operator": ">=",
                    "threshold": 0.8,
                    "label": "release mAP50",
                }
            ],
        },
    )
    assert release_policy.status_code == 201
    approved_again = client.post(
        f"/api/v1/model-versions/{completion.json()['id']}:evaluate",
        headers=workspace_headers,
    )
    assert approved_again.status_code == 200
    assert approved_again.json()["verdict"] == "approved"
    validation_only_deployment = client.post(
        f"/api/v1/projects/{project['id']}/deployments",
        headers=workspace_headers,
        json={
            "model_version_id": completion.json()["id"],
            "name": "Validation only service",
            "endpoint_slug": "validation-only-service",
            "environment": "production",
        },
    )
    assert validation_only_deployment.status_code == 409

    acceptance_dataset = client.post(
        f"/api/v1/projects/{project['id']}/datasets",
        headers=workspace_headers,
        json={"name": "helmet_acceptance"},
    ).json()
    acceptance_asset = register_image(
        acceptance_dataset["id"],
        workspace_headers,
        checksum="e" * 64,
        filename="helmet-acceptance.png",
    )
    prepare_detection_item(
        acceptance_dataset["id"],
        acceptance_asset,
        workspace_headers,
        split="valid",
    )
    acceptance_train_asset = register_image(
        acceptance_dataset["id"],
        workspace_headers,
        checksum="f" * 64,
        filename="helmet-acceptance-train.png",
    )
    prepare_detection_item(
        acceptance_dataset["id"],
        acceptance_train_asset,
        workspace_headers,
        split="train",
    )
    acceptance_version = client.post(
        f"/api/v1/datasets/{acceptance_dataset['id']}/versions:freeze",
        headers=workspace_headers,
        json={"class_map": {"0": "helmet"}},
    ).json()

    reused_training_data = client.post(
        (
            f"/api/v1/projects/{project['id']}/model-versions/"
            f"{completion.json()['id']}/acceptance-runs"
        ),
        headers={
            **workspace_headers,
            "Idempotency-Key": "acceptance-reused-training-data",
        },
        json={"dataset_version_id": version["id"]},
    )
    assert reused_training_data.status_code == 409

    acceptance_response = client.post(
        (
            f"/api/v1/projects/{project['id']}/model-versions/"
            f"{completion.json()['id']}/acceptance-runs"
        ),
        headers={
            **workspace_headers,
            "Idempotency-Key": "acceptance-test-request-001",
        },
        json={
            "dataset_version_id": acceptance_version["id"],
            "image_size": 640,
            "batch_size": 8,
        },
    )
    assert acceptance_response.status_code == 201
    acceptance_run = acceptance_response.json()
    assert acceptance_run["run_type"] == "model.acceptance-evaluate"
    assert fake_dispatcher.acceptance_submissions[-1] == (
        workspace["id"],
        acceptance_run["id"],
    )
    listed_acceptance = client.get(
        f"/api/v1/projects/{project['id']}/acceptance-runs",
        headers=workspace_headers,
    )
    assert listed_acceptance.status_code == 200
    assert listed_acceptance.json()[0]["id"] == acceptance_run["id"]

    acceptance_attempt_id = str(uuid4())
    acceptance_claim = client.post(
        f"/api/v1/internal/training-runs/{acceptance_run['id']}/execution:claim",
        headers=worker_headers,
        json={"attempt_id": acceptance_attempt_id, "worker_id": "evaluation-worker"},
    )
    assert acceptance_claim.status_code == 200
    acceptance_spec = acceptance_claim.json()["job_spec"]
    assert acceptance_spec["model_version"]["id"] == completion.json()["id"]
    assert acceptance_spec["dataset_version"]["id"] == acceptance_version["id"]
    assert acceptance_spec["policy"]["version_number"] == 3
    acceptance_started = client.post(
        f"/api/v1/internal/training-runs/{acceptance_run['id']}/events",
        headers=worker_headers,
        json={
            "attempt_id": acceptance_attempt_id,
            "event_id": str(uuid4()),
            "event_type": "job.started",
            "occurred_at": occurred_at,
        },
    )
    assert acceptance_started.status_code == 200
    acceptance_completion_payload = {
        "attempt_id": acceptance_attempt_id,
        "event_id": str(uuid4()),
        "metrics": {"metrics/mAP50(B)": 0.84},
        "evaluated_asset_count": 1,
        "runtime_image": "ultralytics@sha256:test",
        "occurred_at": occurred_at,
    }
    acceptance_completion = client.post(
        f"/api/v1/internal/acceptance-runs/{acceptance_run['id']}/complete",
        headers=worker_headers,
        json=acceptance_completion_payload,
    )
    assert acceptance_completion.status_code == 200
    acceptance_evaluation = acceptance_completion.json()
    assert acceptance_evaluation["source"] == "acceptance-dataset"
    assert acceptance_evaluation["verdict"] == "approved"
    acceptance_report = fake_storage.get_json(acceptance_evaluation["report_uri"])
    assert acceptance_report["evaluated_asset_count"] == 1
    assert acceptance_report["runtime"]["image_size"] == 640
    repeated_acceptance_completion = client.post(
        f"/api/v1/internal/acceptance-runs/{acceptance_run['id']}/complete",
        headers=worker_headers,
        json=acceptance_completion_payload,
    )
    assert repeated_acceptance_completion.status_code == 200
    assert repeated_acceptance_completion.json()["id"] == acceptance_evaluation["id"]
    accepted_overview = client.get(
        "/api/v1/overview", headers=workspace_headers
    ).json()
    assert accepted_overview["metrics"]["model_versions_ready"] == 1

    deployment_response = client.post(
        f"/api/v1/projects/{project['id']}/deployments",
        headers=workspace_headers,
        json={
            "model_version_id": completion.json()["id"],
            "name": "Helmet detection service",
            "endpoint_slug": "helmet-detector",
            "environment": "production",
        },
    )
    assert deployment_response.status_code == 201
    deployment = deployment_response.json()
    original_api_key = deployment["api_key"]
    assert original_api_key.startswith("smu_live_")
    assert deployment["status"] == "published"
    assert deployment["evaluation_policy_version"] == 3
    assert deployment["endpoint_url"].endswith(
        "/inference/v1/workspaces/training-space/endpoints/helmet-detector:predict"
    )
    deployment_spec = fake_storage.get_json(deployment["spec_uri"])
    assert deployment_spec["gate"]["evaluation_id"] == acceptance_evaluation["id"]
    assert "api_key" not in deployment_spec

    listed_deployments = client.get(
        f"/api/v1/projects/{project['id']}/deployments",
        headers=workspace_headers,
    )
    assert listed_deployments.status_code == 200
    assert "api_key" not in listed_deployments.json()[0]
    assert listed_deployments.json()[0]["request_count"] == 0

    invalid_capability = client.post(
        f"/api/v1/deployments/{deployment['id']}/capability-spec",
        headers=workspace_headers,
        json={
            "capability_slug": "ppe-compliance",
            "display_name": "PPE 合规检测",
            "problem_definition": "识别固定摄像头画面中的安全帽与反光衣违规行为。",
            "input": {
                "media_types": ["image/jpeg", "image/png"],
                "max_payload_bytes": 8388608,
                "capture_constraints": "固定摄像头，人员高度建议不低于 80 像素。",
            },
            "output": {
                "contract": "classification.v1",
                "classes": ["person", "hardhat", "safety_vest"],
                "business_events": ["missing_hardhat"],
            },
            "applicability": {
                "verified_scenes": ["construction-site"],
                "unsupported_conditions": ["严重逆光"],
            },
            "delivery": {
                "profiles": ["shared-api"],
                "data_retention_default": "none",
            },
        },
    )
    assert invalid_capability.status_code == 409

    capability_response = client.post(
        f"/api/v1/deployments/{deployment['id']}/capability-spec",
        headers=workspace_headers,
        json={
            "capability_slug": "ppe-compliance",
            "display_name": "PPE 合规检测",
            "problem_definition": "识别固定摄像头画面中的安全帽与反光衣违规行为。",
            "input": {
                "media_types": ["image/jpeg", "image/png"],
                "max_payload_bytes": 8388608,
                "capture_constraints": "固定摄像头，人员高度建议不低于 80 像素。",
            },
            "output": {
                "contract": "detections.v1",
                "classes": ["person", "hardhat", "safety_vest"],
                "business_events": ["missing_hardhat", "missing_safety_vest"],
            },
            "applicability": {
                "verified_scenes": ["construction-site", "warehouse"],
                "unsupported_conditions": ["严重逆光", "严重遮挡"],
            },
            "delivery": {
                "profiles": ["shared-api", "dedicated-endpoint"],
                "data_retention_default": "none",
            },
        },
    )
    assert capability_response.status_code == 201
    capability = capability_response.json()
    assert capability["capability_slug"] == "ppe-compliance"
    assert capability["version_number"] == 1
    assert capability["output"]["contract"] == "detections.v1"
    assert capability["evidence"]["evaluation_id"] == acceptance_evaluation["id"]
    capability_document = fake_storage.get_json(capability["spec_uri"])
    assert capability_document["kind"] == "CapabilitySpec"
    assert capability_document["metadata"]["id"] == "ppe-compliance"
    assert capability_document["spec"]["implementation"]["deployment_id"] == deployment["id"]
    assert capability["content_hash"]

    duplicate_capability = client.post(
        f"/api/v1/deployments/{deployment['id']}/capability-spec",
        headers=workspace_headers,
        json={
            "capability_slug": "ppe-compliance",
            "display_name": "PPE 合规检测",
            "problem_definition": "识别固定摄像头画面中的安全帽与反光衣违规行为。",
            "input": {
                "media_types": ["image/jpeg"],
                "max_payload_bytes": 8388608,
                "capture_constraints": "固定摄像头，人员高度建议不低于 80 像素。",
            },
            "output": {
                "contract": "detections.v1",
                "classes": ["person"],
                "business_events": [],
            },
            "applicability": {
                "verified_scenes": ["construction-site"],
                "unsupported_conditions": [],
            },
            "delivery": {
                "profiles": ["shared-api"],
                "data_retention_default": "none",
            },
        },
    )
    assert duplicate_capability.status_code == 409
    listed_capabilities = client.get(
        f"/api/v1/projects/{project['id']}/capability-specs",
        headers=workspace_headers,
    )
    assert listed_capabilities.status_code == 200
    assert [item["id"] for item in listed_capabilities.json()] == [capability["id"]]

    unsafe_workflow = client.post(
        f"/api/v1/projects/{project['id']}/workflow-specs",
        headers=workspace_headers,
        json={
            "workflow_slug": "ppe-alerts",
            "display_name": "PPE 违规告警",
            "capability_spec_id": capability["id"],
            "event_types": ["missing_hardhat"],
            "deduplication_window_seconds": 60,
            "webhook_url": "http://127.0.0.1:8080/events",
        },
    )
    assert unsafe_workflow.status_code == 422
    unsupported_event = client.post(
        f"/api/v1/projects/{project['id']}/workflow-specs",
        headers=workspace_headers,
        json={
            "workflow_slug": "ppe-alerts",
            "display_name": "PPE 违规告警",
            "capability_spec_id": capability["id"],
            "event_types": ["unauthorized_entry"],
            "deduplication_window_seconds": 60,
            "webhook_url": "https://events.example.com/sensemu",
        },
    )
    assert unsupported_event.status_code == 409
    workflow_response = client.post(
        f"/api/v1/projects/{project['id']}/workflow-specs",
        headers=workspace_headers,
        json={
            "workflow_slug": "ppe-alerts",
            "display_name": "PPE 违规告警",
            "capability_spec_id": capability["id"],
            "event_types": ["missing_hardhat", "missing_safety_vest"],
            "deduplication_window_seconds": 60,
            "webhook_url": "https://events.example.com/sensemu",
        },
    )
    assert workflow_response.status_code == 201
    workflow = workflow_response.json()
    assert workflow["template_key"] == "ppe-violation-webhook.v1"
    assert workflow["capability_spec_id"] == capability["id"]
    assert workflow["event_types"] == ["missing_hardhat", "missing_safety_vest"]
    workflow_document = fake_storage.get_json(workflow["spec_uri"])
    assert workflow_document["kind"] == "WorkflowSpec"
    assert workflow_document["spec"]["capability"]["content_hash"] == capability["content_hash"]
    listed_workflows = client.get(
        f"/api/v1/projects/{project['id']}/workflow-specs",
        headers=workspace_headers,
    )
    assert listed_workflows.status_code == 200
    assert [item["id"] for item in listed_workflows.json()] == [workflow["id"]]

    vision_event_payload = {
        "request_id": "request-vision-001",
        "idempotency_key": "event-missing-hardhat-001",
        "deduplication_key": "north-gate.0",
        "event_type": "missing_hardhat",
        "payload": {
            "source": {"id": "north-gate", "type": "camera", "input_index": 0},
            "condition": {
                "kind": "frame-class-absence.v1",
                "required_class": "hardhat",
                "person_count": 1,
                "required_class_count": 0,
            },
            "frame": {"width": 1920, "height": 1080, "detection_count": 1},
        },
        "occurred_at": occurred_at,
    }
    invalid_gateway_event = client.post(
        f"/api/v1/internal/workflow-specs/{workflow['id']}/vision-events",
        headers={"X-SenseMu-Gateway-Token": "invalid-gateway-token"},
        json=vision_event_payload,
    )
    assert invalid_gateway_event.status_code == 403
    unsupported_vision_event = client.post(
        f"/api/v1/internal/workflow-specs/{workflow['id']}/vision-events",
        headers={"X-SenseMu-Gateway-Token": "sensemu-gateway-local-only"},
        json={**vision_event_payload, "event_type": "unauthorized_entry"},
    )
    assert unsupported_vision_event.status_code == 409
    emitted_vision_event = client.post(
        f"/api/v1/internal/workflow-specs/{workflow['id']}/vision-events",
        headers={"X-SenseMu-Gateway-Token": "sensemu-gateway-local-only"},
        json=vision_event_payload,
    )
    assert emitted_vision_event.status_code == 200
    vision_event = emitted_vision_event.json()
    assert vision_event["reused"] is False
    assert vision_event["delivery_status"] == "pending"
    assert fake_webhook_dispatcher.submissions[-1] == vision_event["delivery_id"]
    repeated_vision_event = client.post(
        f"/api/v1/internal/workflow-specs/{workflow['id']}/vision-events",
        headers={"X-SenseMu-Gateway-Token": "sensemu-gateway-local-only"},
        json=vision_event_payload,
    )
    assert repeated_vision_event.status_code == 200
    assert repeated_vision_event.json()["id"] == vision_event["id"]
    assert repeated_vision_event.json()["reused"] is True
    deduplicated_vision_event = client.post(
        f"/api/v1/internal/workflow-specs/{workflow['id']}/vision-events",
        headers={"X-SenseMu-Gateway-Token": "sensemu-gateway-local-only"},
        json={
            **vision_event_payload,
            "request_id": "request-vision-002",
            "idempotency_key": "event-missing-hardhat-002",
            "occurred_at": (datetime.fromisoformat(occurred_at) + timedelta(seconds=30)).isoformat(),
        },
    )
    assert deduplicated_vision_event.status_code == 200
    assert deduplicated_vision_event.json()["id"] == vision_event["id"]
    assert deduplicated_vision_event.json()["reused"] is True

    invalid_worker_claim = client.post(
        f"/api/v1/internal/webhook-deliveries/{vision_event['delivery_id']}:claim",
        headers={"X-SenseMu-Worker-Token": "invalid-worker-token"},
    )
    assert invalid_worker_claim.status_code == 403
    webhook_claim = client.post(
        f"/api/v1/internal/webhook-deliveries/{vision_event['delivery_id']}:claim",
        headers={"X-SenseMu-Worker-Token": "sensemu-worker-local-only"},
    )
    assert webhook_claim.status_code == 200
    claimed_webhook = webhook_claim.json()
    encoded_webhook = json.dumps(
        claimed_webhook["payload"],
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    expected_signature = hmac_new(
        b"sensemu-webhook-signing-local-only",
        encoded_webhook,
        sha256,
    ).hexdigest()
    assert claimed_webhook["signature"] == expected_signature
    assert claimed_webhook["payload"]["event_id"] == vision_event["id"]
    assert claimed_webhook["payload"]["workflow"]["slug"] == "ppe-alerts"

    failed_webhook = client.post(
        f"/api/v1/internal/webhook-deliveries/{vision_event['delivery_id']}:complete",
        headers={"X-SenseMu-Worker-Token": "sensemu-worker-local-only"},
        json={"succeeded": False, "status_code": 502, "error": "上游暂时不可用"},
    )
    assert failed_webhook.status_code == 200
    assert failed_webhook.json()["status"] == "retrying"
    assert failed_webhook.json()["attempt_count"] == 1
    with TestingSession() as session:
        delivery = session.get(models.WebhookDelivery, UUID(vision_event["delivery_id"]))
        assert delivery is not None
        delivery.next_attempt_at = datetime.now(UTC) - timedelta(seconds=1)
        session.commit()
    recovered_webhook = client.post(
        "/api/v1/internal/webhook-deliveries:recover",
        headers={"X-SenseMu-Worker-Token": "sensemu-worker-local-only"},
    )
    assert recovered_webhook.status_code == 200
    assert recovered_webhook.json()["queued_delivery_ids"] == [
        vision_event["delivery_id"]
    ]
    assert fake_webhook_dispatcher.submissions[-1] == vision_event["delivery_id"]
    retried_claim = client.post(
        f"/api/v1/internal/webhook-deliveries/{vision_event['delivery_id']}:claim",
        headers={"X-SenseMu-Worker-Token": "sensemu-worker-local-only"},
    )
    assert retried_claim.status_code == 200
    assert retried_claim.json()["attempt_count"] == 2
    delivered_webhook = client.post(
        f"/api/v1/internal/webhook-deliveries/{vision_event['delivery_id']}:complete",
        headers={"X-SenseMu-Worker-Token": "sensemu-worker-local-only"},
        json={"succeeded": True, "status_code": 204},
    )
    assert delivered_webhook.status_code == 200
    assert delivered_webhook.json()["status"] == "delivered"
    listed_vision_events = client.get(
        f"/api/v1/projects/{project['id']}/vision-events",
        headers=workspace_headers,
    )
    assert listed_vision_events.status_code == 200
    listed_vision_event = listed_vision_events.json()[0]
    assert {
        key: listed_vision_event[key]
        for key in (
            "id",
            "request_id",
            "event_type",
            "workflow_spec_id",
            "workflow_slug",
            "workflow_name",
            "delivery_id",
            "delivery_status",
            "attempt_count",
            "last_error",
        )
    } == {
        "id": vision_event["id"],
        "request_id": "request-vision-001",
        "event_type": "missing_hardhat",
        "workflow_spec_id": workflow["id"],
        "workflow_slug": "ppe-alerts",
        "workflow_name": "PPE 违规告警",
        "delivery_id": vision_event["delivery_id"],
        "delivery_status": "delivered",
        "attempt_count": 2,
        "last_error": None,
    }
    assert datetime.fromisoformat(listed_vision_event["occurred_at"]) == datetime.fromisoformat(
        occurred_at
    )
    assert datetime.fromisoformat(
        listed_vision_event["delivered_at"]
    ) == datetime.fromisoformat(delivered_webhook.json()["delivered_at"])
    replayed_vision_event = client.get(
        f"/api/v1/projects/{project['id']}/vision-events/{vision_event['id']}/replay",
        headers=workspace_headers,
    )
    assert replayed_vision_event.status_code == 200
    replay = replayed_vision_event.json()
    assert replay["event_id"] == vision_event["id"]
    assert replay["template_key"] == "ppe-violation-webhook.v1"
    assert replay["sample"] == {
        "source_id": "north-gate",
        "source_type": "camera",
        "input_index": 0,
        "condition_kind": "frame-class-absence.v1",
        "required_class": "hardhat",
        "person_count": 1,
        "required_class_count": 0,
        "detection_count": 1,
        "width": 1920,
        "height": 1080,
    }
    assert replay["decision"]["matched"] is True
    assert replay["decision"]["deduplication_key"] == "north-gate.0"
    assert replay["decision"]["deduplication_window_seconds"] == 60
    assert replay["delivery"]["status"] == "delivered"
    assert replay["delivery"]["target_host"] == "events.example.com"
    assert replay["delivery"]["attempt_count"] == 2

    missing_replay = client.get(
        f"/api/v1/projects/{project['id']}/vision-events/{uuid4()}/replay",
        headers=workspace_headers,
    )
    assert missing_replay.status_code == 404

    gateway_headers = {
        "X-SenseMu-Gateway-Token": "sensemu-gateway-local-only",
        "X-API-Key": original_api_key,
    }
    resolved = client.post(
        "/api/v1/internal/inference/workspaces/training-space/endpoints/helmet-detector:resolve",
        headers=gateway_headers,
    )
    assert resolved.status_code == 200
    assert resolved.json()["contract"] == "detections.v1"
    assert resolved.json()["artifact_uri"] == artifact_uri
    assert resolved.json()["workflow_bindings"] == [
        {
            "workflow_id": workflow["id"],
            "workflow_slug": "ppe-alerts",
            "workflow_version": 1,
            "template_key": "ppe-violation-webhook.v1",
            "event_types": ["missing_hardhat", "missing_safety_vest"],
            "deduplication_window_seconds": 60,
        }
    ]

    invalid_key = client.post(
        "/api/v1/internal/inference/workspaces/training-space/endpoints/helmet-detector:resolve",
        headers={**gateway_headers, "X-API-Key": "smu_live_invalid-key"},
    )
    assert invalid_key.status_code == 401

    usage_payload = {
        "deployment_id": deployment["id"],
        "request_id": "request-metering-001",
        "capability_id": "vision.predict",
        "billable_units": 2,
        "unit": "image",
        "dimensions": {"contract": "detections.v1", "input_count": 2},
        "occurred_at": occurred_at,
    }
    usage = client.post(
        "/api/v1/internal/inference/usage-records",
        headers={"X-SenseMu-Gateway-Token": "sensemu-gateway-local-only"},
        json=usage_payload,
    )
    assert usage.status_code == 200
    assert usage.json()["reused"] is False
    repeated_usage = client.post(
        "/api/v1/internal/inference/usage-records",
        headers={"X-SenseMu-Gateway-Token": "sensemu-gateway-local-only"},
        json=usage_payload,
    )
    assert repeated_usage.status_code == 200
    assert repeated_usage.json()["reused"] is True
    metered_deployment = client.get(
        f"/api/v1/projects/{project['id']}/deployments",
        headers=workspace_headers,
    ).json()[0]
    assert metered_deployment["request_count"] == 1
    assert metered_deployment["billable_units"] == 2
    metered_overview = client.get("/api/v1/overview", headers=workspace_headers).json()
    assert metered_overview["metrics"]["inference_calls_month"] == 1

    rotated = client.post(
        f"/api/v1/deployments/{deployment['id']}:rotate-key",
        headers=workspace_headers,
    )
    assert rotated.status_code == 200
    rotated_api_key = rotated.json()["api_key"]
    assert rotated_api_key != original_api_key
    old_key_rejected = client.post(
        "/api/v1/internal/inference/workspaces/training-space/endpoints/helmet-detector:resolve",
        headers=gateway_headers,
    )
    assert old_key_rejected.status_code == 401
    new_key_resolved = client.post(
        "/api/v1/internal/inference/workspaces/training-space/endpoints/helmet-detector:resolve",
        headers={**gateway_headers, "X-API-Key": rotated_api_key},
    )
    assert new_key_resolved.status_code == 200

    disabled = client.post(
        f"/api/v1/deployments/{deployment['id']}:disable",
        headers=workspace_headers,
    )
    assert disabled.status_code == 200
    assert disabled.json()["status"] == "disabled"
    disabled_resolution = client.post(
        "/api/v1/internal/inference/workspaces/training-space/endpoints/helmet-detector:resolve",
        headers={**gateway_headers, "X-API-Key": rotated_api_key},
    )
    assert disabled_resolution.status_code == 404
    enabled = client.post(
        f"/api/v1/deployments/{deployment['id']}:enable",
        headers=workspace_headers,
    )
    assert enabled.status_code == 200
    assert enabled.json()["status"] == "published"

    stale_run = client.post(
        f"/api/v1/projects/{project['id']}/training-runs",
        headers={
            **workspace_headers,
            "Idempotency-Key": "training-test-request-003",
        },
        json=payload,
    ).json()
    stale_attempt_id = str(uuid4())
    stale_claim = client.post(
        f"/api/v1/internal/training-runs/{stale_run['id']}/execution:claim",
        headers=worker_headers,
        json={"attempt_id": stale_attempt_id, "worker_id": "lost-worker"},
    )
    assert stale_claim.status_code == 200
    with TestingSession() as session:
        stored_run = session.get(models.Run, UUID(stale_run["id"]))
        assert stored_run is not None
        stored_run.heartbeat_at = datetime.now(UTC) - timedelta(minutes=5)
        session.commit()

    recovered = client.post(
        "/api/v1/internal/training-runs/executions:recover-stale",
        headers={"X-SenseMu-Worker-Token": "sensemu-worker-local-only"},
    )
    assert recovered.status_code == 200
    assert recovered.json()["recovered"] == [
        {
            "workspace_id": workspace["id"],
            "run_id": stale_run["id"],
            "action": "requeued",
            "execution_attempt": 1,
        }
    ]
    assert fake_dispatcher.submissions[-1] == (workspace["id"], stale_run["id"])
    after_recovery = client.get(
        f"/api/v1/training-runs/{stale_run['id']}",
        headers=workspace_headers,
    ).json()
    assert after_recovery["status"] == "queued"
    assert after_recovery["progress"] == 0
    assert after_recovery["heartbeat_at"] is None
    stale_events = client.get(
        f"/api/v1/training-runs/{stale_run['id']}/events",
        headers=workspace_headers,
    ).json()
    assert [event["event_type"] for event in stale_events][-1] == "job.lease_expired"
    old_attempt_rejected = client.post(
        f"/api/v1/internal/training-runs/{stale_run['id']}/execution:heartbeat",
        headers=worker_headers,
        json={"attempt_id": stale_attempt_id},
    )
    assert old_attempt_rejected.status_code == 409

    replacement_attempt_id = str(uuid4())
    replacement_claim = client.post(
        f"/api/v1/internal/training-runs/{stale_run['id']}/execution:claim",
        headers=worker_headers,
        json={"attempt_id": replacement_attempt_id, "worker_id": "replacement-worker"},
    )
    assert replacement_claim.status_code == 200
    assert replacement_claim.json()["status"] == "preparing"
    cancel_replacement = client.post(
        f"/api/v1/training-runs/{stale_run['id']}:cancel",
        headers=workspace_headers,
    )
    assert cancel_replacement.status_code == 200
    assert cancel_replacement.json()["status"] == "cancel_requested"
    with TestingSession() as session:
        stored_run = session.get(models.Run, UUID(stale_run["id"]))
        assert stored_run is not None
        stored_run.heartbeat_at = datetime.now(UTC) - timedelta(minutes=5)
        session.commit()
    cancelled_recovery = client.post(
        "/api/v1/internal/training-runs/executions:recover-stale",
        headers={"X-SenseMu-Worker-Token": "sensemu-worker-local-only"},
    )
    assert cancelled_recovery.status_code == 200
    assert cancelled_recovery.json()["recovered"][0]["action"] == "cancelled"
    final_stale_run = client.get(
        f"/api/v1/training-runs/{stale_run['id']}",
        headers=workspace_headers,
    ).json()
    assert final_stale_run["status"] == "cancelled"

    exhausted_run = client.post(
        f"/api/v1/projects/{project['id']}/training-runs",
        headers={
            **workspace_headers,
            "Idempotency-Key": "training-test-request-004",
        },
        json=payload,
    ).json()
    exhausted_attempt_id = str(uuid4())
    exhausted_claim = client.post(
        f"/api/v1/internal/training-runs/{exhausted_run['id']}/execution:claim",
        headers=worker_headers,
        json={"attempt_id": exhausted_attempt_id, "worker_id": "unstable-worker"},
    )
    assert exhausted_claim.status_code == 200
    with TestingSession() as session:
        stored_run = session.get(models.Run, UUID(exhausted_run["id"]))
        assert stored_run is not None
        stored_run.execution_attempt = 3
        stored_run.heartbeat_at = datetime.now(UTC) - timedelta(minutes=5)
        session.commit()
    exhausted_recovery = client.post(
        "/api/v1/internal/training-runs/executions:recover-stale",
        headers={"X-SenseMu-Worker-Token": "sensemu-worker-local-only"},
    )
    assert exhausted_recovery.status_code == 200
    assert exhausted_recovery.json()["recovered"][0]["action"] == "failed"
    exhausted_result = client.get(
        f"/api/v1/training-runs/{exhausted_run['id']}",
        headers=workspace_headers,
    ).json()
    assert exhausted_result["status"] == "failed"
    assert exhausted_result["error_code"] == "execution_lease_exhausted"

    superseding_policy = client.post(
        f"/api/v1/projects/{project['id']}/evaluation-policies",
        headers=workspace_headers,
        json={
            "name": "Helmet next release gate",
            "rules": [
                {
                    "metric": "metrics/mAP50(B)",
                    "operator": ">=",
                    "threshold": 0.85,
                    "label": "next release mAP50",
                }
            ],
        },
    )
    assert superseding_policy.status_code == 201
    invalidated_model = client.get(
        f"/api/v1/projects/{project['id']}/model-versions",
        headers=workspace_headers,
    ).json()[0]
    assert invalidated_model["status"] == "candidate"
    stale_acceptance_deployment = client.post(
        f"/api/v1/projects/{project['id']}/deployments",
        headers=workspace_headers,
        json={
            "model_version_id": completion.json()["id"],
            "name": "Stale acceptance service",
            "endpoint_slug": "stale-acceptance-service",
            "environment": "production",
        },
    )
    assert stale_acceptance_deployment.status_code == 409


def test_annotation_task_persists_asset_snapshot_and_progress() -> None:
    workspace_response = client.post(
        "/api/v1/workspaces",
        json={"slug": "annotation-task-test", "name": "Annotation Task Test"},
    )
    assert workspace_response.status_code == 201
    workspace = workspace_response.json()
    headers = {"X-Workspace-ID": workspace["id"]}
    project_response = client.post(
        "/api/v1/projects",
        headers=headers,
        json={"slug": "annotation-project", "name": "Annotation Project", "task_type": "object-detection"},
    )
    assert project_response.status_code == 201
    dataset_response = client.post(
        f"/api/v1/projects/{project_response.json()['id']}/datasets",
        headers=headers,
        json={"name": "frames"},
    )
    assert dataset_response.status_code == 201
    dataset_id = dataset_response.json()["id"]
    missing_classes = client.post(
        f"/api/v1/datasets/{dataset_id}/annotation-tasks",
        headers=headers,
        json={"name": "缺少类别表", "method": "manual", "asset_scope": "all"},
    )
    assert missing_classes.status_code == 409
    assert "类别" in missing_classes.json()["detail"]
    saved_classes = client.patch(
        f"/api/v1/datasets/{dataset_id}/classes",
        headers=headers,
        json={"class_map": {"0": "helmet"}},
    )
    assert saved_classes.status_code == 200
    assert saved_classes.json()["class_map"] == {"0": "helmet"}
    asset = register_image(dataset_id, headers, checksum="a" * 64, filename="frame.png")
    prepare_detection_item(dataset_id, asset, headers, split="train")
    asset_two = register_image(dataset_id, headers, checksum="b" * 64, filename="frame-2.png")
    task_response = client.post(
        f"/api/v1/datasets/{dataset_id}/annotation-tasks",
        headers=headers,
        json={
            "name": "未标注帧",
            "method": "manual",
            "asset_scope": "unlabeled",
            "class_map": {"0": "helmet"},
        },
    )
    assert task_response.status_code == 201
    task = task_response.json()
    assert task["asset_count"] == 1
    assert task["completed_count"] == 0
    task_assets = client.get(
        f"/api/v1/datasets/{dataset_id}/annotation-tasks/{task['id']}/assets",
        headers=headers,
    )
    assert task_assets.status_code == 200
    assert [item["id"] for item in task_assets.json()] == [asset_two["id"]]
    blocked_smart = client.post(
        f"/api/v1/datasets/{dataset_id}/annotation-tasks",
        headers=headers,
        json={"name": "智能任务", "method": "smart", "asset_scope": "all"},
    )
    assert blocked_smart.status_code == 409
    complete_before_annotation = client.patch(
        f"/api/v1/datasets/{dataset_id}/annotation-tasks/{task['id']}",
        headers=headers,
        json={"status": "done"},
    )
    assert complete_before_annotation.status_code == 409
    prepare_detection_item(dataset_id, asset_two, headers, split="train")
    completed = client.patch(
        f"/api/v1/datasets/{dataset_id}/annotation-tasks/{task['id']}",
        headers=headers,
        json={"status": "done"},
    )
    assert completed.status_code == 200
    assert completed.json()["completed_count"] == 1
    valid_asset = register_image(dataset_id, headers, checksum="c" * 64, filename="frame-valid.png")
    prepare_detection_item(dataset_id, valid_asset, headers, split="valid")
    pending_review = client.post(
        f"/api/v1/datasets/{dataset_id}/annotation-tasks",
        headers=headers,
        json={
            "name": "冻结前检查",
            "method": "manual",
            "asset_scope": "all",
            "class_map": {"0": "helmet"},
        },
    )
    assert pending_review.status_code == 201
    blocked_freeze = client.post(
        f"/api/v1/datasets/{dataset_id}/versions:freeze",
        headers=headers,
        json={"class_map": {"0": "helmet"}},
    )
    assert blocked_freeze.status_code == 409
    assert "冻结前检查" in blocked_freeze.json()["detail"]
    completed_review = client.patch(
        f"/api/v1/datasets/{dataset_id}/annotation-tasks/{pending_review.json()['id']}",
        headers=headers,
        json={"status": "done"},
    )
    assert completed_review.status_code == 200
    freeze_after_review = client.post(
        f"/api/v1/datasets/{dataset_id}/versions:freeze",
        headers=headers,
        json={"class_map": {"0": "helmet"}},
    )
    assert freeze_after_review.status_code == 201
    blocked_class_change = client.patch(
        f"/api/v1/datasets/{dataset_id}/classes",
        headers=headers,
        json={"class_map": {"0": "headgear"}},
    )
    assert blocked_class_change.status_code == 409


def _replace_zip_entry(package: bytes, entry_name: str, body: bytes) -> bytes:
    output = BytesIO()
    with ZipFile(BytesIO(package)) as source, ZipFile(
        output,
        "w",
        compression=ZIP_DEFLATED,
    ) as destination:
        for info in source.infolist():
            destination.writestr(
                info.filename,
                body if info.filename == entry_name else source.read(info.filename),
            )
    return output.getvalue()


def test_annotation_task_yolo_package_export_and_validated_import() -> None:
    workspace = client.post(
        "/api/v1/workspaces",
        json={"slug": "annotation-package-test", "name": "Annotation Package Test"},
    ).json()
    headers = {"X-Workspace-ID": workspace["id"]}
    project = client.post(
        "/api/v1/projects",
        headers=headers,
        json={
            "slug": "annotation-package-project",
            "name": "Annotation Package Project",
            "task_type": "object-detection",
        },
    ).json()
    dataset = client.post(
        f"/api/v1/projects/{project['id']}/datasets",
        headers=headers,
        json={"name": "external-labeling"},
    ).json()
    image_body = b"p" * 2048
    asset = register_image(
        dataset["id"],
        headers,
        checksum=sha256(image_body).hexdigest(),
        filename="package-frame.png",
    )
    fake_storage.objects[asset["uri"].removeprefix(f"s3://{fake_storage.bucket}/")] = image_body
    task_response = client.post(
        f"/api/v1/datasets/{dataset['id']}/annotation-tasks",
        headers=headers,
        json={
            "name": "外部标注任务",
            "method": "manual",
            "asset_scope": "all",
            "class_map": {"0": "person", "1": "helmet"},
        },
    )
    assert task_response.status_code == 201
    task = task_response.json()
    assert task["class_map"] == {"0": "person", "1": "helmet"}

    exported = client.get(
        f"/api/v1/datasets/{dataset['id']}/annotation-tasks/{task['id']}/yolo-package",
        headers=headers,
    )
    assert exported.status_code == 200
    assert exported.headers["content-type"] == "application/zip"
    with ZipFile(BytesIO(exported.content)) as archive:
        manifest = json.loads(archive.read("sensemu-task.json"))
        assert manifest["task"]["id"] == task["id"]
        assert manifest["class_map"] == task["class_map"]
        image_path = manifest["assets"][0]["image_path"]
        label_path = manifest["assets"][0]["label_path"]
        assert archive.read(image_path) == image_body
        assert archive.read(label_path) == b""
        assert b"0: \"person\"" in archive.read("data.yaml")

    def import_package(package: bytes, suffix: str):
        checksum = sha256(package).hexdigest()
        intent_response = client.post(
            (
                f"/api/v1/datasets/{dataset['id']}/annotation-tasks/{task['id']}"
                "/yolo-import-uploads"
            ),
            headers=headers,
            json={
                "filename": f"external-{suffix}.zip",
                "byte_size": len(package),
                "checksum_sha256": checksum,
            },
        )
        assert intent_response.status_code == 201
        intent = intent_response.json()
        fake_storage.objects[intent["object_key"]] = package
        return client.post(
            (
                f"/api/v1/datasets/{dataset['id']}/annotation-tasks/{task['id']}"
                "/yolo-import"
            ),
            headers=headers,
            json={
                "object_key": intent["object_key"],
                "byte_size": len(package),
                "checksum_sha256": checksum,
            },
        )

    tampered_image_package = _replace_zip_entry(exported.content, image_path, b"x" * 2048)
    tampered_image_response = import_package(tampered_image_package, "bad-image")
    assert tampered_image_response.status_code == 409
    assert "图片与原始素材不一致" in tampered_image_response.json()["detail"]

    invalid_class_package = _replace_zip_entry(exported.content, label_path, b"2 0.5 0.5 0.2 0.2\n")
    invalid_class_response = import_package(invalid_class_package, "bad-class")
    assert invalid_class_response.status_code == 409
    assert "未定义类别 2" in invalid_class_response.json()["detail"]

    label_body = b"1 0.5 0.5 0.2 0.2\n"
    completed_package = _replace_zip_entry(exported.content, label_path, label_body)
    imported = import_package(completed_package, "complete")
    assert imported.status_code == 200
    assert imported.json()["imported_asset_count"] == 1
    assert imported.json()["task"]["completed_count"] == 1
    assert imported.json()["task"]["asset_count"] == 1
    annotation = client.get(
        f"/api/v1/datasets/{dataset['id']}/items/{asset['id']}/annotation",
        headers=headers,
    )
    assert annotation.status_code == 200
    assert annotation.content == label_body
