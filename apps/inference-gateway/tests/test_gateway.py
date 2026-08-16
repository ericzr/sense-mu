import json

import httpx
from fastapi.testclient import TestClient
from sensemu_gateway.config import get_settings
from sensemu_gateway.main import create_app


def test_live_health() -> None:
    client = TestClient(create_app())
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_predict_fails_closed_without_runtime(monkeypatch) -> None:
    monkeypatch.setenv("SENSEMU_GATEWAY_RUNTIME_URL", "")
    get_settings.cache_clear()

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["x-api-key"] == "smu_live_test-key"
        return httpx.Response(
            200,
            json={
                "deployment_id": "2bc78bb9-b9c1-4bee-bdb5-e0c1350ec4ae",
                "workspace_id": "1bc78bb9-b9c1-4bee-bdb5-e0c1350ec4ae",
                "workspace_slug": "sensemu-test",
                "endpoint_slug": "demo",
                "model_version_id": "3bc78bb9-b9c1-4bee-bdb5-e0c1350ec4ae",
                "artifact_uri": "s3://sensemu-dev/model.pt",
                "task_type": "object-detection",
                "contract": "detections.v1",
                "capability_id": "vision.predict",
            },
        )

    client = TestClient(create_app(httpx.MockTransport(handler)))
    response = client.post(
        "/inference/v1/workspaces/sensemu-test/endpoints/demo:predict",
        headers={"X-API-Key": "smu_live_test-key"},
        json={"inputs": ["s3://sensemu-dev/example.jpg"]},
    )
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "RUNTIME_NOT_CONFIGURED"


def test_predict_resolves_proxies_and_meters_once(monkeypatch) -> None:
    monkeypatch.setenv("SENSEMU_GATEWAY_RUNTIME_URL", "http://runtime.test")
    monkeypatch.setenv("SENSEMU_GATEWAY_CONTROL_PLANE_URL", "http://control.test")
    get_settings.cache_clear()
    observed: list[tuple[str, dict]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content) if request.content else {}
        observed.append((str(request.url), body))
        if request.url.path.endswith("demo:authorize"):
            assert request.headers["x-api-key"] == "smu_live_test-key"
            assert body["billable_units"] == 2
            assert request.headers["x-sensemu-gateway-token"]
            return httpx.Response(
                200,
                json={
                    "deployment_id": "2bc78bb9-b9c1-4bee-bdb5-e0c1350ec4ae",
                    "workspace_id": "1bc78bb9-b9c1-4bee-bdb5-e0c1350ec4ae",
                    "workspace_slug": "sensemu-test",
                    "endpoint_slug": "demo",
                    "model_version_id": "3bc78bb9-b9c1-4bee-bdb5-e0c1350ec4ae",
                    "artifact_uri": "s3://sensemu-dev/model.pt",
                    "task_type": "object-detection",
                    "contract": "detections.v1",
                    "capability_id": "vision.predict",
                },
            )
        if request.url.host == "runtime.test":
            assert body["request_id"] == "request-test-001"
            assert body["model"]["artifact_uri"] == "s3://sensemu-dev/model.pt"
            assert request.headers["x-sensemu-runtime-token"]
            return httpx.Response(200, json={"detections": [{"class": "helmet"}]})
        if request.url.path.endswith("usage-records"):
            assert body["request_id"] == "request-test-001"
            assert body["billable_units"] == 2
            return httpx.Response(200, json={"reused": False})
        return httpx.Response(404)

    client = TestClient(create_app(httpx.MockTransport(handler)))
    response = client.post(
        "/inference/v1/workspaces/sensemu-test/endpoints/demo:predict",
        headers={
            "X-API-Key": "smu_live_test-key",
            "X-Request-ID": "request-test-001",
        },
        json={
            "inputs": ["s3://sensemu-dev/a.jpg", "s3://sensemu-dev/b.jpg"],
            "parameters": {"confidence": 0.4},
        },
    )
    assert response.status_code == 200
    assert response.headers["x-request-id"] == "request-test-001"
    assert response.json()["contract"] == "detections.v1"
    assert response.json()["outputs"]["detections"][0]["class"] == "helmet"
    assert len(observed) == 3


