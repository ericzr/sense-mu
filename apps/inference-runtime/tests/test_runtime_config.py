import pytest
from pydantic import ValidationError

from sensemu_runtime.config import RuntimeSettings

SAFE_SECRET = "production-secret-0123456789abcdef"


def test_production_runtime_rejects_local_default_secrets() -> None:
    with pytest.raises(ValidationError, match="必须显式配置安全凭据"):
        RuntimeSettings(_env_file=None, environment="production")


def test_production_runtime_accepts_explicit_configuration() -> None:
    settings = RuntimeSettings(
        _env_file=None,
        environment="production",
        token=SAFE_SECRET,
        object_storage_endpoint="https://objects.example.com",
        object_storage_secret_key=SAFE_SECRET,
    )

    assert settings.environment == "production"
