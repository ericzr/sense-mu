from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class DeploymentCreate(BaseModel):
    model_version_id: UUID
    name: str = Field(min_length=1, max_length=180)
    endpoint_slug: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{2,119}$")
    environment: Literal["staging", "production"] = "production"


class DeploymentResponse(BaseModel):
    id: UUID
    workspace_id: UUID
    workspace_slug: str
    project_id: UUID
    model_version_id: UUID
    model_name: str
    model_version_number: int
    task_type: str
    evaluation_id: UUID | None
    evaluation_policy_version: int | None
    name: str
    endpoint_slug: str
    endpoint_url: str
    environment: str
    status: str
    spec_uri: str | None
    api_key_prefix: str | None
    request_count: int
    billable_units: float
    published_at: datetime | None
    disabled_at: datetime | None
    created_at: datetime
    updated_at: datetime


class DeploymentSecretResponse(DeploymentResponse):
    api_key: str


class WorkflowEventBinding(BaseModel):
    workflow_id: UUID
    workflow_slug: str
    workflow_version: int
    template_key: str
    event_types: list[str]
    deduplication_window_seconds: int


class GatewayDeploymentResponse(BaseModel):
    deployment_id: UUID
    workspace_id: UUID
    workspace_slug: str
    endpoint_slug: str
    model_version_id: UUID
    artifact_uri: str
    task_type: str
    contract: str
    capability_id: str = "vision.predict"
    workflow_bindings: list[WorkflowEventBinding] = Field(default_factory=list)


class UsageRecordCreate(BaseModel):
    deployment_id: UUID
    reservation_id: UUID | None = None
    request_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,99}$")
    capability_id: str = Field(min_length=1, max_length=64)
    billable_units: float = Field(gt=0, allow_inf_nan=False)
    unit: Literal["image"] = "image"
    dimensions: dict[str, Any] = Field(default_factory=dict)
    occurred_at: datetime


class UsageRecordResponse(BaseModel):
    id: UUID
    deployment_id: UUID | None
    listing_id: UUID | None
    subscription_id: UUID | None
    request_id: str
    capability_id: str
    billable_units: float
    unit: str
    dimensions: dict[str, Any]
    occurred_at: datetime
    reused: bool = False
