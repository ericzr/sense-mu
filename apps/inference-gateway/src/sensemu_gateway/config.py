from functools import lru_cache
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _unsafe_production_secret(value: str) -> bool:
    normalized = value.strip().lower()
    return len(value.strip()) < 32 or "local-only" in normalized


class GatewaySettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="SENSEMU_GATEWAY_",
        extra="ignore",
    )

    environment: Literal["development", "test", "staging", "production"] = "development"
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

    @model_validator(mode="after")
    def validate_deployment_configuration(self) -> "GatewaySettings":
        if self.environment in {"development", "test"}:
            return self
        if not self.runtime_url.strip():
            raise ValueError("staging/production 必须配置推理运行时地址")
        unsafe_secrets = [
            name
            for name, value in {
                "runtime_token": self.runtime_token,
                "control_plane_token": self.control_plane_token,
            }.items()
            if _unsafe_production_secret(value)
        ]
        if unsafe_secrets:
            raise ValueError(
                "staging/production 必须显式配置安全凭据: "
                + ", ".join(unsafe_secrets)
            )
        return self


@lru_cache
def get_settings() -> GatewaySettings:
    return GatewaySettings()
