from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class CapabilityInputSpec(BaseModel):
    media_types: list[Literal["image/jpeg", "image/png", "image/webp"]] = Field(
        min_length=1, max_length=3
    )
    max_payload_bytes: int = Field(ge=1, le=32 * 1024 * 1024)
    capture_constraints: str = Field(min_length=8, max_length=1_000)


class CapabilityOutputSpec(BaseModel):
    contract: str = Field(min_length=3, max_length=64)
    classes: list[str] = Field(min_length=1, max_length=100)
    business_events: list[str] = Field(default_factory=list, max_length=32)


class CapabilityApplicabilitySpec(BaseModel):
    verified_scenes: list[str] = Field(min_length=1, max_length=24)
    unsupported_conditions: list[str] = Field(default_factory=list, max_length=24)


class CapabilityDeliverySpec(BaseModel):
    profiles: list[Literal["shared-api", "dedicated-endpoint"]] = Field(
        min_length=1, max_length=2
    )
    data_retention_default: Literal["none", "customer-configured"] = "none"


class CapabilitySpecCreate(BaseModel):
    capability_slug: str = Field(
        pattern=r"^[a-z0-9][a-z0-9-]{2,79}$",
    )
    display_name: str = Field(min_length=2, max_length=180)
    problem_definition: str = Field(min_length=16, max_length=1_500)
    input: CapabilityInputSpec
    output: CapabilityOutputSpec
    applicability: CapabilityApplicabilitySpec
    delivery: CapabilityDeliverySpec


class CapabilitySpecResponse(BaseModel):
    id: UUID
    workspace_id: UUID
    project_id: UUID
    deployment_id: UUID
    capability_slug: str
    version_number: int
    display_name: str
    problem_definition: str
    input: CapabilityInputSpec
    output: CapabilityOutputSpec
    applicability: CapabilityApplicabilitySpec
    delivery: CapabilityDeliverySpec
    evidence: dict[str, Any]
    status: str
    content_hash: str
    spec_uri: str
    published_at: datetime
    created_at: datetime
