from functools import lru_cache
from ipaddress import ip_address
from typing import Literal
from urllib.parse import urlparse

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _unsafe_production_secret(value: str) -> bool:
    normalized = value.strip().lower()
    return len(value.strip()) < 32 or "local-only" in normalized


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


class RuntimeSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="SENSEMU_RUNTIME_",
        extra="ignore",
    )

    environment: Literal["development", "test", "staging", "production"] = "development"
    host: str = "0.0.0.0"
    port: int = 8090
    token: str = "sensemu-runtime-local-only"
    object_storage_endpoint: str = "http://localhost:9000"
    object_storage_access_key: str = "sensemu"
    object_storage_secret_key: str = "sensemu-local-only"
    object_storage_bucket: str = "sensemu-dev"
    object_storage_region: str = "us-east-1"
    object_storage_local_path: str = ".local-data/objects"
    cache_path: str = ".local-data/inference-cache"
    max_cached_models: int = 2
    max_model_bytes: int = 2 * 1024 * 1024 * 1024
    max_input_bytes: int = 8 * 1024 * 1024
    max_concurrent_requests: int = 1
    queue_timeout_seconds: float = 2.0
    device: str = "cpu"

    @model_validator(mode="after")
    def validate_deployment_configuration(self) -> "RuntimeSettings":
        if self.environment in {"development", "test"}:
            return self
        unsafe_secrets = [
            name
            for name, value in {
                "token": self.token,
                "object_storage_secret_key": self.object_storage_secret_key,
            }.items()
            if _unsafe_production_secret(value)
        ]
        if unsafe_secrets:
            raise ValueError(
                "staging/production 必须显式配置安全凭据: "
                + ", ".join(unsafe_secrets)
            )
        if self.object_storage_endpoint.strip().lower() == "local://":
            raise ValueError("staging/production 禁止使用本地对象存储")
        if _is_local_endpoint(self.object_storage_endpoint):
            raise ValueError("staging/production 禁止连接本机对象存储")
        return self


@lru_cache
def get_settings() -> RuntimeSettings:
    return RuntimeSettings()
