from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class EvaluationRule(BaseModel):
    metric: str = Field(min_length=1, max_length=160)
    operator: Literal[">=", "<=", ">", "<"]
    threshold: float = Field(allow_inf_nan=False)
    label: str | None = Field(default=None, max_length=180)


class EvaluationPolicyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=180)
    rules: list[EvaluationRule] = Field(min_length=1, max_length=20)


class EvaluationPolicyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    version_number: int
    name: str
    rules: list[EvaluationRule]
    is_active: bool
    created_at: datetime


class EvaluationRuleResult(BaseModel):
    metric: str
    operator: str
    threshold: float
    actual: float | None
    passed: bool
    label: str | None
    reason: str | None


class EvaluationResponse(BaseModel):
    id: UUID
    model_version_id: UUID
    model_name: str
    model_version_number: int
    dataset_version_id: UUID
    policy_id: UUID
    policy_name: str
    policy_version: int
    source: str
    status: str
    verdict: str
    metrics: dict[str, Any]
    rule_results: list[EvaluationRuleResult]
    report_uri: str
    evaluated_at: datetime
    created_at: datetime


class AcceptanceRunCreate(BaseModel):
    dataset_version_id: UUID
    image_size: int = Field(default=640, ge=320, le=1536, multiple_of=32)
    batch_size: int = Field(default=16, ge=1, le=256)


class WorkerAcceptanceCompletion(BaseModel):
    attempt_id: UUID
    event_id: UUID
    metrics: dict[str, Any] = Field(default_factory=dict)
    evaluated_asset_count: int = Field(ge=1)
    runtime_image: str = Field(min_length=1, max_length=512)
    occurred_at: datetime
