from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from sensemu_api import provider_service
from sensemu_api.db.session import get_session
from sensemu_api.dependencies import WorkspaceAdminId
from sensemu_api.provider_schemas import (
    ProviderDashboardResponse,
    ProviderProfileResponse,
    ProviderProfileUpdate,
)

router = APIRouter(prefix="/api/v1/provider", tags=["provider-center"])
SessionDep = Annotated[Session, Depends(get_session)]


@router.get("/dashboard", response_model=ProviderDashboardResponse)
def get_provider_dashboard(
    workspace_id: WorkspaceAdminId,
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> ProviderDashboardResponse:
    return provider_service.get_dashboard(
        session, workspace_id, limit=limit
    )


@router.get("/profile", response_model=ProviderProfileResponse | None)
def get_provider_profile(
    workspace_id: WorkspaceAdminId,
    session: SessionDep,
) -> ProviderProfileResponse | None:
    return provider_service.get_profile(session, workspace_id)


@router.patch("/profile", response_model=ProviderProfileResponse)
def update_provider_profile(
    payload: ProviderProfileUpdate,
    workspace_id: WorkspaceAdminId,
    session: SessionDep,
) -> ProviderProfileResponse:
    return provider_service.update_profile(session, workspace_id, payload)
