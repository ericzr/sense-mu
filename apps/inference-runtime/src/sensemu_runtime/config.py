from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class RuntimeSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="SENSEMU_RUNTIME_",
        extra="ignore",
    )

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


@lru_cache
def get_settings() -> RuntimeSettings:
    return RuntimeSettings()
