import os

from celery import Celery
from celery.signals import worker_init

from sensemu_worker.config import WorkerSettings

broker_url = os.getenv("SENSEMU_CELERY_BROKER_URL", "redis://localhost:6379/1")
result_backend = os.getenv("SENSEMU_CELERY_RESULT_BACKEND", "redis://localhost:6379/2")

app = Celery("sensemu-worker", broker=broker_url, backend=result_backend)
app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    worker_prefetch_multiplier=1,
    imports=("sensemu_worker.tasks",),
    task_routes={
        "sensemu.training.execute": {"queue": "training"},
        "sensemu.batch-inference.execute": {"queue": "training"},
        "sensemu.video-extraction.execute": {"queue": "extraction"},
        "sensemu.video-extraction.recover-stale": {"queue": "maintenance"},
        "sensemu.training.recover-stale": {"queue": "training"},
        "sensemu.inference.recover-stale-reservations": {"queue": "maintenance"},
        "sensemu.webhooks.deliver": {"queue": "maintenance"},
        "sensemu.webhooks.recover": {"queue": "maintenance"},
    },
    beat_schedule={
        "recover-stale-training-leases": {
            "task": "sensemu.training.recover-stale",
            "schedule": 30.0,
            "options": {"queue": "training"},
        },
        "recover-stale-video-extraction-leases": {
            "task": "sensemu.video-extraction.recover-stale",
            "schedule": 30.0,
            "options": {"queue": "maintenance"},
        },
        "recover-stale-inference-reservations": {
            "task": "sensemu.inference.recover-stale-reservations",
            "schedule": 60.0,
            "options": {"queue": "maintenance"},
        },
        "recover-webhook-deliveries": {
            "task": "sensemu.webhooks.recover",
            "schedule": 15.0,
            "options": {"queue": "maintenance"},
        },
    },
)


@worker_init.connect
def validate_worker_configuration(**_: object) -> None:
    WorkerSettings.from_environment()


@app.task(name="sensemu.system.ping")
def ping() -> dict[str, str]:
    return {"service": "sensemu-worker", "status": "ok"}


if __name__ == "__main__":
    app.worker_main(["worker", "--loglevel=INFO"])