def test_ready_reports_control_plane_runtime_cache_and_capacity(monkeypatch) -> None:
    monkeypatch.setenv("SENSEMU_GATEWAY_RUNTIME_URL", "http://runtime.test")
    monkeypatch.setenv("SENSEMU_GATEWAY_CONTROL_PLANE_URL", "http://control.test")
    get_settings.cache_clear()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "control.test":
            return httpx.Response(200, json={"status": "ready"})
        if request.url.host == "runtime.test":
            return httpx.Response(
                200,
                json={
                    "status": "ready",
                    "accepting_requests": True,
                    "cache": {"loaded_models": 1, "max_cached_models": 2},
                    "capacity": {
                        "active_requests": 0,
                        "waiting_requests": 0,
                        "max_concurrent_requests": 1,
                        "available_slots": 1,
                    },
                },
            )
        return httpx.Response(404)

    client = TestClient(create_app(httpx.MockTransport(handler)))
    response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json()["status"] == "ready"
    assert response.json()["control_plane"]["status"] == "ready"
    assert response.json()["runtime"]["cache"]["loaded_models"] == 1
    assert response.json()["runtime"]["capacity"]["available_slots"] == 1


def test_prewarm_resolves_and_loads_without_metering(monkeypatch) -> None:
    monkeypatch.setenv("SENSEMU_GATEWAY_RUNTIME_URL", "http://runtime.test")
    monkeypatch.setenv("SENSEMU_GATEWAY_CONTROL_PLANE_URL", "http://control.test")
    get_settings.cache_clear()
    observed_paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        observed_paths.append(request.url.path)
        if request.url.path.endswith("demo:resolve"):
            return httpx.Response(
                200,
                json={
                    "deployment_id": "2bc78bb9-b9c1-4bee-bdb5-e0c1350ec4ae",
                    "model_version_id": "3bc78bb9-b9c1-4bee-bdb5-e0c1350ec4ae",
                    "artifact_uri": "s3://sensemu-dev/model.pt",
                    "task_type": "object-detection",
                    "contract": "detections.v1",
                    "capability_id": "vision.predict",
                },
            )
        if request.url.path == "/v1/models:prewarm":
            body = json.loads(request.content)
            assert body["model"]["artifact_uri"] == "s3://sensemu-dev/model.pt"
            return httpx.Response(
                200,
                json={"cache_hit": False, "cache": {"loaded_models": 1}},
            )
        return httpx.Response(404)

    client = TestClient(create_app(httpx.MockTransport(handler)))
    response = client.post(
        "/inference/v1/workspaces/sensemu-test/endpoints/demo:prewarm",
        headers={
            "X-API-Key": "smu_live_test-key",
            "X-Request-ID": "request-prewarm-001",
        },
    )

    assert response.status_code == 200
    assert response.json()["runtime"]["cache_hit"] is False
    assert observed_paths == [
        "/api/v1/internal/inference/workspaces/sensemu-test/endpoints/demo:resolve",
        "/v1/models:prewarm",
    ]


def test_runtime_timeout_is_explicit_and_not_metered(monkeypatch) -> None:
    monkeypatch.setenv("SENSEMU_GATEWAY_RUNTIME_URL", "http://runtime.test")
    monkeypatch.setenv("SENSEMU_GATEWAY_CONTROL_PLANE_URL", "http://control.test")
    get_settings.cache_clear()
    observed_paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        observed_paths.append(request.url.path)
        if request.url.path.endswith("demo:authorize"):
            return httpx.Response(
                200,
                json={
                    "deployment_id": "2bc78bb9-b9c1-4bee-bdb5-e0c1350ec4ae",
                    "model_version_id": "3bc78bb9-b9c1-4bee-bdb5-e0c1350ec4ae",
                    "artifact_uri": "s3://sensemu-dev/model.pt",
                    "task_type": "object-detection",
                    "contract": "detections.v1",
                    "capability_id": "vision.predict",
                    "reservation_id": "4bc78bb9-b9c1-4bee-bdb5-e0c1350ec4ae",
                },
            )
        if request.url.host == "runtime.test":
            raise httpx.ReadTimeout("runtime timed out", request=request)
        if request.url.path.endswith(":release"):
            return httpx.Response(200, json={"status": "released"})
        return httpx.Response(404)

    client = TestClient(create_app(httpx.MockTransport(handler)))
    response = client.post(
        "/inference/v1/workspaces/sensemu-test/endpoints/demo:predict",
        headers={"X-API-Key": "smu_live_test-key"},
        json={"inputs": ["s3://sensemu-dev/example.jpg"]},
    )

    assert response.status_code == 504
    assert response.json()["detail"]["code"] == "RUNTIME_TIMEOUT"
    assert not any(path.endswith("usage-records") for path in observed_paths)
    assert any(path.endswith(":release") for path in observed_paths)


