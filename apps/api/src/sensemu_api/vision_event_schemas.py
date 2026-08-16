from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class VisionEventCreate(BaseModel):
    request_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,99}$")
    idempotency_key: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,119}$")
    deduplication_key: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,159}$")
    event_type: str = Field(min_length=3, max_length=120)
    payload: dict[str, Any] = Field(default_factory=dict)
    occurred_at: datetime


class VisionEventResponse(BaseModel):
    id: UUID
    workspace_id: UUID
    project_id: UUID
    workflow_spec_id: UUID
    capability_spec_id: UUID
    request_id: str
    deduplication_key: str
    event_type: str
    payload: dict[str, Any]
    occurred_at: datetime
    delivery_id: UUID
    delivery_status: str
    reused: bool = False


class VisionEventListItem(BaseModel):
    id: UUID
    request_id: str
    event_type: str
    occurred_at: datetime
    workflow_spec_id: UUID
    workflow_slug: str
    workflow_name: str
    delivery_id: UUID
    delivery_status: str
    attempt_count: int
    last_error: str | None
    delivered_at: datetime | None


class VisionEventReplaySample(BaseModel):
    source_id: str | None
    source_type: str | None
    input_index: int | None
    condition_kind: str | None
    required_class: str | None
    person_count: int | None
    required_class_count: int | None
    detection_count: int | None
    width: int | None
    height: int | None


class VisionEventReplayDecision(BaseModel):
    matched: bool
    reasons: list[str]
    deduplication_key: str
    deduplication_window_seconds: int


class VisionEventReplayDelivery(BaseModel):
    id: UUID
    status: str
    attempt_count: int
    target_host: str | None
    next_attempt_at: datetime
    last_error: str | None
    delivered_at: datetime | None


class VisionEventReplayResponse(BaseModel):
    event_id: UUID
    request_id: str
    event_type: str
    occurred_at: datetime
    workflow_slug: str
    workflow_name: str
    workflow_version: int
    template_key: str
    sample: VisionEventReplaySample
    decision: VisionEventReplayDecision
    delivery: VisionEventReplayDelivery


class WebhookDeliveryClaimResponse(BaseModel):
    id: UUID
    target_url: str
    payload: dict[str, Any]
    signature: str
    attempt_count: int


class WebhookDeliveryComplete(BaseModel):
    succeeded: bool
    status_code: int | None = Field(default=None, ge=100, le=599)
    error: str | None = Field(default=None, max_length=2_000)


class WebhookDeliveryResponse(BaseModel):
    id: UUID
    vision_event_id: UUID
    status: str
    attempt_count: int
    next_attempt_at: datetime
    last_error: str | None
    delivered_at: datetime | None


class WebhookDeliveryRecoveryResponse(BaseModel):
    queued_delivery_ids: list[UUID]
