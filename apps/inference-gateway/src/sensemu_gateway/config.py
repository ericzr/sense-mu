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
        local_endpoints = [
            name
            for name, value in {
                "runtime_url": self.runtime_url,
                "control_plane_url": self.control_plane_url,
            }.items()
            if _is_local_endpoint(value)
        ]
        if local_endpoints:
            raise ValueError(
                "staging/production 禁止连接本机依赖: " + ", ".join(local_endpoints)
            )
        if urlparse(self.web_origin).scheme != "https":
            raise ValueError("staging/production Web 来源必须使用 HTTPS")
        return self


@lru_cache
def get_settings() -> GatewaySettings:
    return GatewaySettings()
