import logging
from functools import lru_cache
from typing import Annotated, Protocol
from uuid import UUID

from celery import Celery
from fastapi import Depends

from sensemu_api.config import get_settings

logger = logging.getLogger(__name__)


class WebhookDispatcher(Protocol):
    def submit(self, delivery_id: UUID) -> None: ...


class CeleryWebhookDispatcher:
    def __init__(self) -> None:
        settings = get_settings()
        self.client = Celery("sensemu-webhook-dispatcher", broker=settings.celery_broker_url)
        self.client.conf.broker_transport_options = {
            "socket_connect_timeout": 0.5,
            "socket_timeout": 0.5,
        }

    def submit(self, delivery_id: UUID) -> None:
        try:
            self.client.send_task(
                "sensemu.webhooks.deliver",
                kwargs={"delivery_id": str(delivery_id)},
                task_id=str(delivery_id),
                queue="maintenance",
                retry=False,
            )
        except Exception:
            logger.exception("Unable to dispatch webhook delivery %s", delivery_id)


@lru_cache
def get_webhook_dispatcher() -> WebhookDispatcher:
    return CeleryWebhookDispatcher()


WebhookDispatcherDep = Annotated[WebhookDispatcher, Depends(get_webhook_dispatcher)]
