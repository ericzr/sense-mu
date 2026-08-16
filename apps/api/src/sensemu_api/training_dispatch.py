import logging
from functools import lru_cache
from typing import Annotated, Protocol
from uuid import UUID, uuid4

from celery import Celery
from fastapi import Depends

from sensemu_api.config import get_settings

logger = logging.getLogger(__name__)


class TrainingDispatcher(Protocol):
    def submit(self, workspace_id: UUID, run_id: UUID) -> None: ...

    def submit_acceptance(self, workspace_id: UUID, run_id: UUID) -> None: ...

    def submit_batch_inference(self, workspace_id: UUID, run_id: UUID) -> None: ...


class CeleryTrainingDispatcher:
    def __init__(self) -> None:
        settings = get_settings()
        self.client = Celery("sensemu-api-dispatcher", broker=settings.celery_broker_url)
        self.client.conf.broker_transport_options = {
            "socket_connect_timeout": 0.5,
            "socket_timeout": 0.5,
        }

    def submit(self, workspace_id: UUID, run_id: UUID) -> None:
        self._submit("sensemu.training.execute", workspace_id, run_id)

    def submit_acceptance(self, workspace_id: UUID, run_id: UUID) -> None:
        self._submit("sensemu.evaluation.execute", workspace_id, run_id)

    def submit_batch_inference(self, workspace_id: UUID, run_id: UUID) -> None:
        self._submit("sensemu.batch-inference.execute", workspace_id, run_id)

    def _submit(self, task_name: str, workspace_id: UUID, run_id: UUID) -> None:
        attempt_id = uuid4()
        try:
            self.client.send_task(
                task_name,
                kwargs={
                    "workspace_id": str(workspace_id),
                    "run_id": str(run_id),
                    "attempt_id": str(attempt_id),
                },
                task_id=str(attempt_id),
                queue="training",
                retry=False,
            )
        except Exception:
            logger.exception("Unable to dispatch run %s; it remains queued", run_id)


@lru_cache
def get_training_dispatcher() -> TrainingDispatcher:
    return CeleryTrainingDispatcher()


TrainingDispatcherDep = Annotated[TrainingDispatcher, Depends(get_training_dispatcher)]
