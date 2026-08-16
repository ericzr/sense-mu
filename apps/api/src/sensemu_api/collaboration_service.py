from datetime import UTC, datetime, timedelta
from hashlib import sha256
from secrets import compare_digest, token_urlsafe
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, aliased

from sensemu_api.collaboration_schemas import (
    WorkspaceAccessEventResponse,
    WorkspaceInvitationCreate,
    WorkspaceInvitationResponse,
    WorkspaceInvitationSecretResponse,
    WorkspaceMemberResponse,
    WorkspaceMemberRoleUpdate,
)
from sensemu_api.config import get_settings
from sensemu_api.db.models import (
    UserAccount,
    Workspace,
    WorkspaceAccessEvent,
    WorkspaceInvitation,
    WorkspaceMembership,
)

ROLE_LEVEL = {"viewer": 0, "member": 1, "admin": 2, "owner": 3}


def _conflict(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)


def _not_found(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _normalize_email(email: str) -> str:
    return email.strip().casefold()


def _token_hash(token: str) -> str:
    return sha256(token.encode()).hexdigest()


def _new_invitation_token() -> tuple[str, str, str]:
    token = f"smu_invite_{token_urlsafe(32)}"
    return token, token[:18], _token_hash(token)


def _effective_invitation_status(
    invitation: WorkspaceInvitation,
    now: datetime | None = None,
) -> str:
    if invitation.status == "pending" and _as_utc(invitation.expires_at) <= (
        now or datetime.now(UTC)
    ):
        return "expired"
    return invitation.status


def _actor_membership(
    session: Session,
    workspace_id: UUID,
    actor_user_id: UUID,
) -> WorkspaceMembership:
    membership = session.scalar(
        select(WorkspaceMembership).where(
            WorkspaceMembership.workspace_id == workspace_id,
            WorkspaceMembership.user_id == actor_user_id,
            WorkspaceMembership.status == "active",
        )
    )
    if membership is None or ROLE_LEVEL.get(membership.role, -1) < ROLE_LEVEL["admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="当前成员角色无权管理工作区成员",
        )
    return membership


def _member_response(
    membership: WorkspaceMembership,
    user: UserAccount,
    current_user_id: UUID,
) -> WorkspaceMemberResponse:
    return WorkspaceMemberResponse(
        id=membership.id,
        user_id=user.id,
        email=user.email,
        display_name=user.display_name,
        role=membership.role,
        status=membership.status,
        joined_at=membership.joined_at,
        is_current_user=user.id == current_user_id,
    )


def _invitation_response(
    invitation: WorkspaceInvitation,
) -> WorkspaceInvitationResponse:
    return WorkspaceInvitationResponse(
        id=invitation.id,
        email=invitation.email,
        role=invitation.role,
        status=_effective_invitation_status(invitation),
        token_prefix=invitation.token_prefix,
        invited_by_user_id=invitation.invited_by_user_id,
        expires_at=invitation.expires_at,
        accepted_at=invitation.accepted_at,
        revoked_at=invitation.revoked_at,
        created_at=invitation.created_at,
    )


def _append_event(
    session: Session,
    workspace_id: UUID,
    actor_user_id: UUID,
    event_type: str,
    *,
    target_user_id: UUID | None = None,
    invitation_id: UUID | None = None,
    details: dict[str, str] | None = None,
) -> None:
    session.add(
        WorkspaceAccessEvent(
            workspace_id=workspace_id,
            actor_user_id=actor_user_id,
            event_type=event_type,
            target_user_id=target_user_id,
            invitation_id=invitation_id,
            details=details or {},
            occurred_at=datetime.now(UTC),
        )
    )


def list_members(
    session: Session,
    workspace_id: UUID,
    current_user_id: UUID,
) -> list[WorkspaceMemberResponse]:
    records = session.execute(
        select(WorkspaceMembership, UserAccount)
        .join(UserAccount, UserAccount.id == WorkspaceMembership.user_id)
        .where(
            WorkspaceMembership.workspace_id == workspace_id,
            UserAccount.status == "active",
        )
        .order_by(WorkspaceMembership.joined_at)
    ).all()
    responses = [
        _member_response(membership, user, current_user_id)
        for membership, user in records
    ]
    return sorted(
        responses,
        key=lambda item: (
            item.status != "active",
            -ROLE_LEVEL.get(item.role, -1),
            item.joined_at,
        ),
    )


def create_invitation(
    session: Session,
    workspace_id: UUID,
    actor: UserAccount,
    payload: WorkspaceInvitationCreate,
) -> WorkspaceInvitationSecretResponse:
    actor_membership = _actor_membership(session, workspace_id, actor.id)
    if payload.role == "admin" and actor_membership.role != "owner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="只有工作区所有者可以邀请管理员",
        )
    workspace = session.scalar(
        select(Workspace).where(Workspace.id == workspace_id).with_for_update()
    )
    if workspace is None:
        raise _not_found("未找到工作区")
    normalized_email = _normalize_email(payload.email)
    existing_member = session.scalar(
        select(WorkspaceMembership)
        .join(UserAccount, UserAccount.id == WorkspaceMembership.user_id)
        .where(
            WorkspaceMembership.workspace_id == workspace_id,
            WorkspaceMembership.status == "active",
            func.lower(UserAccount.email) == normalized_email,
        )
    )
    if existing_member is not None:
        raise _conflict("该邮箱对应的用户已是工作区成员")
    now = datetime.now(UTC)
    pending = session.scalar(
        select(WorkspaceInvitation).where(
            WorkspaceInvitation.workspace_id == workspace_id,
            WorkspaceInvitation.normalized_email == normalized_email,
            WorkspaceInvitation.status == "pending",
            WorkspaceInvitation.expires_at > now,
        )
    )
    if pending is not None:
        raise _conflict("该邮箱已有尚未失效的邀请")
    token, token_prefix, token_hash = _new_invitation_token()
    invitation = WorkspaceInvitation(
        workspace_id=workspace_id,
        email=payload.email.strip(),
        normalized_email=normalized_email,
        role=payload.role,
        status="pending",
        token_prefix=token_prefix,
        token_hash=token_hash,
        invited_by_user_id=actor.id,
        expires_at=now + timedelta(days=7),
    )
    session.add(invitation)
    session.flush()
    _append_event(
        session,
        workspace_id,
        actor.id,
        "invitation.created",
        invitation_id=invitation.id,
        details={"email": invitation.email, "role": invitation.role},
    )
    session.flush()
    response = _invitation_response(invitation).model_dump()
    acceptance_url = (
        f"{get_settings().web_origin.rstrip('/')}/settings#invite={token}"
    )
    return WorkspaceInvitationSecretResponse(
        **response,
        invite_token=token,
        acceptance_url=acceptance_url,
    )


