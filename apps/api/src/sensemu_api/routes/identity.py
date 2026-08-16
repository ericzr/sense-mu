from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from sensemu_api import identity_service
from sensemu_api.config import get_settings
from sensemu_api.db.session import get_session
from sensemu_api.dependencies import CurrentUser
from sensemu_api.identity_schemas import (
    IdentityMembershipResponse,
    IdentityMeResponse,
)

router = APIRouter(prefix="/api/v1", tags=["identity"])
SessionDep = Annotated[Session, Depends(get_session)]


@router.get("/identity/me", response_model=IdentityMeResponse)
def current_identity(
    current_user: CurrentUser,
    session: SessionDep,
) -> IdentityMeResponse:
    memberships = identity_service.list_user_workspaces(session, current_user.id)
    return IdentityMeResponse(
        id=current_user.id,
        email=current_user.email,
        email_verified=current_user.email_verified,
        display_name=current_user.display_name,
        auth_mode=get_settings().auth_mode,
        memberships=[
            IdentityMembershipResponse(
                workspace_id=workspace.id,
                workspace_slug=workspace.slug,
                workspace_name=workspace.name,
                role=membership.role,
                joined_at=membership.joined_at,
            )
            for workspace, membership in memberships
        ],
    )
