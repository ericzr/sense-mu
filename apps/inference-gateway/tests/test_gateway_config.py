import pytest
from pydantic import ValidationError
from sensemu_gateway.config import GatewaySettings

SAFE_SECRET = "production-secret-0123456789abcdef"


def test_production_gateway_rejects_local_default_secrets() -> None:
    with pytest.raises(ValidationError, match="必须显式配置安全凭据"):
        GatewaySettings(
            _env_file=None,
            environment="production",
            runtime_url="http://runtime:8090",
        )


def test_production_gateway_accepts_explicit_configuration() -> None:
    settings = GatewaySettings(
        _env_file=None,
        environment="production",
        runtime_url="http://runtime:8090",
        runtime_token=SAFE_SECRET,
        control_plane_token=SAFE_SECRET,
    )

    assert settings.environment == "production"