def list_invitations(
    session: Session,
    workspace_id: UUID,
) -> list[WorkspaceInvitationResponse]:
    invitations = session.scalars(
        select(WorkspaceInvitation)
        .where(WorkspaceInvitation.workspace_id == workspace_id)
        .order_by(WorkspaceInvitation.created_at.desc())
    ).all()
    return [_invitation_response(invitation) for invitation in invitations]


def revoke_invitation(
    session: Session,
    workspace_id: UUID,
    invitation_id: UUID,
    actor: UserAccount,
) -> WorkspaceInvitationResponse:
    invitation = session.scalar(
        select(WorkspaceInvitation)
        .where(
            WorkspaceInvitation.id == invitation_id,
            WorkspaceInvitation.workspace_id == workspace_id,
        )
        .with_for_update()
    )
    if invitation is None:
        raise _not_found("未找到工作区邀请")
    if _effective_invitation_status(invitation) != "pending":
        raise _conflict("只有待接受的邀请可以撤销")
    invitation.status = "revoked"
    invitation.revoked_at = datetime.now(UTC)
    _append_event(
        session,
        workspace_id,
        actor.id,
        "invitation.revoked",
        invitation_id=invitation.id,
        details={"email": invitation.email, "role": invitation.role},
    )
    session.flush()
    return _invitation_response(invitation)


def accept_invitation(
    session: Session,
    actor: UserAccount,
    invite_token: str,
) -> WorkspaceMemberResponse:
    supplied_hash = _token_hash(invite_token)
    invitation = session.scalar(
        select(WorkspaceInvitation)
        .where(WorkspaceInvitation.token_hash == supplied_hash)
        .with_for_update()
    )
    if invitation is None or not compare_digest(invitation.token_hash, supplied_hash):
        raise _not_found("邀请不存在或已失效")
    if actor.email is None or not actor.email_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="当前身份没有经过验证的邮箱，无法接受邀请",
        )
    if not compare_digest(_normalize_email(actor.email), invitation.normalized_email):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="当前登录邮箱与邀请邮箱不一致",
        )
    if _effective_invitation_status(invitation) == "expired":
        raise _conflict("邀请已过期，请联系管理员重新邀请")
    if invitation.status == "revoked":
        raise _conflict("邀请已被撤销")
    membership = session.scalar(
        select(WorkspaceMembership)
        .where(
            WorkspaceMembership.workspace_id == invitation.workspace_id,
            WorkspaceMembership.user_id == actor.id,
        )
        .with_for_update()
    )
    if invitation.status == "accepted":
        if invitation.accepted_by_user_id == actor.id and membership is not None:
            return _member_response(membership, actor, actor.id)
        raise _conflict("邀请已经被接受")
    if membership is not None and membership.status != "active":
        raise _conflict("该用户的历史成员身份已停用，请联系管理员处理")
    now = datetime.now(UTC)
    if membership is None:
        membership = WorkspaceMembership(
            workspace_id=invitation.workspace_id,
            user_id=actor.id,
            role=invitation.role,
            status="active",
            joined_at=now,
        )
        session.add(membership)
    invitation.status = "accepted"
    invitation.accepted_by_user_id = actor.id
    invitation.accepted_at = now
    session.flush()
    _append_event(
        session,
        invitation.workspace_id,
        actor.id,
        "invitation.accepted",
        target_user_id=actor.id,
        invitation_id=invitation.id,
        details={"role": membership.role},
    )
    session.flush()
    return _member_response(membership, actor, actor.id)


