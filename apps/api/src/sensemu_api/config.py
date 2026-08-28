from functools import lru_cache
from ipaddress import ip_address
from typing import Literal
from urllib.parse import urlparse

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["development", "test", "staging", "production"]


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


def _is_https_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme == "https" and bool(parsed.hostname)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="SENSEMU_",
        extra="ignore",
    )

    environment: Environment = "development"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    database_url: str = "postgresql+psycopg://sensemu:sensemu@localhost:5432/sensemu"
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/1"
    object_storage_endpoint: str = "http://localhost:9000"
    object_storage_access_key: str = "sensemu"
    object_storage_secret_key: str = "sensemu-local-only"
    object_storage_bucket: str = "sensemu-dev"
    object_storage_region: str = "us-east-1"
    object_storage_local_path: str = ".local-data/objects"
    api_public_url: str = "http://localhost:8000"
    web_origin: str = "http://localhost:3000"
    worker_token: str = "sensemu-worker-local-only"
    gateway_token: str = "sensemu-gateway-local-only"
    payment_adapter_token: str = "sensemu-payment-adapter-local-only"
    platform_review_token: str = "sensemu-platform-review-local-only"
    webhook_signing_secret: str = "sensemu-webhook-signing-local-only"
    auth_mode: Literal["development", "oidc"] = "development"
    oidc_issuer_url: str = ""
    oidc_audience: str = ""
    oidc_jwks_url: str = ""
    development_user_subject: str = "local-developer"
    development_user_email: str = "developer@localhost"
    development_user_name: str = "SenseMu 本地开发者"
    inference_gateway_public_url: str = "http://localhost:8080"
    ultralytics_docker_image: str = "ultralytics/ultralytics:latest-cpu"
    training_execution_lease_timeout_seconds: int = 120
    training_execution_max_attempts: int = 3
    video_extraction_execution_lease_timeout_seconds: int = 120
    video_extraction_execution_max_attempts: int = 3
    inference_reservation_timeout_seconds: int = 180
    operational_training_queue_alert_seconds: int = 600
    operational_webhook_delivery_alert_seconds: int = 300

    @model_validator(mode="after")
    def validate_deployment_configuration(self) -> "Settings":
        if self.environment in {"development", "test"}:
            return self

        if self.auth_mode != "oidc":
            raise ValueError("staging/production 必须使用 OIDC 身份验证")
        missing_oidc = [
            name
            for name, value in {
                "oidc_issuer_url": self.oidc_issuer_url,
                "oidc_audience": self.oidc_audience,
                "oidc_jwks_url": self.oidc_jwks_url,
            }.items()
            if not value.strip()
        ]
        if missing_oidc:
            raise ValueError(f"OIDC 配置不完整: {', '.join(missing_oidc)}")
        insecure_public_urls = [
            name
            for name, value in {
                "oidc_issuer_url": self.oidc_issuer_url,
                "oidc_jwks_url": self.oidc_jwks_url,
                "api_public_url": self.api_public_url,
                "web_origin": self.web_origin,
                "inference_gateway_public_url": self.inference_gateway_public_url,
            }.items()
            if not _is_https_url(value)
        ]
        if insecure_public_urls:
            raise ValueError(
                "staging/production 公开地址必须使用 HTTPS: "
                + ", ".join(insecure_public_urls)
            )

        unsafe_secrets = [
            name
            for name, value in {
                "object_storage_secret_key": self.object_storage_secret_key,
                "worker_token": self.worker_token,
                "gateway_token": self.gateway_token,
                "payment_adapter_token": self.payment_adapter_token,
                "platform_review_token": self.platform_review_token,
                "webhook_signing_secret": self.webhook_signing_secret,
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
        if not self.database_url.startswith("postgresql"):
            raise ValueError("staging/production 必须使用 PostgreSQL")
        local_endpoints = [
            name
            for name, value in {
                "database_url": self.database_url,
                "redis_url": self.redis_url,
                "celery_broker_url": self.celery_broker_url,
                "object_storage_endpoint": self.object_storage_endpoint,
            }.items()
            if _is_local_endpoint(value)
        ]
        if local_endpoints:
            raise ValueError(
                "staging/production 禁止连接本机依赖: " + ", ".join(local_endpoints)
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
