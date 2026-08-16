from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from sensemu_api import identity_service
from sensemu_api.db.models import UserAccount, WorkspaceMembership
from sensemu_api.db.session import get_session

SessionDep = Annotated[Session, Depends(get_session)]
ROLE_LEVEL = {"viewer": 0, "member": 1, "admin": 2, "owner": 3}


def resolve_current_user(
    session: SessionDep,
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
) -> UserAccount:
    claims = identity_service.authenticate_identity(authorization)
    return identity_service.resolve_user(session, claims)


CurrentUser = Annotated[UserAccount, Depends(resolve_current_user)]


def _require_workspace_role(
    session: Session,
    user_id: UUID,
    workspace_id: UUID,
    minimum_role: str,
) -> None:
    membership = session.scalar(
        select(WorkspaceMembership).where(
            WorkspaceMembership.workspace_id == workspace_id,
            WorkspaceMembership.user_id == user_id,
            WorkspaceMembership.status == "active",
        )
    )
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="当前用户不是该工作区成员",
        )
    if ROLE_LEVEL.get(membership.role, -1) < ROLE_LEVEL[minimum_role]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="当前成员角色无权执行该操作",
        )


def workspace_access(
    request: Request,
    session: SessionDep,
    current_user: CurrentUser,
    workspace_id: Annotated[UUID, Header(alias="X-Workspace-ID")],
) -> UUID:
    minimum_role = "viewer" if request.method in {"GET", "HEAD", "OPTIONS"} else "member"
    _require_workspace_role(session, current_user.id, workspace_id, minimum_role)
    return workspace_id


def workspace_admin_access(
    session: SessionDep,
    current_user: CurrentUser,
    workspace_id: Annotated[UUID, Header(alias="X-Workspace-ID")],
) -> UUID:
    _require_workspace_role(session, current_user.id, workspace_id, "admin")
    return workspace_id


WorkspaceId = Annotated[UUID, Depends(workspace_access)]
WorkspaceAdminId = Annotated[UUID, Depends(workspace_admin_access)]
