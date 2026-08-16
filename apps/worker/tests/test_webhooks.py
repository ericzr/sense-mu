import json

import httpx

from sensemu_worker import tasks


class FakeWebhookAPI:
    def __init__(self, claim: dict) -> None:
        self.claim = claim
        self.completions: list[tuple[str, dict]] = []

    def claim_webhook_delivery(self, delivery_id: str) -> dict:
        del delivery_id
        return self.claim

    def complete_webhook_delivery(self, delivery_id: str, **payload) -> dict:
        self.completions.append((delivery_id, payload))
        return {"id": delivery_id, "status": "delivered" if payload["succeeded"] else "retrying"}


def webhook_claim() -> dict:
    return {
        "id": "delivery-1",
        "target_url": "https://events.example.com/sensemu",
        "payload": {
            "event_id": "event-1",
            "event_type": "missing_hardhat",
            "data": {"camera": "北门", "count": 1},
        },
        "signature": "signed-body",
        "attempt_count": 1,
    }


def install_fake_api(monkeypatch, api: FakeWebhookAPI) -> None:
    monkeypatch.setattr(tasks.WorkerSettings, "from_environment", lambda: object())
    monkeypatch.setattr(tasks, "WorkerAPIClient", lambda settings: api)


def test_webhook_delivery_uses_canonical_json_and_signature(monkeypatch) -> None:
    api = FakeWebhookAPI(webhook_claim())
    install_fake_api(monkeypatch, api)
    requests: list[dict] = []

    def fake_post(url: str, **kwargs) -> httpx.Response:
        requests.append({"url": url, **kwargs})
        return httpx.Response(204)

    monkeypatch.setattr(tasks.httpx, "post", fake_post)

    result = tasks.deliver_webhook("delivery-1")

    expected_body = json.dumps(
        api.claim["payload"],
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    assert result["status"] == "delivered"
    assert requests[0]["content"] == expected_body
    assert requests[0]["headers"] == {
        "Content-Type": "application/json",
        "X-SenseMu-Event-ID": "event-1",
        "X-SenseMu-Webhook-Signature": "sha256=signed-body",
    }
    assert requests[0]["follow_redirects"] is False
    assert api.completions == [
        ("delivery-1", {"succeeded": True, "status_code": 204, "error": None})
    ]


def test_webhook_network_failure_is_recorded_for_retry(monkeypatch) -> None:
    api = FakeWebhookAPI(webhook_claim())
    install_fake_api(monkeypatch, api)

    def fail_post(url: str, **kwargs) -> httpx.Response:
        del kwargs
        raise httpx.ConnectError(f"cannot connect to {url}")

    monkeypatch.setattr(tasks.httpx, "post", fail_post)

    result = tasks.deliver_webhook("delivery-1")

    assert result["status"] == "retrying"
    assert api.completions[0][0] == "delivery-1"
    assert api.completions[0][1]["succeeded"] is False
    assert "网络请求失败" in api.completions[0][1]["error"]


def test_recovery_dispatches_every_queued_delivery(monkeypatch) -> None:
    class FakeRecoveryAPI:
        def recover_webhook_deliveries(self) -> dict:
            return {"queued_delivery_ids": ["delivery-1", "delivery-2"]}

    monkeypatch.setattr(tasks.WorkerSettings, "from_environment", lambda: object())
    monkeypatch.setattr(tasks, "WorkerAPIClient", lambda settings: FakeRecoveryAPI())
    queued: list[str] = []
    monkeypatch.setattr(tasks.deliver_webhook, "delay", queued.append)

    result = tasks.recover_webhook_deliveries()

    assert result == {"queued_delivery_ids": ["delivery-1", "delivery-2"]}
    assert queued == ["delivery-1", "delivery-2"]