def test_marketplace_quota_failure_does_not_reach_runtime(monkeypatch) -> None:
    monkeypatch.setenv("SENSEMU_GATEWAY_RUNTIME_URL", "http://runtime.test")
    monkeypatch.setenv("SENSEMU_GATEWAY_CONTROL_PLANE_URL", "http://control.test")
    get_settings.cache_clear()
    observed_hosts: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        observed_hosts.append(request.url.host)
        if request.url.path.endswith("demo:authorize"):
            return httpx.Response(402, json={"detail": "调用额度已用尽"})
        return httpx.Response(500)

    client = TestClient(create_app(httpx.MockTransport(handler)))
    response = client.post(
        "/inference/v1/workspaces/sensemu-test/endpoints/demo:predict",
        headers={"X-API-Key": "smu_market_test-key"},
        json={"inputs": ["s3://sensemu-dev/example.jpg"]},
    )

    assert response.status_code == 402
    assert response.json()["detail"]["code"] == "QUOTA_EXHAUSTED"
    assert observed_hosts == ["control.test"]


def test_predict_dispatches_only_fixed_ppe_events_after_metering(monkeypatch) -> None:
    monkeypatch.setenv("SENSEMU_GATEWAY_RUNTIME_URL", "http://runtime.test")
    monkeypatch.setenv("SENSEMU_GATEWAY_CONTROL_PLANE_URL", "http://control.test")
    get_settings.cache_clear()
    dispatched_events: list[dict] = []
    workflow_one = "9bc78bb9-b9c1-4bee-bdb5-e0c1350ec4ae"
    workflow_two = "8bc78bb9-b9c1-4bee-bdb5-e0c1350ec4ae"

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content) if request.content else {}
        if request.url.path.endswith("demo:authorize"):
            return httpx.Response(
                200,
                json={
                    "deployment_id": "2bc78bb9-b9c1-4bee-bdb5-e0c1350ec4ae",
                    "model_version_id": "3bc78bb9-b9c1-4bee-bdb5-e0c1350ec4ae",
                    "artifact_uri": "s3://sensemu-dev/model.pt",
                    "task_type": "object-detection",
                    "contract": "detections.v1",
                    "capability_id": "vision.predict",
                    "workflow_bindings": [
                        {
                            "workflow_id": workflow_one,
                            "template_key": "ppe-violation-webhook.v1",
                            "event_types": ["missing_hardhat", "missing_safety_vest"],
                        },
                        {
                            "workflow_id": workflow_two,
                            "template_key": "ppe-violation-webhook.v1",
                            "event_types": ["missing_hardhat"],
                        },
                        {
                            "workflow_id": "7bc78bb9-b9c1-4bee-bdb5-e0c1350ec4ae",
                            "template_key": "unsupported-template.v1",
                            "event_types": ["missing_hardhat"],
                        },
                    ],
                },
            )
        if request.url.host == "runtime.test":
            return httpx.Response(
                200,
                json={
                    "predictions": [
                        {
                            "width": 1920,
                            "height": 1080,
                            "detections": [{"class_name": "person", "confidence": 0.91}],
                        }
                    ]
                },
            )
        if request.url.path.endswith("usage-records"):
            return httpx.Response(200, json={"reused": False})
        if request.url.path.endswith("vision-events"):
            dispatched_events.append(body)
            return httpx.Response(200, json={"reused": False})
        return httpx.Response(404)

    client = TestClient(create_app(httpx.MockTransport(handler)))
    raw_input = "data:image/jpeg;base64,do-not-leak-this-input"
    response = client.post(
        "/inference/v1/workspaces/sensemu-test/endpoints/demo:predict",
        headers={
            "X-API-Key": "smu_live_test-key",
            "X-Request-ID": "request-ppe-event-001",
        },
        json={
            "inputs": [raw_input],
            "event_context": {"source_id": "camera-north-gate", "source_type": "camera"},
        },
    )

    assert response.status_code == 200
    assert len(dispatched_events) == 3
    assert {event["event_type"] for event in dispatched_events} == {
        "missing_hardhat",
        "missing_safety_vest",
    }
    assert {event["deduplication_key"] for event in dispatched_events} == {
        "camera-north-gate.0"
    }
    assert {event["payload"]["source"]["id"] for event in dispatched_events} == {
        "camera-north-gate"
    }
    assert all(event["payload"]["frame"] == {
        "detection_count": 1,
        "width": 1920,
        "height": 1080,
    } for event in dispatched_events)
    assert raw_input not in json.dumps(dispatched_events)


