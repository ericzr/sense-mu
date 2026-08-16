import pytest
from pydantic import ValidationError

from sensemu_api.config import Settings

SAFE_SECRET = "production-secret-0123456789abcdef"


def production_settings(**overrides: str) -> Settings:
    values = {
        "environment": "production",
        "auth_mode": "oidc",
        "oidc_issuer_url": "https://identity.example.com/realms/sensemu",
        "oidc_audience": "sensemu-api",
        "oidc_jwks_url": "https://identity.example.com/realms/sensemu/certs",
        "object_storage_endpoint": "https://objects.example.com",
        "object_storage_secret_key": SAFE_SECRET,
        "worker_token": SAFE_SECRET,
        "gateway_token": SAFE_SECRET,
        "payment_adapter_token": SAFE_SECRET,
        "platform_review_token": SAFE_SECRET,
        "webhook_signing_secret": SAFE_SECRET,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_production_rejects_development_authentication() -> None:
    with pytest.raises(ValidationError, match="必须使用 OIDC"):
        Settings(_env_file=None, environment="production")


def test_production_rejects_local_default_secrets() -> None:
    with pytest.raises(ValidationError, match="必须显式配置安全凭据"):
        production_settings(worker_token="sensemu-worker-local-only")


def test_production_accepts_complete_explicit_configuration() -> None:
    settings = production_settings()

    assert settings.environment == "production"
    assert settings.auth_mode == "oidc"
