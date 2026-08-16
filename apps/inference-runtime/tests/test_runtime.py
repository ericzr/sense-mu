from pathlib import Path
from typing import ClassVar

from fastapi.testclient import TestClient

from sensemu_runtime.main import create_app
from sensemu_runtime.service import ModelCache, PredictionService


class FakeStore:
    def __init__(self) -> None:
        self.materialized: list[str] = []

    def materialize(self, uri: str, destination: Path, max_bytes: int) -> None:
        del max_bytes
        self.materialized.append(uri)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(b"test")


class FakeTensor:
    def __init__(self, value) -> None:
        self.value = value

    def tolist(self):
        return self.value


class FakeBoxes:
    xyxy = FakeTensor([[10.0, 20.0, 110.0, 220.0]])
    conf = FakeTensor([0.91])
    cls = FakeTensor([0.0])


class FakeResult:
    boxes = FakeBoxes()
    names: ClassVar[dict[int, str]] = {0: "helmet"}
    orig_shape = (480, 640)


class FakePredictor:
    def __init__(self) -> None:
        self.calls: list[tuple[list[str], dict]] = []

    def __call__(self, sources: list[str], **kwargs):
        self.calls.append((sources, kwargs))
        return [FakeResult() for _ in sources]


def test_runtime_materializes_caches_and_serializes_detections(tmp_path: Path) -> None:
    store = FakeStore()
    predictor = FakePredictor()
    factory_calls: list[Path] = []

    def factory(path: Path) -> FakePredictor:
        factory_calls.append(path)
        return predictor

    cache = ModelCache(store, tmp_path / "cache", factory, 2, 1024)
    service = PredictionService(store, cache, device="cpu", max_input_bytes=512)
    client = TestClient(create_app(service))
    request = {
        "request_id": "request-runtime-001",
        "contract": "detections.v1",
        "model": {
            "version_id": "3bc78bb9-b9c1-4bee-bdb5-e0c1350ec4ae",
            "artifact_uri": "local://models/model-v1.pt",
            "task_type": "object-detection",
        },
        "inputs": ["local://inputs/yard.jpg"],
        "parameters": {"confidence": 0.4, "image_size": 640},
    }
    headers = {"X-SenseMu-Runtime-Token": "sensemu-runtime-local-only"}

    first = client.post("/v1/predict", headers=headers, json=request)
    second = client.post("/v1/predict", headers=headers, json=request)
    inline = client.post(
        "/v1/predict",
        headers=headers,
        json={**request, "inputs": ["data:image/png;base64,dGVzdA=="]},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert inline.status_code == 200
    assert inline.json()["predictions"][0]["input"] == "inline-image-1"
    prediction = first.json()["predictions"][0]
    assert prediction["width"] == 640
    assert prediction["height"] == 480
    assert prediction["detections"][0] == {
        "class_id": 0,
        "class_name": "helmet",
        "confidence": 0.91,
        "box": {"x1": 10.0, "y1": 20.0, "x2": 110.0, "y2": 220.0},
    }
    assert len(factory_calls) == 1
    assert store.materialized.count("local://models/model-v1.pt") == 1
    assert store.materialized.count("local://inputs/yard.jpg") == 2
    assert predictor.calls[0][1]["conf"] == 0.4


def test_runtime_rejects_unknown_parameters_and_credentials(tmp_path: Path) -> None:
    store = FakeStore()
    cache = ModelCache(store, tmp_path / "cache", lambda path: FakePredictor(), 1, 1024)
    client = TestClient(
        create_app(PredictionService(store, cache, device="cpu", max_input_bytes=512))
    )
    payload = {
        "request_id": "request-runtime-002",
        "contract": "detections.v1",
        "model": {
            "version_id": "3bc78bb9-b9c1-4bee-bdb5-e0c1350ec4ae",
            "artifact_uri": "local://models/model-v1.pt",
            "task_type": "object-detection",
        },
        "inputs": ["local://inputs/yard.jpg"],
        "parameters": {"arbitrary_command": "not-allowed"},
    }

    rejected_parameters = client.post(
        "/v1/predict",
        headers={"X-SenseMu-Runtime-Token": "sensemu-runtime-local-only"},
        json=payload,
    )
    rejected_token = client.post(
        "/v1/predict",
        headers={"X-SenseMu-Runtime-Token": "invalid-runtime-token"},
        json={**payload, "parameters": {}},
    )

    assert rejected_parameters.status_code == 422
    assert rejected_token.status_code == 403


def test_runtime_prewarms_model_and_reports_cache_capacity(tmp_path: Path) -> None:
    store = FakeStore()
    factory_calls: list[Path] = []

    def factory(path: Path) -> FakePredictor:
        factory_calls.append(path)
        return FakePredictor()

    cache = ModelCache(store, tmp_path / "cache", factory, 2, 1024)
    service = PredictionService(
        store,
        cache,
        device="cpu",
        max_input_bytes=512,
        max_concurrent_requests=2,
    )
    client = TestClient(create_app(service))
    payload = {
        "request_id": "request-prewarm-001",
        "contract": "detections.v1",
        "model": {
            "version_id": "3bc78bb9-b9c1-4bee-bdb5-e0c1350ec4ae",
            "artifact_uri": "local://models/model-v1.pt",
            "task_type": "object-detection",
        },
    }
    headers = {"X-SenseMu-Runtime-Token": "sensemu-runtime-local-only"}

    first = client.post("/v1/models:prewarm", headers=headers, json=payload)
    second = client.post("/v1/models:prewarm", headers=headers, json=payload)
    health = client.get("/health/ready")

    assert first.status_code == 200
    assert first.json()["cache_hit"] is False
    assert second.json()["cache_hit"] is True
    assert len(factory_calls) == 1
    assert health.json()["capacity"] == {
        "active_requests": 0,
        "waiting_requests": 0,
        "max_concurrent_requests": 2,
        "available_slots": 2,
    }
    assert health.json()["cache"]["loaded_models"] == 1


def test_runtime_rejects_when_capacity_is_full(tmp_path: Path) -> None:
    store = FakeStore()
    cache = ModelCache(store, tmp_path / "cache", lambda path: FakePredictor(), 1, 1024)
    service = PredictionService(
        store,
        cache,
        device="cpu",
        max_input_bytes=512,
        max_concurrent_requests=1,
        queue_timeout_seconds=0.001,
    )
    client = TestClient(create_app(service))
    payload = {
        "request_id": "request-runtime-busy-001",
        "contract": "detections.v1",
        "model": {
            "version_id": "3bc78bb9-b9c1-4bee-bdb5-e0c1350ec4ae",
            "artifact_uri": "local://models/model-v1.pt",
            "task_type": "object-detection",
        },
        "inputs": ["local://inputs/yard.jpg"],
    }

    with service._capacity_slot():
        response = client.post(
            "/v1/predict",
            headers={"X-SenseMu-Runtime-Token": "sensemu-runtime-local-only"},
            json=payload,
        )

    assert response.status_code == 429
    assert response.headers["retry-after"] == "1"
    assert response.json()["detail"]["code"] == "RUNTIME_BUSY"
