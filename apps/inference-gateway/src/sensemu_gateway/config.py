from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class GatewaySettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="SENSEMU_GATEWAY_",
        extra="ignore",
    )

    host: str = "0.0.0.0"
    port: int = 8080
    runtime_url: str = ""
    runtime_token: str = "sensemu-runtime-local-only"
    control_plane_url: str = "http://localhost:8000"
    control_plane_token: str = "sensemu-gateway-local-only"
    control_plane_timeout_seconds: float = 5.0
    runtime_timeout_seconds: float = 60.0
    metering_timeout_seconds: float = 5.0
    health_timeout_seconds: float = 2.0
    web_origin: str = "http://localhost:3000"


@lru_cache
def get_settings() -> GatewaySettings:
    return GatewaySettings()
