from collections.abc import Iterator
from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from sensemu_api.db import Base
from sensemu_api.db.models import UserAccount, Workspace, WorkspaceMembership
from sensemu_api.db.session import get_session
from sensemu_api.dependencies import resolve_current_user
from sensemu_api.main import create_app


def _client() -> tuple[
    TestClient,
    dict[str, UserAccount],
    Workspace,
    dict[str, WorkspaceMembership],
]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    testing_session = sessionmaker(bind=engine, expire_on_commit=False)
    Base.metadata.create_all(engine)
    now = datetime.now(UTC)
    users = {
        name: UserAccount(
            issuer="urn:sensemu:test",
            subject=name,
            email=f"{name}@example.test",
            email_verified=True,
            display_name=name,
            status="active",
            last_seen_at=now,
        )
        for name in ("owner", "admin", "invitee", "intruder", "unverified")
    }
    users["unverified"].email_verified = False
    workspace = Workspace(slug="collaboration-lab", name="协作实验室")
    with testing_session() as session:
        session.add_all([*users.values(), workspace])
        session.flush()
        memberships = {
            "owner": WorkspaceMembership(
                workspace_id=workspace.id,
                user_id=users["owner"].id,
                role="owner",
                status="active",
                joined_at=now,
            ),
            "admin": WorkspaceMembership(
                workspace_id=workspace.id,
                user_id=users["admin"].id,
                role="admin",
                status="active",
                joined_at=now,
            ),
        }
        session.add_all(memberships.values())
        session.commit()

    def override_session() -> Iterator[Session]:
        with testing_session() as session:
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise

    active_user = {"name": "admin"}

    def override_user() -> UserAccount:
        return users[active_user["name"]]

    application = create_app()
    application.dependency_overrides[get_session] = override_session
    application.dependency_overrides[resolve_current_user] = override_user
    client = TestClient(application)
    client.active_user = active_user  # type: ignore[attr-defined]
    return client, users, workspace, memberships


def test_invitation_membership_roles_and_access_audit() -> None:
    client, _, workspace, memberships = _client()
    headers = {"X-Workspace-ID": str(workspace.id)}
    active_user: dict[str, str] = client.active_user  # type: ignore[attr-defined]

    members = client.get("/api/v1/workspace-members", headers=headers)
    assert members.status_code == 200
    assert {item["role"] for item in members.json()} == {"owner", "admin"}

    forbidden_admin_invite = client.post(
        "/api/v1/workspace-invitations",
        headers=headers,
        json={"email": "invitee@example.test", "role": "admin"},
    )
    assert forbidden_admin_invite.status_code == 403

    created = client.post(
        "/api/v1/workspace-invitations",
        headers=headers,
        json={"email": "invitee@example.test", "role": "member"},
    )
    assert created.status_code == 201
    invitation = created.json()
    assert invitation["invite_token"].startswith("smu_invite_")
    assert invitation["acceptance_url"].endswith(
        f"#invite={invitation['invite_token']}"
    )
    assert client.post(
        "/api/v1/workspace-invitations",
        headers=headers,
        json={"email": "invitee@example.test", "role": "viewer"},
    ).status_code == 409
    listed_invites = client.get(
        "/api/v1/workspace-invitations", headers=headers
    ).json()
    assert "invite_token" not in listed_invites[0]
    assert listed_invites[0]["token_prefix"] == invitation["token_prefix"]

    active_user["name"] = "intruder"
    mismatched = client.post(
        "/api/v1/workspace-invitations:accept",
        json={"invite_token": invitation["invite_token"]},
    )
    assert mismatched.status_code == 403

    active_user["name"] = "invitee"
    accepted = client.post(
        "/api/v1/workspace-invitations:accept",
        json={"invite_token": invitation["invite_token"]},
    )
    assert accepted.status_code == 200
    assert accepted.json()["role"] == "member"
    assert accepted.json()["is_current_user"] is True
    repeated = client.post(
        "/api/v1/workspace-invitations:accept",
        json={"invite_token": invitation["invite_token"]},
    )
    assert repeated.status_code == 200

    active_user["name"] = "admin"
    changed = client.patch(
        f"/api/v1/workspace-members/{accepted.json()['id']}",
        headers=headers,
        json={"role": "viewer"},
    )
    assert changed.status_code == 200
    assert changed.json()["role"] == "viewer"
    protected_owner = client.patch(
        f"/api/v1/workspace-members/{memberships['owner'].id}",
        headers=headers,
        json={"role": "member"},
    )
    assert protected_owner.status_code == 409

    suspended = client.post(
        f"/api/v1/workspace-members/{accepted.json()['id']}:suspend",
        headers=headers,
    )
    assert suspended.status_code == 200
    assert suspended.json()["status"] == "suspended"
    active_user["name"] = "invitee"
    assert client.get("/api/v1/projects", headers=headers).status_code == 403

    active_user["name"] = "owner"
    unverified_invite = client.post(
        "/api/v1/workspace-invitations",
        headers=headers,
        json={"email": "unverified@example.test", "role": "viewer"},
    )
    assert unverified_invite.status_code == 201
    active_user["name"] = "unverified"
    unverified_acceptance = client.post(
        "/api/v1/workspace-invitations:accept",
        json={"invite_token": unverified_invite.json()["invite_token"]},
    )
    assert unverified_acceptance.status_code == 403

    active_user["name"] = "owner"
    revocable = client.post(
        "/api/v1/workspace-invitations",
        headers=headers,
        json={"email": "other@example.test", "role": "admin"},
    )
    assert revocable.status_code == 201
    revoked = client.post(
        f"/api/v1/workspace-invitations/{revocable.json()['id']}:revoke",
        headers=headers,
    )
    assert revoked.status_code == 200
    assert revoked.json()["status"] == "revoked"

    events = client.get("/api/v1/workspace-access-events", headers=headers)
    assert events.status_code == 200
    assert {
        "invitation.created",
        "invitation.accepted",
        "invitation.revoked",
        "membership.role_changed",
        "membership.suspended",
    } <= {item["event_type"] for item in events.json()}


def test_viewers_cannot_read_collaboration_admin_surfaces() -> None:
    client, _, workspace, _ = _client()
    active_user: dict[str, str] = client.active_user  # type: ignore[attr-defined]
    headers = {"X-Workspace-ID": str(workspace.id)}
    active_user["name"] = "invitee"
    assert client.get("/api/v1/workspace-members", headers=headers).status_code == 403
    assert (
        client.get("/api/v1/workspace-access-events", headers=headers).status_code
        == 403
    )
