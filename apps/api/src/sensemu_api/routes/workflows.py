from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from sensemu_api import workflow_service
from sensemu_api.db.session import get_session
from sensemu_api.dependencies import WorkspaceAdminId, WorkspaceId
from sensemu_api.storage import Storage, get_storage
from sensemu_api.workflow_schemas import WorkflowSpecCreate, WorkflowSpecResponse

router = APIRouter(prefix="/api/v1", tags=["workflows"])
SessionDep = Annotated[Session, Depends(get_session)]
StorageDep = Annotated[Storage, Depends(get_storage)]


@router.post(
    "/projects/{project_id}/workflow-specs",
    response_model=WorkflowSpecResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_workflow_spec(
    project_id: UUID,
    payload: WorkflowSpecCreate,
    workspace_id: WorkspaceAdminId,
    session: SessionDep,
    storage: StorageDep,
) -> WorkflowSpecResponse:
    return workflow_service.create_spec(
        session, storage, workspace_id, project_id, payload
    )


@router.get(
    "/projects/{project_id}/workflow-specs",
    response_model=list[WorkflowSpecResponse],
)
def list_workflow_specs(
    project_id: UUID,
    workspace_id: WorkspaceId,
    session: SessionDep,
) -> list[WorkflowSpecResponse]:
    return workflow_service.list_specs(session, workspace_id, project_id)