def _manageable_membership(
    session: Session,
    workspace_id: UUID,
    membership_id: UUID,
    actor: UserAccount,
) -> tuple[WorkspaceMembership, UserAccount, WorkspaceMembership]:
    actor_membership = _actor_membership(session, workspace_id, actor.id)
    record = session.execute(
        select(WorkspaceMembership, UserAccount)
        .join(UserAccount, UserAccount.id == WorkspaceMembership.user_id)
        .where(
            WorkspaceMembership.id == membership_id,
            WorkspaceMembership.workspace_id == workspace_id,
        )
        .with_for_update()
    ).one_or_none()
    if record is None:
        raise _not_found("未找到工作区成员")
    target, target_user = record
    if target.user_id == actor.id:
        raise _conflict("不能在此处修改自己的成员身份")
    if target.role == "owner":
        raise _conflict("工作区所有者身份不能在此处变更")
    if target.role == "admin" and actor_membership.role != "owner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="只有工作区所有者可以管理管理员",
        )
    return target, target_user, actor_membership


def update_member_role(
    session: Session,
    workspace_id: UUID,
    membership_id: UUID,
    actor: UserAccount,
    payload: WorkspaceMemberRoleUpdate,
) -> WorkspaceMemberResponse:
    target, target_user, actor_membership = _manageable_membership(
        session, workspace_id, membership_id, actor
    )
    if target.status != "active":
        raise _conflict("已停用成员不能调整角色")
    if payload.role == "admin" and actor_membership.role != "owner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="只有工作区所有者可以授予管理员角色",
        )
    previous_role = target.role
    if previous_role != payload.role:
        target.role = payload.role
        _append_event(
            session,
            workspace_id,
            actor.id,
            "membership.role_changed",
            target_user_id=target.user_id,
            details={"from": previous_role, "to": payload.role},
        )
        session.flush()
    return _member_response(target, target_user, actor.id)


def suspend_member(
    session: Session,
    workspace_id: UUID,
    membership_id: UUID,
    actor: UserAccount,
) -> WorkspaceMemberResponse:
    target, target_user, _ = _manageable_membership(
        session, workspace_id, membership_id, actor
    )
    if target.status != "active":
        raise _conflict("成员身份已经停用")
    target.status = "suspended"
    _append_event(
        session,
        workspace_id,
        actor.id,
        "membership.suspended",
        target_user_id=target.user_id,
        details={"role": target.role},
    )
    session.flush()
    return _member_response(target, target_user, actor.id)


def list_access_events(
    session: Session,
    workspace_id: UUID,
    limit: int,
) -> list[WorkspaceAccessEventResponse]:
    actor_alias = aliased(UserAccount)
    target_alias = aliased(UserAccount)
    records = session.execute(
        select(WorkspaceAccessEvent, actor_alias, target_alias)
        .join(actor_alias, actor_alias.id == WorkspaceAccessEvent.actor_user_id)
        .outerjoin(target_alias, target_alias.id == WorkspaceAccessEvent.target_user_id)
        .where(WorkspaceAccessEvent.workspace_id == workspace_id)
        .order_by(WorkspaceAccessEvent.occurred_at.desc())
        .limit(limit)
    ).all()
    return [
        WorkspaceAccessEventResponse(
            id=event.id,
            event_type=event.event_type,
            actor_user_id=actor_user.id,
            actor_name=actor_user.display_name or actor_user.email or "未知成员",
            target_user_id=target_user.id if target_user else None,
            target_name=(target_user.display_name or target_user.email) if target_user else None,
            invitation_id=event.invitation_id,
            details=event.details,
            occurred_at=event.occurred_at,
        )
        for event, actor_user, target_user in records
    ]
