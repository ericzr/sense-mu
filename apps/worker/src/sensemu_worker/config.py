import os
from dataclasses import dataclass
from ipaddress import ip_address
from urllib.parse import urlparse


def _is_local_endpoint(value: str) -> bool:
    hostname = urlparse(value).hostname
    if not hostname:
        return False
    normalized = hostname.rstrip(".").lower()
    if normalized == "localhost" or normalized.endswith(".localhost"):
        return True
    try:
        return ip_address(normalized).is_loopback
    except ValueError:
        return False


@dataclass(frozen=True)
class WorkerSettings:
    environment: str
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

    def __post_init__(self) -> None:
        normalized_environment = self.environment.strip().lower()
        object.__setattr__(self, "environment", normalized_environment)
        if normalized_environment not in {
            "development",
            "test",
            "staging",
            "production",
        }:
            raise ValueError("SENSEMU_ENVIRONMENT 必须是 development/test/staging/production")
        if normalized_environment in {"development", "test"}:
            return
        unsafe_secrets = [
            name
            for name, value in {
                "worker_token": self.worker_token,
                "runtime_token": self.runtime_token,
                "object_storage_secret_key": self.object_storage_secret_key,
            }.items()
            if len(value.strip()) < 32 or "local-only" in value.strip().lower()
        ]
        if unsafe_secrets:
            raise ValueError(
                "staging/production 必须显式配置安全凭据: "
                + ", ".join(unsafe_secrets)
            )
        if self.object_storage_endpoint.strip().lower() == "local://":
            raise ValueError("staging/production 禁止使用本地对象存储")
        if self.docker_allow_cross_architecture:
            raise ValueError("staging/production 禁止跨架构转译训练")
        local_endpoints = [
            name
            for name, value in {
                "api_url": self.api_url,
                "runtime_url": self.runtime_url,
                "object_storage_endpoint": self.object_storage_endpoint,
            }.items()
            if _is_local_endpoint(value)
        ]
        if local_endpoints:
            raise ValueError(
                "staging/production 禁止连接本机依赖: " + ", ".join(local_endpoints)
            )
        if "@sha256:" not in self.docker_image:
            raise ValueError("staging/production 训练镜像必须固定 sha256 摘要")

    @staticmethod
    def _env_bool(name: str, default: bool = False) -> bool:
        value = os.getenv(name)
        if value is None:
            return default
        return value.strip().lower() in {"1", "true", "yes", "on"}

    @classmethod
    def from_environment(cls) -> "WorkerSettings":
        return cls(
            environment=os.getenv("SENSEMU_ENVIRONMENT", "development"),
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
