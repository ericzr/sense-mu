from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="SENSEMU_",
        extra="ignore",
    )

    environment: str = "development"
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
    auth_mode: str = "development"
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


@lru_cache
def get_settings() -> Settings:
    return Settings()
