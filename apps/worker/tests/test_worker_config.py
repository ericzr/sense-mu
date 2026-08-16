import pytest

from sensemu_worker.config import WorkerSettings

SAFE_SECRET = "production-secret-0123456789abcdef"


def test_production_worker_rejects_local_default_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SENSEMU_ENVIRONMENT", "production")

    with pytest.raises(ValueError, match="必须显式配置安全凭据"):
        WorkerSettings.from_environment()


def test_production_worker_accepts_explicit_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SENSEMU_ENVIRONMENT", "production")
    monkeypatch.setenv("SENSEMU_WORKER_TOKEN", SAFE_SECRET)
    monkeypatch.setenv("SENSEMU_RUNTIME_TOKEN", SAFE_SECRET)
    monkeypatch.setenv("SENSEMU_OBJECT_STORAGE_ENDPOINT", "https://objects.example.com")
    monkeypatch.setenv("SENSEMU_OBJECT_STORAGE_SECRET_KEY", SAFE_SECRET)

    settings = WorkerSettings.from_environment()

    assert settings.environment == "production"
