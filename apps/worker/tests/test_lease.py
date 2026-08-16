import pytest

from sensemu_worker.api_client import TransientWorkerAPIError, WorkerAPIError
from sensemu_worker.lease import ExecutionLeaseHeartbeat, ExecutionLeaseLostError


class FakeHeartbeatAPI:
    def __init__(self, failure: Exception | None = None) -> None:
        self.failure = failure
        self.calls = 0

    def heartbeat_execution(
        self,
        workspace_id: str,
        run_id: str,
        attempt_id: str,
    ) -> dict:
        del workspace_id, run_id, attempt_id
        self.calls += 1
        if self.failure:
            raise self.failure
        return {"status": "running"}


def test_execution_lease_starts_with_an_immediate_heartbeat() -> None:
    api = FakeHeartbeatAPI()
    lease = ExecutionLeaseHeartbeat(api, "workspace", "run-12345678", "attempt", 60)

    lease.start()
    lease.ensure_owned()
    lease.stop()

    assert api.calls == 1


def test_transient_heartbeat_failure_does_not_abandon_owned_work() -> None:
    api = FakeHeartbeatAPI(TransientWorkerAPIError("temporary"))
    lease = ExecutionLeaseHeartbeat(api, "workspace", "run-12345678", "attempt", 60)

    lease.start()
    lease.ensure_owned()
    lease.stop()

    assert api.calls == 1


def test_definitive_heartbeat_rejection_stops_stale_worker() -> None:
    api = FakeHeartbeatAPI(WorkerAPIError("lease rejected"))
    lease = ExecutionLeaseHeartbeat(api, "workspace", "run-12345678", "attempt", 60)

    with pytest.raises(ExecutionLeaseLostError, match="失去训练任务执行租约"):
        lease.start()
    lease.stop()
