from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, status
from sqlalchemy.orm import Session

from sensemu_api import capability_service, deployment_service
from sensemu_api.capability_schemas import CapabilitySpecCreate, CapabilitySpecResponse
from sensemu_api.db.session import get_session
from sensemu_api.dependencies import WorkspaceAdminId, WorkspaceId
from sensemu_api.deployment_schemas import (
    DeploymentCreate,
    DeploymentResponse,
    DeploymentSecretResponse,
    GatewayDeploymentResponse,
    UsageRecordCreate,
    UsageRecordResponse,
)
from sensemu_api.gateway_auth import GatewayAuth
from sensemu_api.storage import Storage, get_storage

router = APIRouter(prefix="/api/v1", tags=["deployments"])
SessionDep = Annotated[Session, Depends(get_session)]
StorageDep = Annotated[Storage, Depends(get_storage)]
ApiKey = Annotated[str, Header(alias="X-API-Key", min_length=16, max_length=160)]


@router.post(
    "/projects/{project_id}/deployments",
    response_model=DeploymentSecretResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_deployment(
    project_id: UUID,
    payload: DeploymentCreate,
    workspace_id: WorkspaceAdminId,
    session: SessionDep,
    storage: StorageDep,
) -> DeploymentSecretResponse:
    deployment, api_key = deployment_service.create_deployment(
        session, storage, workspace_id, project_id, payload
    )
    response = deployment_service.to_response(session, deployment)
    return DeploymentSecretResponse(**response.model_dump(), api_key=api_key)


@router.get(
    "/projects/{project_id}/deployments",
    response_model=list[DeploymentResponse],
)
def list_deployments(
    project_id: UUID,
    workspace_id: WorkspaceId,
    session: SessionDep,
) -> list[DeploymentResponse]:
    return deployment_service.list_deployments(session, workspace_id, project_id)


@router.post(
    "/deployments/{deployment_id}/capability-spec",
    response_model=CapabilitySpecResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_capability_spec(
    deployment_id: UUID,
    payload: CapabilitySpecCreate,
    workspace_id: WorkspaceAdminId,
    session: SessionDep,
    storage: StorageDep,
) -> CapabilitySpecResponse:
    return capability_service.create_spec(
        session, storage, workspace_id, deployment_id, payload
    )


@router.get(
    "/projects/{project_id}/capability-specs",
    response_model=list[CapabilitySpecResponse],
)
def list_capability_specs(
    project_id: UUID,
    workspace_id: WorkspaceId,
    session: SessionDep,
) -> list[CapabilitySpecResponse]:
    return capability_service.list_specs(session, workspace_id, project_id)


@router.post(
    "/deployments/{deployment_id}:disable",
    response_model=DeploymentResponse,
)
def disable_deployment(
    deployment_id: UUID,
    workspace_id: WorkspaceAdminId,
    session: SessionDep,
) -> DeploymentResponse:
    deployment = deployment_service.set_deployment_enabled(
        session, workspace_id, deployment_id, enabled=False
    )
    return deployment_service.to_response(session, deployment)


@router.post(
    "/deployments/{deployment_id}:enable",
    response_model=DeploymentResponse,
)
def enable_deployment(
    deployment_id: UUID,
    workspace_id: WorkspaceAdminId,
    session: SessionDep,
) -> DeploymentResponse:
    deployment = deployment_service.set_deployment_enabled(
        session, workspace_id, deployment_id, enabled=True
    )
    return deployment_service.to_response(session, deployment)


@router.post(
    "/deployments/{deployment_id}:rotate-key",
    response_model=DeploymentSecretResponse,
)
def rotate_deployment_key(
    deployment_id: UUID,
    workspace_id: WorkspaceAdminId,
    session: SessionDep,
) -> DeploymentSecretResponse:
    deployment, api_key = deployment_service.rotate_api_key(
        session, workspace_id, deployment_id
    )
    response = deployment_service.to_response(session, deployment)
    return DeploymentSecretResponse(**response.model_dump(), api_key=api_key)


@router.post(
    "/internal/inference/workspaces/{workspace_slug}/endpoints/{endpoint_slug}:resolve",
    response_model=GatewayDeploymentResponse,
    include_in_schema=False,
)
def resolve_inference_endpoint(
    workspace_slug: str,
    endpoint_slug: str,
    api_key: ApiKey,
    session: SessionDep,
    _gateway_auth: GatewayAuth,
) -> GatewayDeploymentResponse:
    return deployment_service.resolve_endpoint(
        session, workspace_slug, endpoint_slug, api_key
    )


@router.post(
    "/internal/inference/usage-records",
    response_model=UsageRecordResponse,
    include_in_schema=False,
)
def create_usage_record(
    payload: UsageRecordCreate,
    session: SessionDep,
    _gateway_auth: GatewayAuth,
) -> UsageRecordResponse:
    return deployment_service.record_usage(session, payload)
