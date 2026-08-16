import logging
from functools import lru_cache
from typing import Annotated, Protocol
from uuid import UUID, uuid4

from celery import Celery
from fastapi import Depends

from sensemu_api.config import get_settings

logger = logging.getLogger(__name__)


class VideoExtractionDispatcher(Protocol):
    def submit(self, workspace_id: UUID, job_id: UUID) -> None: ...


class CeleryVideoExtractionDispatcher:
    def __init__(self) -> None:
        settings = get_settings()
        self.client = Celery("sensemu-video-extraction-dispatcher", broker=settings.celery_broker_url)
        self.client.conf.broker_transport_options = {
            "socket_connect_timeout": 0.5,
            "socket_timeout": 0.5,
        }

    def submit(self, workspace_id: UUID, job_id: UUID) -> None:
        attempt_id = uuid4()
        try:
            self.client.send_task(
                "sensemu.video-extraction.execute",
                kwargs={
                    "workspace_id": str(workspace_id),
                    "job_id": str(job_id),
                    "attempt_id": str(attempt_id),
                },
                task_id=str(attempt_id),
                queue="extraction",
                retry=False,
            )
        except Exception:
            logger.exception("Unable to dispatch video extraction job %s", job_id)


@lru_cache
def get_video_extraction_dispatcher() -> VideoExtractionDispatcher:
    return CeleryVideoExtractionDispatcher()


VideoExtractionDispatcherDep = Annotated[
    VideoExtractionDispatcher,
    Depends(get_video_extraction_dispatcher),
]
