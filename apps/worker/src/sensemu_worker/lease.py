import logging
import threading
from collections.abc import Callable
from typing import Protocol

from sensemu_worker.api_client import TransientWorkerAPIError, WorkerAPIError

logger = logging.getLogger(__name__)


class HeartbeatAPI(Protocol):
    def heartbeat_execution(
        self,
        workspace_id: str,
        run_id: str,
        attempt_id: str,
    ) -> dict: ...


class ExecutionLeaseLostError(RuntimeError):
    pass


class ExecutionLeaseHeartbeat:
    def __init__(
        self,
        api: HeartbeatAPI,
        workspace_id: str,
        run_id: str,
        attempt_id: str,
        interval_seconds: int,
        *,
        heartbeat: Callable[[str, str, str], dict] | None = None,
        resource_name: str = "训练任务",
    ) -> None:
        self.api = api
        self.workspace_id = workspace_id
        self.run_id = run_id
        self.attempt_id = attempt_id
        self.interval_seconds = max(1, interval_seconds)
        self._heartbeat = heartbeat or api.heartbeat_execution
        self.resource_name = resource_name
        self._stop = threading.Event()
        self._lost = threading.Event()
        self._thread: threading.Thread | None = None

    def pulse(self) -> None:
        try:
            self._heartbeat(
                self.workspace_id,
                self.run_id,
                self.attempt_id,
            )
        except TransientWorkerAPIError:
            logger.warning("%s %s 的租约心跳暂时无法送达", self.resource_name, self.run_id)
        except WorkerAPIError:
            logger.warning("%s %s 的执行租约已失效", self.resource_name, self.run_id)
            self._lost.set()

    def _run(self) -> None:
        while not self._stop.wait(self.interval_seconds):
            self.pulse()

    def start(self) -> None:
        if self._thread is not None:
            return
        self.pulse()
        self.ensure_owned()
        self._thread = threading.Thread(
            target=self._run,
            name=f"sensemu-lease-{self.run_id[:8]}",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2)
            self._thread = None

    def ensure_owned(self) -> None:
        if self._lost.is_set():
            raise ExecutionLeaseLostError(f"当前 Worker 已失去{self.resource_name}执行租约")
