from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from sensemu_api.db import Base
from sensemu_api.db.models import VideoExtractionJob
from sensemu_api.db.session import get_session
from sensemu_api.main import create_app
from sensemu_api.storage import get_storage
from sensemu_api.video_extraction_dispatch import get_video_extraction_dispatcher


class MemoryStorage:
    bucket = "sensemu-video-test"

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def presign_put(
        self,
        key: str,
        content_type: str,
        checksum_sha256: str,
        expires_in: int = 900,
    ) -> str:
        del content_type, checksum_sha256, expires_in
        return f"https://uploads.example.test/{key}"

    def uri_for(self, key: str) -> str:
        return f"s3://{self.bucket}/{key}"

    def put_bytes(
        self,
        key: str,
        payload: bytes,
        content_type: str = "application/octet-stream",
    ) -> str:
        del content_type
        self.objects[key] = payload
        return self.uri_for(key)

    def put_json(self, key: str, payload: dict) -> str:
        return self.put_bytes(key, b"{}", "application/json")

    def get_bytes(self, uri: str) -> bytes:
        return self.objects[uri.removeprefix(f"s3://{self.bucket}/")]

    def get_json(self, uri: str) -> dict:
        del uri
        return {}

    def check_ready(self) -> None:
        return None

    def verify_object(self, key: str, byte_size: int, checksum_sha256: str) -> bool:
        del checksum_sha256
        return len(self.objects.get(key, b"")) == byte_size


class FakeDispatcher:
    def __init__(self) -> None:
        self.submissions: list[tuple[str, str]] = []

    def submit(self, workspace_id: UUID, job_id: UUID) -> None:
        self.submissions.append((str(workspace_id), str(job_id)))


def _client() -> tuple[TestClient, MemoryStorage, FakeDispatcher, sessionmaker[Session]]:
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
    application.dependency_overrides[get_video_extraction_dispatcher] = lambda: dispatcher
    return TestClient(application), storage, dispatcher, sessions


def _seed_video(client: TestClient, storage: MemoryStorage) -> tuple[dict, dict, dict, dict]:
    workspace = client.post(
        "/api/v1/workspaces",
        json={"slug": "video-workspace", "name": "视频工作区"},
    ).json()
    headers = {"X-Workspace-ID": workspace["id"]}
    project = client.post(
        "/api/v1/projects",
        headers=headers,
        json={
            "slug": "video-project",
            "name": "视频项目",
            "task_type": "object-detection",
        },
    ).json()
    dataset = client.post(
        f"/api/v1/projects/{project['id']}/datasets",
        headers=headers,
        json={"name": "视频帧数据集"},
    ).json()
    video_checksum = "a" * 64
    intent = client.post(
        f"/api/v1/datasets/{dataset['id']}/uploads",
        headers=headers,
        json={
            "filename": "camera.mp4",
            "content_type": "video/mp4",
            "byte_size": 1024,
            "checksum_sha256": video_checksum,
        },
    ).json()
    storage.objects[intent["object_key"]] = b"v" * 1024
    source = client.post(
        f"/api/v1/datasets/{dataset['id']}/assets",
        headers=headers,
        json={
            "object_key": intent["object_key"],
            "media_type": "video/mp4",
            "checksum_sha256": video_checksum,
            "byte_size": 1024,
            "width": None,
            "height": None,
        },
    ).json()
    return workspace, dataset, source, headers


