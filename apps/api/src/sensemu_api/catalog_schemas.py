from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class WorkspaceCreate(BaseModel):
    slug: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{2,79}$")
    name: str = Field(min_length=1, max_length=160)


class WorkspaceResponse(ORMModel):
    id: UUID
    slug: str
    name: str
    created_at: datetime
    role: str = "viewer"


class ProjectCreate(BaseModel):
    slug: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{2,99}$")
    name: str = Field(min_length=1, max_length=180)
    task_type: Literal[
        "object-detection",
        "classification",
        "segmentation",
        "pose",
        "ocr",
    ]
    description: str | None = Field(default=None, max_length=2_000)


class ProjectResponse(ORMModel):
    id: UUID
    workspace_id: UUID
    slug: str
    name: str
    task_type: str
    description: str | None
    status: Literal["active", "paused"]
    created_at: datetime


class DatasetCreate(BaseModel):
    name: str = Field(min_length=1, max_length=180)
    description: str | None = Field(default=None, max_length=2_000)


class DatasetResponse(ORMModel):
    id: UUID
    project_id: UUID
    name: str
    description: str | None
    class_map: dict[str, str]
    created_at: datetime
    asset_count: int = 0
    version_count: int = 0


class UploadIntentCreate(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    content_type: Literal[
        "image/jpeg",
        "image/png",
        "image/webp",
        "video/mp4",
        "video/quicktime",
        "video/webm",
    ]
    byte_size: int = Field(gt=0, le=2 * 1024 * 1024 * 1024)
    checksum_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


class UploadIntentResponse(BaseModel):
    method: Literal["PUT"] = "PUT"
    upload_url: str
    object_key: str
    headers: dict[str, str]
    expires_in: int


class AssetRegister(BaseModel):
    object_key: str = Field(min_length=1, max_length=1_024)
    media_type: Literal[
        "image/jpeg",
        "image/png",
        "image/webp",
        "video/mp4",
        "video/quicktime",
        "video/webm",
    ]
    checksum_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    byte_size: int = Field(gt=0, le=2 * 1024 * 1024 * 1024)
    width: int | None = Field(default=None, gt=0, le=100_000)
    height: int | None = Field(default=None, gt=0, le=100_000)


class AssetResponse(ORMModel):
    id: UUID
    workspace_id: UUID
    uri: str
    media_type: str
    checksum_sha256: str
    byte_size: int
    width: int | None
    height: int | None
    created_at: datetime
    split: str | None = None
    annotation_uri: str | None = None
    reused: bool = False


class SourceAssetResponse(ORMModel):
    id: UUID
    workspace_id: UUID
    uri: str
    media_type: str
    checksum_sha256: str
    byte_size: int
    width: int | None
    height: int | None
    created_at: datetime


class DatasetItemUpdate(BaseModel):
    split: Literal["train", "valid", "test"]


class AnnotationUploadIntentCreate(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    byte_size: int = Field(ge=0, le=5 * 1024 * 1024)
    checksum_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


class AnnotationRegister(BaseModel):
    object_key: str = Field(min_length=1, max_length=1_024)
    byte_size: int = Field(ge=0, le=5 * 1024 * 1024)
    checksum_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


def _normalize_class_map(class_map: dict[str, str]) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for key, name in class_map.items():
        try:
            class_id = int(key)
        except ValueError as error:
            raise ValueError("class_map keys must be non-negative integers") from error
        if class_id < 0 or str(class_id) != key:
            raise ValueError("class_map keys must be non-negative integers")
        cleaned_name = name.strip()
        if not cleaned_name:
            raise ValueError("class_map names must not be empty")
        normalized[str(class_id)] = cleaned_name
    if normalized and sorted(map(int, normalized)) != list(range(len(normalized))):
        raise ValueError("class_map keys must be contiguous and start at 0")
    return normalized


class DatasetClassMapUpdate(BaseModel):
    class_map: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_class_map(self) -> "DatasetClassMapUpdate":
        self.class_map = _normalize_class_map(self.class_map)
        return self


class AnnotationTaskCreate(BaseModel):
    name: str = Field(min_length=1, max_length=180)
    method: Literal["manual", "smart"]
    asset_scope: Literal["unlabeled", "all"] = "unlabeled"
    class_map: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_class_map(self) -> "AnnotationTaskCreate":
        self.class_map = _normalize_class_map(self.class_map)
        return self


class AnnotationTaskFromVideoExtractionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=180)
    class_map: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_class_map(self) -> "AnnotationTaskFromVideoExtractionCreate":
        self.class_map = _normalize_class_map(self.class_map)
        return self


class AnnotationTaskResponse(BaseModel):
    id: UUID
    dataset_id: UUID
    name: str
    method: Literal["manual", "smart"]
    asset_scope: Literal["unlabeled", "all", "video_extraction"]
    status: Literal["annotating", "review", "done"]
    assigned_to_user_id: UUID
    source_video_extraction_job_id: UUID | None
    class_map: dict[str, str]
    asset_count: int = Field(ge=0)
    completed_count: int = Field(ge=0)
    created_at: datetime
    updated_at: datetime


class AnnotationTaskStatusUpdate(BaseModel):
    status: Literal["review", "done"]


class AnnotationTaskYoloImportUploadIntentCreate(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    byte_size: int = Field(gt=0, le=512 * 1024 * 1024)
    checksum_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


class AnnotationTaskYoloImport(BaseModel):
    object_key: str = Field(min_length=1, max_length=1_024)
    byte_size: int = Field(gt=0, le=512 * 1024 * 1024)
    checksum_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


class AnnotationTaskYoloImportResponse(BaseModel):
    task: AnnotationTaskResponse
    imported_asset_count: int = Field(ge=0)


class VideoExtractionJobCreate(BaseModel):
    source_asset_id: UUID
    frame_interval_ms: int = Field(default=1_000, ge=100, le=60_000)
    deduplicate: bool = True


class VideoExtractionJobResponse(ORMModel):
    id: UUID
    dataset_id: UUID
    source_asset_id: UUID
    idempotency_key: str
    frame_interval_ms: int
    deduplicate: bool
    status: Literal[
        "queued",
        "preparing",
        "running",
        "succeeded",
        "failed",
        "cancel_requested",
        "cancelled",
    ]
    progress: int = Field(ge=0, le=100)
    frames_created: int = Field(ge=0)
    error_code: str | None
    error_message: str | None
    execution_attempt: int
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime
    updated_at: datetime


class VideoExtractionWorkerClaim(BaseModel):
    attempt_id: UUID
    worker_id: str = Field(min_length=1, max_length=160)


class VideoExtractionWorkerHeartbeat(BaseModel):
    attempt_id: UUID


class VideoExtractionFrame(BaseModel):
    object_uri: str = Field(min_length=1, max_length=2048)
    media_type: Literal["image/jpeg", "image/png", "image/webp"] = "image/jpeg"
    checksum_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    byte_size: int = Field(gt=0, le=25 * 1024 * 1024)
    width: int | None = Field(default=None, gt=0, le=100_000)
    height: int | None = Field(default=None, gt=0, le=100_000)
    frame_index: int = Field(ge=0)
    timestamp_ms: int = Field(ge=0)


class VideoExtractionWorkerEvent(BaseModel):
    attempt_id: UUID
    event_type: Literal["job.started", "job.progressed", "job.failed", "job.cancelled"]
    progress: int | None = Field(default=None, ge=0, le=99)
    error_code: str | None = Field(default=None, max_length=80)
    error_message: str | None = Field(default=None, max_length=4_000)


class VideoExtractionWorkerCompletion(BaseModel):
    attempt_id: UUID
    frames: list[VideoExtractionFrame] = Field(max_length=20_000)
    occurred_at: datetime


class VideoExtractionRecoveryItem(BaseModel):
    workspace_id: UUID
    job_id: UUID
    action: Literal["requeued", "cancelled", "failed"]
    execution_attempt: int


class VideoExtractionRecoveryResponse(BaseModel):
    recovered: list[VideoExtractionRecoveryItem]


class FreezeDatasetVersion(BaseModel):
    train_ratio: float = Field(default=0.8, gt=0, lt=1)
    valid_ratio: float = Field(default=0.1, gt=0, lt=1)
    test_ratio: float = Field(default=0.1, gt=0, lt=1)
    class_map: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_ratios(self) -> "FreezeDatasetVersion":
        total = self.train_ratio + self.valid_ratio + self.test_ratio
        if abs(total - 1.0) > 0.000_001:
            raise ValueError("train_ratio, valid_ratio and test_ratio must sum to 1")
        normalized: dict[str, str] = {}
        for key, name in self.class_map.items():
            try:
                class_id = int(key)
            except ValueError as error:
                raise ValueError("class_map keys must be non-negative integers") from error
            if class_id < 0 or str(class_id) != key:
                raise ValueError("class_map keys must be non-negative integers")
            cleaned_name = name.strip()
            if not cleaned_name:
                raise ValueError("class_map names must not be empty")
            normalized[str(class_id)] = cleaned_name
        if normalized and sorted(map(int, normalized)) != list(range(len(normalized))):
            raise ValueError("class_map keys must be contiguous and start at 0")
        self.class_map = normalized
        return self


class DatasetVersionResponse(ORMModel):
    id: UUID
    dataset_id: UUID
    version_number: int
    status: str
    manifest_uri: str
    asset_count: int
    class_map: dict[str, str]
    frozen_at: datetime | None
    created_at: datetime


class DatasetVersionClassDistribution(BaseModel):
    class_id: int = Field(ge=0)
    class_name: str
    annotation_count: int = Field(ge=0)
    asset_count: int = Field(ge=0)


class DatasetVersionImageDimensions(BaseModel):
    known_asset_count: int = Field(ge=0)
    unknown_asset_count: int = Field(ge=0)
    min_width: int | None = Field(default=None, gt=0)
    max_width: int | None = Field(default=None, gt=0)
    min_height: int | None = Field(default=None, gt=0)
    max_height: int | None = Field(default=None, gt=0)


class DatasetVersionQualityReport(BaseModel):
    dataset_version_id: UUID
    schema_version: Literal["1.0"]
    asset_count: int = Field(ge=0)
    split_counts: dict[str, int]
    annotated_asset_count: int = Field(ge=0)
    unannotated_asset_count: int = Field(ge=0)
    annotation_coverage_percent: float = Field(ge=0, le=100)
    class_distribution: list[DatasetVersionClassDistribution]
    image_dimensions: DatasetVersionImageDimensions
    advisories: list[str]
