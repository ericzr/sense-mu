from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import UUID, uuid4

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from jwt.exceptions import PyJWKClientConnectionError
from pydantic import ValidationError
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from sensemu_api import identity_service
from sensemu_api.config import get_settings
from sensemu_api.db import Base
from sensemu_api.db.models import WorkspaceMembership
from sensemu_api.db.session import get_session
from sensemu_api.main import create_app


def _client() -> tuple[TestClient, sessionmaker[Session]]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    testing_session = sessionmaker(bind=engine, expire_on_commit=False)
    Base.metadata.create_all(engine)

    def override_session() -> Iterator[Session]:
        with testing_session() as session:
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise

    application = create_app()
    application.dependency_overrides[get_session] = override_session
    return TestClient(application), testing_session


def _set_membership_role(
    testing_session: sessionmaker[Session],
    workspace_id: str,
    *,
    role: str,
    member_status: str = "active",
) -> None:
    with testing_session() as session:
        membership = session.scalar(
            select(WorkspaceMembership).where(
                WorkspaceMembership.workspace_id == UUID(workspace_id)
            )
        )
        assert membership is not None
        membership.role = role
        membership.status = member_status
        session.commit()


def test_development_identity_and_workspace_roles() -> None:
    client, testing_session = _client()
    identity = client.get("/api/v1/identity/me")
    assert identity.status_code == 200
    assert identity.json()["auth_mode"] == "development"
    assert identity.json()["email"] == "developer@localhost"
    assert identity.json()["email_verified"] is True

    created = client.post(
        "/api/v1/workspaces",
        json={"slug": "identity-lab", "name": "身份测试实验室"},
    )
    assert created.status_code == 201
    workspace = created.json()
    assert workspace["role"] == "owner"
    headers = {"X-Workspace-ID": workspace["id"]}

    listed = client.get("/api/v1/workspaces").json()
    assert listed[0]["id"] == workspace["id"]
    assert listed[0]["role"] == "owner"
    me = client.get("/api/v1/identity/me").json()
    assert me["memberships"][0]["role"] == "owner"

    _set_membership_role(testing_session, workspace["id"], role="viewer")
    assert client.get("/api/v1/projects", headers=headers).status_code == 200
    viewer_write = client.post(
        "/api/v1/projects",
        headers=headers,
        json={
            "slug": "viewer-project",
            "name": "查看者项目",
            "task_type": "object-detection",
        },
    )
    assert viewer_write.status_code == 403

    _set_membership_role(testing_session, workspace["id"], role="member")
    member_write = client.post(
        "/api/v1/projects",
        headers=headers,
        json={
            "slug": "member-project",
            "name": "成员项目",
            "task_type": "object-detection",
        },
    )
    assert member_write.status_code == 201
    admin_only = client.post(
        f"/api/v1/capability-specs/{uuid4()}/marketplace-listing",
        headers=headers,
        json={
            "title": "管理员商品",
            "summary": "只允许管理员执行的上架操作。",
            "price_per_1000_cents": 100,
            "monthly_quota_units": 100,
        },
    )
    assert admin_only.status_code == 403

    _set_membership_role(testing_session, workspace["id"], role="admin")
    admin_request = client.post(
        f"/api/v1/deployments/{uuid4()}/marketplace-listing",
        headers=headers,
        json={
            "title": "管理员商品",
            "summary": "管理员已通过权限检查，继续校验业务资源。",
            "price_per_1000_cents": 100,
            "monthly_quota_units": 100,
        },
    )
    assert admin_request.status_code == 404

    _set_membership_role(
        testing_session,
        workspace["id"],
        role="admin",
        member_status="suspended",
    )
    assert client.get("/api/v1/projects", headers=headers).status_code == 403


