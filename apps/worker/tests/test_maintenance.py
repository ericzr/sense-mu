from sensemu_worker import tasks


def test_stale_reservation_task_delegates_to_core_api(monkeypatch) -> None:
    class FakeAPI:
        def recover_stale_usage_reservations(self) -> dict:
            return {"recovered": [{"reservation_id": "reservation-1"}]}

    fake_api = FakeAPI()
    monkeypatch.setattr(tasks.WorkerSettings, "from_environment", lambda: object())
    monkeypatch.setattr(tasks, "WorkerAPIClient", lambda settings: fake_api)

    result = tasks.recover_stale_usage_reservations()

    assert result == {"recovered": [{"reservation_id": "reservation-1"}]}