def test_video_extraction_writes_frames_back_as_training_assets() -> None:
    client, storage, dispatcher, _sessions = _client()
    workspace, dataset, source, headers = _seed_video(client, storage)

    assert client.get(f"/api/v1/datasets/{dataset['id']}/assets", headers=headers).json() == []
    source_videos = client.get(
        f"/api/v1/datasets/{dataset['id']}/source-videos",
        headers=headers,
    ).json()
    assert [item["id"] for item in source_videos] == [source["id"]]

    created = client.post(
        f"/api/v1/datasets/{dataset['id']}/video-extractions",
        headers={**headers, "Idempotency-Key": "extract-camera-001"},
        json={
            "source_asset_id": source["id"],
            "frame_interval_ms": 1_000,
            "deduplicate": True,
        },
    )
    assert created.status_code == 201
    job = created.json()
    assert job["status"] == "queued"
    assert dispatcher.submissions == [(workspace["id"], job["id"])]

    repeated = client.post(
        f"/api/v1/datasets/{dataset['id']}/video-extractions",
        headers={**headers, "Idempotency-Key": "extract-camera-001"},
        json={
            "source_asset_id": source["id"],
            "frame_interval_ms": 1_000,
            "deduplicate": True,
        },
    )
    assert repeated.status_code == 201
    assert repeated.json()["id"] == job["id"]

    worker_headers = {
        **headers,
        "X-SenseMu-Worker-Token": "sensemu-worker-local-only",
    }
    attempt_id = str(uuid4())
    claim = client.post(
        f"/api/v1/internal/video-extractions/{job['id']}/execution:claim",
        headers=worker_headers,
        json={"attempt_id": attempt_id, "worker_id": "video-worker"},
    )
    assert claim.status_code == 200
    assert claim.json()["job_spec"]["source"]["asset_id"] == source["id"]

    started = client.post(
        f"/api/v1/internal/video-extractions/{job['id']}/events",
        headers=worker_headers,
        json={"attempt_id": attempt_id, "event_type": "job.started"},
    )
    assert started.status_code == 200

    frame_key = (
        f"workspaces/{workspace['id']}/datasets/{dataset['id']}/"
        f"video-extractions/{job['id']}/frames/frame-000001.jpg"
    )
    storage.objects[frame_key] = b"frame"
    completed = client.post(
        f"/api/v1/internal/video-extractions/{job['id']}/complete",
        headers=worker_headers,
        json={
            "attempt_id": attempt_id,
            "occurred_at": datetime.now(UTC).isoformat(),
            "frames": [
                {
                    "object_uri": storage.uri_for(frame_key),
                    "media_type": "image/jpeg",
                    "checksum_sha256": "b" * 64,
                    "byte_size": 5,
                    "width": 1280,
                    "height": 720,
                    "frame_index": 0,
                    "timestamp_ms": 0,
                }
            ],
        },
    )
    assert completed.status_code == 200
    assert completed.json()["status"] == "succeeded"
    assert completed.json()["frames_created"] == 1

    assets = client.get(f"/api/v1/datasets/{dataset['id']}/assets", headers=headers).json()
    assert len(assets) == 1
    assert assets[0]["media_type"] == "image/jpeg"
    assert assets[0]["width"] == 1280

    unrelated_checksum = "c" * 64
    unrelated_intent = client.post(
        f"/api/v1/datasets/{dataset['id']}/uploads",
        headers=headers,
        json={
            "filename": "unrelated.jpg",
            "content_type": "image/jpeg",
            "byte_size": 7,
            "checksum_sha256": unrelated_checksum,
        },
    ).json()
    storage.objects[unrelated_intent["object_key"]] = b"outside"
    unrelated = client.post(
        f"/api/v1/datasets/{dataset['id']}/assets",
        headers=headers,
        json={
            "object_key": unrelated_intent["object_key"],
            "media_type": "image/jpeg",
            "checksum_sha256": unrelated_checksum,
            "byte_size": 7,
            "width": 640,
            "height": 360,
        },
    )
    assert unrelated.status_code == 201

    task_response = client.put(
        f"/api/v1/datasets/{dataset['id']}/video-extractions/{job['id']}/annotation-task",
        headers=headers,
        json={"name": "camera.mp4 抽帧标注", "class_map": {"0": "person"}},
    )
    assert task_response.status_code == 200
    task = task_response.json()
    assert task["asset_scope"] == "video_extraction"
    assert task["source_video_extraction_job_id"] == job["id"]
    assert task["asset_count"] == 1
    task_assets = client.get(
        f"/api/v1/datasets/{dataset['id']}/annotation-tasks/{task['id']}/assets",
        headers=headers,
    ).json()
    assert [item["id"] for item in task_assets] == [assets[0]["id"]]

    repeated_task = client.put(
        f"/api/v1/datasets/{dataset['id']}/video-extractions/{job['id']}/annotation-task",
        headers=headers,
        json={"name": "重复点击不会新建"},
    )
    assert repeated_task.status_code == 200
    assert repeated_task.json()["id"] == task["id"]


