import os
from dataclasses import dataclass


@dataclass(frozen=True)
class WorkerSettings:
    api_url: str
    worker_token: str
    object_storage_endpoint: str
    object_storage_access_key: str
    object_storage_secret_key: str
    object_storage_bucket: str
    object_storage_region: str
    object_storage_local_path: str
    docker_image: str
    docker_gpus: str
    runtime_url: str
    runtime_token: str
    lease_heartbeat_interval_seconds: int
    docker_execution_timeout_seconds: int
    docker_allow_cross_architecture: bool

    @staticmethod
    def _env_bool(name: str, default: bool = False) -> bool:
        value = os.getenv(name)
        if value is None:
            return default
        return value.strip().lower() in {"1", "true", "yes", "on"}

    @classmethod
    def from_environment(cls) -> "WorkerSettings":
        return cls(
            api_url=os.getenv("SENSEMU_API_URL", "http://localhost:8000").rstrip("/"),
            worker_token=os.getenv(
                "SENSEMU_WORKER_TOKEN",
                "sensemu-worker-local-only",
            ),
            object_storage_endpoint=os.getenv(
                "SENSEMU_OBJECT_STORAGE_ENDPOINT",
                "http://localhost:9000",
            ),
            object_storage_access_key=os.getenv(
                "SENSEMU_OBJECT_STORAGE_ACCESS_KEY",
                "sensemu",
            ),
            object_storage_secret_key=os.getenv(
                "SENSEMU_OBJECT_STORAGE_SECRET_KEY",
                "sensemu-local-only",
            ),
            object_storage_bucket=os.getenv(
                "SENSEMU_OBJECT_STORAGE_BUCKET",
                "sensemu-dev",
            ),
            object_storage_region=os.getenv(
                "SENSEMU_OBJECT_STORAGE_REGION",
                "us-east-1",
            ),
            object_storage_local_path=os.getenv(
                "SENSEMU_OBJECT_STORAGE_LOCAL_PATH",
                ".local-data/objects",
            ),
            docker_image=os.getenv(
                "SENSEMU_ULTRALYTICS_DOCKER_IMAGE",
                "ultralytics/ultralytics:latest-cpu",
            ),
            docker_gpus=os.getenv("SENSEMU_DOCKER_GPUS", "none"),
            runtime_url=os.getenv("SENSEMU_RUNTIME_URL", "http://localhost:8090").rstrip("/"),
            runtime_token=os.getenv(
                "SENSEMU_RUNTIME_TOKEN",
                "sensemu-runtime-local-only",
            ),
            lease_heartbeat_interval_seconds=int(
                os.getenv("SENSEMU_LEASE_HEARTBEAT_INTERVAL_SECONDS", "15")
            ),
            docker_execution_timeout_seconds=int(
                os.getenv("SENSEMU_DOCKER_EXECUTION_TIMEOUT_SECONDS", "7200")
            ),
            docker_allow_cross_architecture=cls._env_bool(
                "SENSEMU_DOCKER_ALLOW_CROSS_ARCHITECTURE"
            ),
        )
