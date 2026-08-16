from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from sensemu_api import collaboration_service
from sensemu_api.collaboration_schemas import (
    WorkspaceAccessEventResponse,
    WorkspaceInvitationAccept,
    WorkspaceInvitationCreate,
    WorkspaceInvitationResponse,
    WorkspaceInvitationSecretResponse,
    WorkspaceMemberResponse,
    WorkspaceMemberRoleUpdate,
)
from sensemu_api.db.session import get_session
from sensemu_api.dependencies import CurrentUser, WorkspaceAdminId

router = APIRouter(prefix="/api/v1", tags=["workspace-collaboration"])
SessionDep = Annotated[Session, Depends(get_session)]


@router.get("/workspace-members", response_model=list[WorkspaceMemberResponse])
def list_workspace_members(
    workspace_id: WorkspaceAdminId,
    current_user: CurrentUser,
    session: SessionDep,
) -> list[WorkspaceMemberResponse]:
    return collaboration_service.list_members(session, workspace_id, current_user.id)


@router.patch(
    "/workspace-members/{membership_id}",
    response_model=WorkspaceMemberResponse,
)
def update_workspace_member(
    membership_id: UUID,
    payload: WorkspaceMemberRoleUpdate,
    workspace_id: WorkspaceAdminId,
    current_user: CurrentUser,
    session: SessionDep,
) -> WorkspaceMemberResponse:
    return collaboration_service.update_member_role(
        session, workspace_id, membership_id, current_user, payload
    )


@router.post(
    "/workspace-members/{membership_id}:suspend",
    response_model=WorkspaceMemberResponse,
)
def suspend_workspace_member(
    membership_id: UUID,
    workspace_id: WorkspaceAdminId,
    current_user: CurrentUser,
    session: SessionDep,
) -> WorkspaceMemberResponse:
    return collaboration_service.suspend_member(
        session, workspace_id, membership_id, current_user
    )


@router.post(
    "/workspace-invitations",
    response_model=WorkspaceInvitationSecretResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_workspace_invitation(
    payload: WorkspaceInvitationCreate,
    workspace_id: WorkspaceAdminId,
    current_user: CurrentUser,
    session: SessionDep,
) -> WorkspaceInvitationSecretResponse:
    return collaboration_service.create_invitation(
        session, workspace_id, current_user, payload
    )


@router.get(
    "/workspace-invitations",
    response_model=list[WorkspaceInvitationResponse],
)
def list_workspace_invitations(
    workspace_id: WorkspaceAdminId,
    session: SessionDep,
) -> list[WorkspaceInvitationResponse]:
    return collaboration_service.list_invitations(session, workspace_id)


@router.post(
    "/workspace-invitations/{invitation_id}:revoke",
    response_model=WorkspaceInvitationResponse,
)
def revoke_workspace_invitation(
    invitation_id: UUID,
    workspace_id: WorkspaceAdminId,
    current_user: CurrentUser,
    session: SessionDep,
) -> WorkspaceInvitationResponse:
    return collaboration_service.revoke_invitation(
        session, workspace_id, invitation_id, current_user
    )


@router.post(
    "/workspace-invitations:accept",
    response_model=WorkspaceMemberResponse,
)
def accept_workspace_invitation(
    payload: WorkspaceInvitationAccept,
    current_user: CurrentUser,
    session: SessionDep,
) -> WorkspaceMemberResponse:
    return collaboration_service.accept_invitation(
        session, current_user, payload.invite_token
    )


@router.get(
    "/workspace-access-events",
    response_model=list[WorkspaceAccessEventResponse],
)
def list_workspace_access_events(
    workspace_id: WorkspaceAdminId,
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[WorkspaceAccessEventResponse]:
    return collaboration_service.list_access_events(session, workspace_id, limit)