def test_video_extraction_validates_interval_and_can_cancel_queued_job() -> None:
    client, storage, _dispatcher, _sessions = _client()
    _workspace, dataset, source, headers = _seed_video(client, storage)
    invalid = client.post(
        f"/api/v1/datasets/{dataset['id']}/video-extractions",
        headers={**headers, "Idempotency-Key": "extract-invalid-001"},
        json={"source_asset_id": source["id"], "frame_interval_ms": 50},
    )
    assert invalid.status_code == 422

    created = client.post(
        f"/api/v1/datasets/{dataset['id']}/video-extractions",
        headers={**headers, "Idempotency-Key": "extract-cancel-001"},
        json={"source_asset_id": source["id"], "frame_interval_ms": 2_000},
    ).json()
    cancelled = client.post(
        f"/api/v1/video-extractions/{created['id']}:cancel",
        headers=headers,
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"


def test_video_extraction_recovers_stale_attempt_and_rejects_old_worker() -> None:
    client, storage, _dispatcher, sessions = _client()
    workspace, dataset, source, headers = _seed_video(client, storage)
    created = client.post(
        f"/api/v1/datasets/{dataset['id']}/video-extractions",
        headers={**headers, "Idempotency-Key": "extract-recovery-001"},
        json={"source_asset_id": source["id"], "frame_interval_ms": 2_000},
    ).json()
    worker_headers = {
        **headers,
        "X-SenseMu-Worker-Token": "sensemu-worker-local-only",
    }
    old_attempt = str(uuid4())
    claimed = client.post(
        f"/api/v1/internal/video-extractions/{created['id']}/execution:claim",
        headers=worker_headers,
        json={"attempt_id": old_attempt, "worker_id": "stale-video-worker"},
    )
    assert claimed.status_code == 200
    with sessions() as session:
        stored = session.get(VideoExtractionJob, UUID(created["id"]))
        assert stored is not None
        stored.heartbeat_at = datetime.now(UTC) - timedelta(minutes=5)
        session.commit()

    recovered = client.post(
        "/api/v1/internal/video-extractions/executions:recover-stale",
        headers={"X-SenseMu-Worker-Token": "sensemu-worker-local-only"},
    )
    assert recovered.status_code == 200
    assert recovered.json()["recovered"] == [
        {
            "workspace_id": workspace["id"],
            "job_id": created["id"],
            "action": "requeued",
            "execution_attempt": 1,
        }
    ]
    old_heartbeat = client.post(
        f"/api/v1/internal/video-extractions/{created['id']}/execution:heartbeat",
        headers=worker_headers,
        json={"attempt_id": old_attempt},
    )
    assert old_heartbeat.status_code == 409
    replacement = client.post(
        f"/api/v1/internal/video-extractions/{created['id']}/execution:claim",
        headers=worker_headers,
        json={"attempt_id": str(uuid4()), "worker_id": "replacement-video-worker"},
    )
    assert replacement.status_code == 200


def test_video_extraction_cancelled_before_completion_does_not_register_frames() -> None:
    client, storage, _dispatcher, _sessions = _client()
    workspace, dataset, source, headers = _seed_video(client, storage)
    created = client.post(
        f"/api/v1/datasets/{dataset['id']}/video-extractions",
        headers={**headers, "Idempotency-Key": "extract-cancel-running-001"},
        json={"source_asset_id": source["id"], "frame_interval_ms": 2_000},
    ).json()
    worker_headers = {
        **headers,
        "X-SenseMu-Worker-Token": "sensemu-worker-local-only",
    }
    attempt_id = str(uuid4())
    client.post(
        f"/api/v1/internal/video-extractions/{created['id']}/execution:claim",
        headers=worker_headers,
        json={"attempt_id": attempt_id, "worker_id": "video-worker"},
    )
    client.post(
        f"/api/v1/internal/video-extractions/{created['id']}/events",
        headers=worker_headers,
        json={"attempt_id": attempt_id, "event_type": "job.started"},
    )
    requested = client.post(
        f"/api/v1/video-extractions/{created['id']}:cancel",
        headers=headers,
    )
    assert requested.status_code == 200
    assert requested.json()["status"] == "cancel_requested"
    frame_key = (
        f"workspaces/{workspace['id']}/datasets/{dataset['id']}/"
        f"video-extractions/{created['id']}/frames/frame-000001.jpg"
    )
    storage.objects[frame_key] = b"frame"
    completion = client.post(
        f"/api/v1/internal/video-extractions/{created['id']}/complete",
        headers=worker_headers,
        json={
            "attempt_id": attempt_id,
            "occurred_at": datetime.now(UTC).isoformat(),
            "frames": [
                {
                    "object_uri": storage.uri_for(frame_key),
                    "media_type": "image/jpeg",
                    "checksum_sha256": "b" * 64,
                    "byte_size": 5,
                    "width": 1280,
                    "height": 720,
                    "frame_index": 0,
                    "timestamp_ms": 0,
                }
            ],
        },
    )
    assert completion.status_code == 409
    assert client.get(f"/api/v1/datasets/{dataset['id']}/assets", headers=headers).json() == []
