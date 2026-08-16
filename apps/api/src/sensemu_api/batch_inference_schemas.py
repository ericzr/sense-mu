from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from sensemu_api.training_schemas import TrainingRunResponse


class BatchInferenceParameters(BaseModel):
    confidence: float = Field(default=0.25, ge=0, le=1, allow_inf_nan=False)
    iou: float = Field(default=0.7, ge=0, le=1, allow_inf_nan=False)
    max_detections: int = Field(default=300, ge=1, le=300)
    image_size: int = Field(default=640, ge=320, le=1536, multiple_of=32)


class BatchInferenceRunCreate(BaseModel):
    deployment_id: UUID
    dataset_version_id: UUID
    source_split: Literal["all", "train", "valid", "test"] = "all"
    parameters: BatchInferenceParameters = Field(default_factory=BatchInferenceParameters)


class BatchInferenceResultResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    run_id: UUID
    deployment_id: UUID
    output_uri: str
    report_uri: str
    summary: dict[str, Any]
    completed_at: datetime


class BatchInferenceRunResponse(TrainingRunResponse):
    result: BatchInferenceResultResponse | None = None


class WorkerBatchInferenceCompletion(BaseModel):
    attempt_id: UUID
    event_id: UUID
    output_uri: str = Field(min_length=1, max_length=2048)
    report_uri: str = Field(min_length=1, max_length=2048)
    processed_asset_count: int = Field(ge=1)
    prediction_count: int = Field(ge=0)
    runtime: dict[str, Any] = Field(default_factory=dict)
    occurred_at: datetime
