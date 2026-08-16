from pathlib import Path
from types import SimpleNamespace

from sensemu_worker import tasks


class FakeVideoAPI:
    def __init__(self, *, cancel_requested: bool = False) -> None:
        self.cancel_requested = cancel_requested
        self.heartbeats: list[tuple[str, str, str]] = []
        self.events: list[str] = []
        self.completed: list[list[dict]] = []

    def claim_video_extraction(
        self,
        workspace_id: str,
        job_id: str,
        attempt_id: str,
        worker_id: str,
    ) -> dict:
        del workspace_id, job_id, attempt_id, worker_id
        return {
            "job": {"status": "preparing"},
            "job_spec": {
                "source": {"uri": "local://source-video", "media_type": "video/mp4"},
                "recipe": {"frame_interval_ms": 1_000, "deduplicate": True},
                "artifact_prefix": "workspaces/workspace/datasets/dataset/video-extractions/job",
            },
        }

    def heartbeat_video_extraction(
        self,
        workspace_id: str,
        job_id: str,
        attempt_id: str,
    ) -> dict:
        self.heartbeats.append((workspace_id, job_id, attempt_id))
        return {"status": "running"}

    def video_extraction_event(
        self,
        workspace_id: str,
        job_id: str,
        attempt_id: str,
        event_type: str,
        **_kwargs: object,
    ) -> dict:
        del workspace_id, job_id, attempt_id
        self.events.append(event_type)
        return {"status": "running"}

    def get_video_extraction(self, workspace_id: str, job_id: str) -> dict:
        del workspace_id, job_id
        return {"status": "cancel_requested" if self.cancel_requested else "running"}

    def complete_video_extraction(
        self,
        workspace_id: str,
        job_id: str,
        attempt_id: str,
        frames: list[dict],
    ) -> dict:
        del workspace_id, job_id, attempt_id
        self.completed.append(frames)
        return {"status": "succeeded"}


class FakeObjectStore:
    def materialize(self, _uri: str, target: Path) -> None:
        target.write_bytes(b"video")

    def upload(self, frame: Path, key: str, media_type: str) -> str:
        assert media_type == "image/jpeg"
        assert frame.is_file()
        return f"local://{key}"


def _prepare_worker(monkeypatch, api: FakeVideoAPI, tmp_path: Path) -> None:
    monkeypatch.setattr(
        tasks.WorkerSettings,
        "from_environment",
        lambda: SimpleNamespace(lease_heartbeat_interval_seconds=3_600),
    )
    monkeypatch.setattr(tasks, "WorkerAPIClient", lambda _settings: api)
    monkeypatch.setattr(tasks, "create_object_store", lambda _settings: FakeObjectStore())

    def extract(
        _source: Path,
        output: Path,
        *,
        frame_interval_ms: int,
        deduplicate: bool,
        on_progress,
    ) -> tuple[list[Path], tuple[int, int], int]:
        assert frame_interval_ms == 1_000
        assert deduplicate is True
        output.mkdir()
        first = output / "frame-000001.jpg"
        second = output / "frame-000002.jpg"
        first.write_bytes(b"first")
        second.write_bytes(b"second")
        on_progress(75)
        return [first, second], (1280, 720), 2_000

    monkeypatch.setattr(tasks, "extract_frames", extract)


def test_video_extraction_worker_heartbeats_and_completes(monkeypatch, tmp_path: Path) -> None:
    api = FakeVideoAPI()
    _prepare_worker(monkeypatch, api, tmp_path)

    result = tasks.execute_video_extraction.run(
        workspace_id="workspace",
        job_id="job-12345678",
        attempt_id="attempt-12345678",
    )

    assert result == {"job_id": "job-12345678", "status": "succeeded", "frames_created": 2}
    assert api.heartbeats == [("workspace", "job-12345678", "attempt-12345678")]
    assert api.events == ["job.started", "job.progressed"]
    assert len(api.completed) == 1
    assert len(api.completed[0]) == 2


def test_video_extraction_worker_stops_when_cancel_is_requested(monkeypatch, tmp_path: Path) -> None:
    api = FakeVideoAPI(cancel_requested=True)
    _prepare_worker(monkeypatch, api, tmp_path)

    result = tasks.execute_video_extraction.run(
        workspace_id="workspace",
        job_id="job-12345678",
        attempt_id="attempt-12345678",
    )

    assert result == {"job_id": "job-12345678", "status": "cancelled"}
    assert api.events == ["job.started", "job.cancelled"]
    assert api.completed == []