def test_predict_skips_ppe_event_when_required_classes_are_present(monkeypatch) -> None:
    monkeypatch.setenv("SENSEMU_GATEWAY_RUNTIME_URL", "http://runtime.test")
    monkeypatch.setenv("SENSEMU_GATEWAY_CONTROL_PLANE_URL", "http://control.test")
    get_settings.cache_clear()
    observed_paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        observed_paths.append(request.url.path)
        if request.url.path.endswith("demo:authorize"):
            return httpx.Response(
                200,
                json={
                    "deployment_id": "2bc78bb9-b9c1-4bee-bdb5-e0c1350ec4ae",
                    "model_version_id": "3bc78bb9-b9c1-4bee-bdb5-e0c1350ec4ae",
                    "artifact_uri": "s3://sensemu-dev/model.pt",
                    "task_type": "object-detection",
                    "contract": "detections.v1",
                    "capability_id": "vision.predict",
                    "workflow_bindings": [
                        {
                            "workflow_id": "9bc78bb9-b9c1-4bee-bdb5-e0c1350ec4ae",
                            "template_key": "ppe-violation-webhook.v1",
                            "event_types": ["missing_hardhat", "missing_safety_vest"],
                        }
                    ],
                },
            )
        if request.url.host == "runtime.test":
            return httpx.Response(
                200,
                json={
                    "predictions": [
                        {
                            "detections": [
                                {"class_name": "person"},
                                {"class_name": "hardhat"},
                                {"class_name": "safety_vest"},
                            ]
                        }
                    ]
                },
            )
        if request.url.path.endswith("usage-records"):
            return httpx.Response(200, json={"reused": False})
        return httpx.Response(404)

    client = TestClient(create_app(httpx.MockTransport(handler)))
    response = client.post(
        "/inference/v1/workspaces/sensemu-test/endpoints/demo:predict",
        headers={"X-API-Key": "smu_live_test-key"},
        json={"inputs": ["s3://sensemu-dev/example.jpg"]},
    )

    assert response.status_code == 200
    assert not any(path.endswith("vision-events") for path in observed_paths)


def test_event_dispatch_failure_keeps_successful_metering(monkeypatch) -> None:
    monkeypatch.setenv("SENSEMU_GATEWAY_RUNTIME_URL", "http://runtime.test")
    monkeypatch.setenv("SENSEMU_GATEWAY_CONTROL_PLANE_URL", "http://control.test")
    get_settings.cache_clear()
    observed_paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        observed_paths.append(request.url.path)
        if request.url.path.endswith("demo:authorize"):
            return httpx.Response(
                200,
                json={
                    "deployment_id": "2bc78bb9-b9c1-4bee-bdb5-e0c1350ec4ae",
                    "model_version_id": "3bc78bb9-b9c1-4bee-bdb5-e0c1350ec4ae",
                    "artifact_uri": "s3://sensemu-dev/model.pt",
                    "task_type": "object-detection",
                    "contract": "detections.v1",
                    "capability_id": "vision.predict",
                    "workflow_bindings": [
                        {
                            "workflow_id": "9bc78bb9-b9c1-4bee-bdb5-e0c1350ec4ae",
                            "template_key": "ppe-violation-webhook.v1",
                            "event_types": ["missing_hardhat"],
                        }
                    ],
                },
            )
        if request.url.host == "runtime.test":
            return httpx.Response(
                200,
                json={"predictions": [{"detections": [{"class_name": "person"}]}]},
            )
        if request.url.path.endswith("usage-records"):
            return httpx.Response(200, json={"reused": False})
        if request.url.path.endswith("vision-events"):
            return httpx.Response(500, json={"detail": "temporary failure"})
        return httpx.Response(404)

    client = TestClient(create_app(httpx.MockTransport(handler)))
    response = client.post(
        "/inference/v1/workspaces/sensemu-test/endpoints/demo:predict",
        headers={"X-API-Key": "smu_live_test-key"},
        json={"inputs": ["s3://sensemu-dev/example.jpg"]},
    )

    assert response.status_code == 502
    assert response.json()["detail"]["code"] == "EVENT_DISPATCH_FAILED"
    assert any(path.endswith("usage-records") for path in observed_paths)
    assert not any(path.endswith(":release") for path in observed_paths)