def test_oidc_token_verification_and_membership_creation(monkeypatch) -> None:
    issuer = "https://identity.example.test/realms/sensemu"
    audience = "sensemu-api"
    monkeypatch.setenv("SENSEMU_AUTH_MODE", "oidc")
    monkeypatch.setenv("SENSEMU_OIDC_ISSUER_URL", issuer)
    monkeypatch.setenv("SENSEMU_OIDC_AUDIENCE", audience)
    monkeypatch.setenv("SENSEMU_OIDC_JWKS_URL", f"{issuer}/jwks")
    get_settings.cache_clear()

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key()

    class FakeJwksClient:
        def get_signing_key_from_jwt(self, _token: str):
            return SimpleNamespace(key=public_key)

    monkeypatch.setattr(
        identity_service,
        "_jwks_client",
        lambda _url: FakeJwksClient(),
    )
    client, _ = _client()
    now = datetime.now(UTC)
    claims = {
        "iss": issuer,
        "sub": "oidc-user-001",
        "aud": audience,
        "exp": now + timedelta(minutes=5),
        "iat": now,
        "email": "owner@example.test",
        "email_verified": True,
        "name": "算法团队负责人",
    }
    token = jwt.encode(claims, private_key, algorithm="RS256")
    authorization = {"Authorization": f"Bearer {token}"}
    try:
        assert client.get("/api/v1/identity/me").status_code == 401
        me = client.get("/api/v1/identity/me", headers=authorization)
        assert me.status_code == 200
        assert me.json()["email"] == "owner@example.test"
        assert me.json()["email_verified"] is True
        assert me.json()["memberships"] == []

        workspace = client.post(
            "/api/v1/workspaces",
            headers=authorization,
            json={"slug": "oidc-lab", "name": "OIDC 实验室"},
        )
        assert workspace.status_code == 201
        assert workspace.json()["role"] == "owner"
        listed = client.get("/api/v1/workspaces", headers=authorization)
        assert listed.status_code == 200
        assert listed.json()[0]["id"] == workspace.json()["id"]

        invalid_token = jwt.encode(
            {**claims, "aud": "another-api"}, private_key, algorithm="RS256"
        )
        rejected = client.get(
            "/api/v1/identity/me",
            headers={"Authorization": f"Bearer {invalid_token}"},
        )
        assert rejected.status_code == 401
    finally:
        get_settings.cache_clear()


def test_oidc_jwks_outage_is_reported_as_service_unavailable(monkeypatch) -> None:
    issuer = "https://identity.example.test/realms/sensemu"
    audience = "sensemu-api"
    monkeypatch.setenv("SENSEMU_AUTH_MODE", "oidc")
    monkeypatch.setenv("SENSEMU_OIDC_ISSUER_URL", issuer)
    monkeypatch.setenv("SENSEMU_OIDC_AUDIENCE", audience)
    monkeypatch.setenv("SENSEMU_OIDC_JWKS_URL", f"{issuer}/jwks")
    get_settings.cache_clear()

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    now = datetime.now(UTC)
    token = jwt.encode(
        {
            "iss": issuer,
            "sub": "oidc-outage-user",
            "aud": audience,
            "exp": now + timedelta(minutes=5),
            "iat": now,
        },
        private_key,
        algorithm="RS256",
    )

    class UnavailableJwksClient:
        def get_signing_key_from_jwt(self, _token: str):
            raise PyJWKClientConnectionError("identity provider unavailable")

    monkeypatch.setattr(
        identity_service,
        "_jwks_client",
        lambda _url: UnavailableJwksClient(),
    )
    client, _ = _client()
    try:
        response = client.get(
            "/api/v1/identity/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 503
        assert response.json()["detail"] == "无法连接身份提供方"
    finally:
        get_settings.cache_clear()


def test_production_rejects_development_identity_mode(monkeypatch) -> None:
    monkeypatch.setenv("SENSEMU_ENVIRONMENT", "production")
    monkeypatch.setenv("SENSEMU_AUTH_MODE", "development")
    get_settings.cache_clear()
    try:
        with pytest.raises(ValidationError, match="必须使用 OIDC"):
            _client()
    finally:
        get_settings.cache_clear()
