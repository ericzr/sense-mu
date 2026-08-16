from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from uuid import UUID

import jwt
from fastapi import HTTPException, status
from jwt import PyJWKClient, PyJWTError
from jwt.exceptions import PyJWKClientConnectionError, PyJWKClientError
from sqlalchemy import select
from sqlalchemy.orm import Session

from sensemu_api.config import Settings, get_settings
from sensemu_api.db.models import UserAccount, Workspace, WorkspaceMembership


@dataclass(frozen=True)
class IdentityClaims:
    issuer: str
    subject: str
    email: str | None
    email_verified: bool
    display_name: str | None


@lru_cache(maxsize=8)
def _jwks_client(jwks_url: str) -> PyJWKClient:
    return PyJWKClient(jwks_url, cache_jwk_set=True, lifespan=300)


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def _require_oidc_settings(settings: Settings) -> None:
    if not (
        settings.oidc_issuer_url
        and settings.oidc_audience
        and settings.oidc_jwks_url
    ):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OIDC 身份验证尚未完成配置",
        )


def authenticate_identity(authorization: str | None) -> IdentityClaims:
    settings = get_settings()
    if settings.auth_mode == "development":
        if settings.environment not in {"development", "test"}:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="非开发环境禁止使用本地身份模式",
            )
        return IdentityClaims(
            issuer="urn:sensemu:development",
            subject=settings.development_user_subject,
            email=settings.development_user_email,
            email_verified=True,
            display_name=settings.development_user_name,
        )
    if settings.auth_mode != "oidc":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="未知的身份验证模式",
        )
    _require_oidc_settings(settings)
    if not authorization:
        raise _unauthorized("缺少身份凭据")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise _unauthorized("身份凭据格式无效")
    try:
        signing_key = _jwks_client(settings.oidc_jwks_url).get_signing_key_from_jwt(
            token
        )
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=settings.oidc_audience,
            issuer=settings.oidc_issuer_url,
            leeway=30,
            options={"require": ["exp", "iss", "sub", "aud"]},
        )
    except PyJWKClientConnectionError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="无法连接身份提供方",
        ) from error
    except (PyJWKClientError, PyJWTError) as error:
        raise _unauthorized("身份凭据无效或已过期") from error

    subject = claims.get("sub")
    if not isinstance(subject, str) or not subject:
        raise _unauthorized("身份凭据缺少用户标识")
    email = claims.get("email")
    email_verified = claims.get("email_verified") is True
    display_name = claims.get("name") or claims.get("preferred_username")
    return IdentityClaims(
        issuer=settings.oidc_issuer_url,
        subject=subject[:255],
        email=email[:320] if isinstance(email, str) else None,
        email_verified=email_verified,
        display_name=(
            display_name[:160] if isinstance(display_name, str) else None
        ),
    )


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def resolve_user(session: Session, claims: IdentityClaims) -> UserAccount:
    user = session.scalar(
        select(UserAccount)
        .where(
            UserAccount.issuer == claims.issuer,
            UserAccount.subject == claims.subject,
        )
        .with_for_update()
    )
    now = datetime.now(UTC)
    if user is None:
        user = UserAccount(
            issuer=claims.issuer,
            subject=claims.subject,
            email=claims.email,
            email_verified=claims.email_verified,
            display_name=claims.display_name,
            status="active",
            last_seen_at=now,
        )
        session.add(user)
        session.flush()
    elif user.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="用户账号已停用",
        )
    else:
        user.email = claims.email or user.email
        user.email_verified = claims.email_verified
        user.display_name = claims.display_name or user.display_name
        last_seen_at = _as_utc(user.last_seen_at) if user.last_seen_at else None
        if last_seen_at is None or last_seen_at < now - timedelta(minutes=5):
            user.last_seen_at = now

    if get_settings().auth_mode == "development":
        _ensure_development_memberships(session, user.id, now)
    session.flush()
    return user


def _ensure_development_memberships(
    session: Session,
    user_id: UUID,
    joined_at: datetime,
) -> None:
    workspace_ids = set(session.scalars(select(Workspace.id)).all())
    member_workspace_ids = set(
        session.scalars(
            select(WorkspaceMembership.workspace_id).where(
                WorkspaceMembership.user_id == user_id
            )
        ).all()
    )
    session.add_all(
        WorkspaceMembership(
            workspace_id=workspace_id,
            user_id=user_id,
            role="owner",
            status="active",
            joined_at=joined_at,
        )
        for workspace_id in workspace_ids - member_workspace_ids
    )


def list_user_workspaces(
    session: Session,
    user_id: UUID,
) -> list[tuple[Workspace, WorkspaceMembership]]:
    statement = (
        select(Workspace, WorkspaceMembership)
        .join(
            WorkspaceMembership,
            WorkspaceMembership.workspace_id == Workspace.id,
        )
        .where(
            WorkspaceMembership.user_id == user_id,
            WorkspaceMembership.status == "active",
        )
        .order_by(Workspace.created_at)
    )
    return list(session.execute(statement).all())


def add_workspace_owner(
    session: Session,
    workspace_id: UUID,
    user_id: UUID,
) -> WorkspaceMembership:
    membership = WorkspaceMembership(
        workspace_id=workspace_id,
        user_id=user_id,
        role="owner",
        status="active",
        joined_at=datetime.now(UTC),
    )
    session.add(membership)
    session.flush()
    return membership
