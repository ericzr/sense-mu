from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    service: str
    environment: str


class ReadinessDependency(BaseModel):
    name: Literal["database", "object_storage"]
    status: Literal["ready", "unavailable"]
    detail: str


class ReadinessResponse(BaseModel):
    status: Literal["ready", "not_ready"]
    service: str
    environment: str
    dependencies: list[ReadinessDependency]


class OperationalIndicator(BaseModel):
    name: Literal[
        "training_queue",
        "stale_training_lease",
        "webhook_delivery",
        "stale_usage_reservation",
    ]
    status: Literal["healthy", "attention"]
    observed_count: int
    threshold_seconds: int
    detail: str


class OperationalResponse(BaseModel):
    status: Literal["healthy", "attention", "unavailable"]
    service: str
    environment: str
    generated_at: datetime
    indicators: list[OperationalIndicator]


class MetricSummary(BaseModel):
    datasets: int
    assets: int
    training_jobs_running: int
    model_versions_ready: int
    inference_calls_month: int


class ActiveRunSummary(BaseModel):
    run_id: str
    project_name: str
    dataset_version_number: int
    status: str
    progress: int
    engine: str
    model: str
    executor: str
    created_at: datetime
    error_message: str | None = None


class WorkspaceProjectSummary(BaseModel):
    id: UUID
    name: str
    task_type: str
    description: str | None
    status: Literal["active", "paused"]
    dataset_version_count: int
    active_run_count: int
    published_service_count: int
    created_at: datetime


class WorkspaceDatasetSummary(BaseModel):
    id: UUID
    project_id: UUID
    project_name: str
    name: str
    description: str | None
    asset_count: int
    version_count: int
    created_at: datetime


class OverviewResponse(BaseModel):
    workspace_id: UUID
    metrics: MetricSummary
    projects: list[WorkspaceProjectSummary]
    datasets: list[WorkspaceDatasetSummary]
    active_runs: list[ActiveRunSummary]
    recent_runs: list[ActiveRunSummary]
