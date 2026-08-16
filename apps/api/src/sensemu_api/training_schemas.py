from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from sensemu_api.training_engine import EngineDescriptor


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class TrainingRunCreate(BaseModel):
    dataset_version_id: UUID
    engine: str = Field(default="ultralytics", min_length=1, max_length=80)
    executor: str = Field(default="docker", min_length=1, max_length=80)
    recipe: dict[str, Any] = Field(default_factory=dict)


class TrainingRunResponse(ORMModel):
    id: UUID
    project_id: UUID
    dataset_version_id: UUID
    run_type: str
    status: str
    engine: str
    executor: str
    recipe: dict[str, Any]
    progress: int
    artifact_prefix: str | None
    spec_uri: str | None
    error_code: str | None
    error_message: str | None
    execution_attempt: int
    claimed_at: datetime | None
    heartbeat_at: datetime | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime
    updated_at: datetime
    reused: bool = False


class RunEventResponse(ORMModel):
    id: UUID
    event_id: UUID
    run_id: UUID
    sequence: int
    event_type: str
    status: str
    progress: int
    payload: dict[str, Any]
    occurred_at: datetime


class TrainingReportRow(BaseModel):
    epoch: int = Field(ge=0)
    metrics: dict[str, float]


class TrainingReportResponse(BaseModel):
    run_id: UUID
    rows: list[TrainingReportRow]


class TrainingClassMetric(BaseModel):
    class_id: int = Field(ge=0)
    name: str = Field(min_length=1, max_length=120)
    precision: float | None = None
    recall: float | None = None
    map50: float | None = None
    map50_95: float | None = None


class TrainingClassMetricsResponse(BaseModel):
    run_id: UUID
    classes: list[TrainingClassMetric]


class ModelVersionResponse(BaseModel):
    id: UUID
    model_id: UUID
    model_name: str
    run_id: UUID
    version_number: int
    status: str
    artifact_uri: str
    metrics: dict[str, Any]
    created_at: datetime


class TrainingEngineResponse(EngineDescriptor):
    executor: Literal["docker"] = "docker"


class WorkerRunEventCreate(BaseModel):
    attempt_id: UUID
    event_id: UUID
    event_type: Literal["job.started", "job.progressed", "job.failed", "job.cancelled"]
    progress: int | None = Field(default=None, ge=0, le=99)
    error_code: str | None = Field(default=None, max_length=80)
    error_message: str | None = Field(default=None, max_length=4000)
    payload: dict[str, Any] = Field(default_factory=dict)
    occurred_at: datetime


class WorkerRunCompletion(BaseModel):
    attempt_id: UUID
    event_id: UUID
    model_name: str = Field(min_length=1, max_length=180)
    artifact_uri: str = Field(min_length=1, max_length=2048)
    metrics: dict[str, Any] = Field(default_factory=dict)
    occurred_at: datetime


class WorkerExecutionResponse(BaseModel):
    run_id: UUID
    attempt_id: UUID
    status: str
    job_spec: dict[str, Any]


class WorkerExecutionClaim(BaseModel):
    attempt_id: UUID
    worker_id: str = Field(min_length=1, max_length=160)


class WorkerExecutionHeartbeat(BaseModel):
    attempt_id: UUID


class ExecutionRecoveryItem(BaseModel):
    workspace_id: UUID
    run_id: UUID
    action: Literal["requeued", "cancelled", "failed"]
    execution_attempt: int


class ExecutionRecoveryResponse(BaseModel):
    recovered: list[ExecutionRecoveryItem]
