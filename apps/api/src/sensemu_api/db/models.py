from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from sensemu_api.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Workspace(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "workspaces"

    slug: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)


class UserAccount(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "user_accounts"
    __table_args__ = (UniqueConstraint("issuer", "subject"),)

    issuer: Mapped[str] = mapped_column(String(255), nullable=False)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str | None] = mapped_column(String(320))
    email_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    display_name: Mapped[str | None] = mapped_column(String(160))
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class WorkspaceMembership(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "workspace_memberships"
    __table_args__ = (
        UniqueConstraint("workspace_id", "user_id"),
        Index("ix_workspace_memberships_user_status", "user_id", "status"),
    )

    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("user_accounts.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class WorkspaceInvitation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "workspace_invitations"
    __table_args__ = (
        Index(
            "ix_workspace_invitations_workspace_status_created_at",
            "workspace_id",
            "status",
            "created_at",
        ),
    )

    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    normalized_email: Mapped[str] = mapped_column(String(320), nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    token_prefix: Mapped[str] = mapped_column(String(24), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    invited_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("user_accounts.id", ondelete="RESTRICT"), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    accepted_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("user_accounts.id", ondelete="RESTRICT")
    )
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class WorkspaceAccessEvent(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "workspace_access_events"
    __table_args__ = (
        Index(
            "ix_workspace_access_events_workspace_occurred_at",
            "workspace_id",
            "occurred_at",
        ),
    )

    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    actor_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("user_accounts.id", ondelete="RESTRICT"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    target_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("user_accounts.id", ondelete="RESTRICT")
    )
    invitation_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("workspace_invitations.id", ondelete="SET NULL")
    )
    details: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ProviderProfile(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "provider_profiles"

    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    public_name: Mapped[str] = mapped_column(String(160), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    provider_type: Mapped[str] = mapped_column(String(32), nullable=False)
    support_email: Mapped[str] = mapped_column(String(320), nullable=False)
    website_url: Mapped[str | None] = mapped_column(Text)
    service_regions: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    support_commitment: Mapped[str] = mapped_column(Text, nullable=False)
    onboarding_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="profile_complete"
    )
    identity_verification_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="not_started"
    )
    payout_onboarding_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="not_started"
    )
    review_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="not_submitted"
    )


class Project(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "projects"
    __table_args__ = (UniqueConstraint("workspace_id", "slug"),)

    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    slug: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    task_type: Mapped[str] = mapped_column(String(40), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="active")
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Asset(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "assets"
    __table_args__ = (
        UniqueConstraint("workspace_id", "checksum_sha256"),
        Index("ix_assets_workspace_media_type", "workspace_id", "media_type"),
    )

    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    uri: Mapped[str] = mapped_column(Text, nullable=False)
    media_type: Mapped[str] = mapped_column(String(100), nullable=False)
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    byte_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)


class Dataset(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "datasets"
    __table_args__ = (UniqueConstraint("project_id", "name"),)

    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    class_map: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)


class DatasetItem(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "dataset_items"
    __table_args__ = (
        UniqueConstraint("dataset_id", "asset_id"),
        Index("ix_dataset_items_dataset_split", "dataset_id", "split"),
    )

    dataset_id: Mapped[UUID] = mapped_column(
        ForeignKey("datasets.id", ondelete="CASCADE"),
        nullable=False,
    )
    asset_id: Mapped[UUID] = mapped_column(
        ForeignKey("assets.id", ondelete="RESTRICT"),
        nullable=False,
    )
    split: Mapped[str | None] = mapped_column(String(16))
    annotation_uri: Mapped[str | None] = mapped_column(Text)
    item_role: Mapped[str] = mapped_column(String(24), nullable=False, default="training_asset")
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class DatasetVersion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "dataset_versions"
    __table_args__ = (UniqueConstraint("dataset_id", "version_number"),)

    dataset_id: Mapped[UUID] = mapped_column(
        ForeignKey("datasets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    manifest_uri: Mapped[str] = mapped_column(Text, nullable=False)
    asset_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    class_map: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    frozen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AnnotationTask(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "annotation_tasks"
    __table_args__ = (
        Index("ix_annotation_tasks_dataset_status_created_at", "dataset_id", "status", "created_at"),
    )

    dataset_id: Mapped[UUID] = mapped_column(
        ForeignKey("datasets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    method: Mapped[str] = mapped_column(String(24), nullable=False)
    asset_scope: Mapped[str] = mapped_column(String(24), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="annotating")
    assigned_to_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("user_accounts.id", ondelete="RESTRICT"),
        nullable=False,
    )
    source_video_extraction_job_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("video_extraction_jobs.id", ondelete="SET NULL"),
        unique=True,
    )
    class_map: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)


class AnnotationTaskItem(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "annotation_task_items"
    __table_args__ = (
        UniqueConstraint("task_id", "asset_id"),
        Index("ix_annotation_task_items_task_position", "task_id", "position"),
    )

    task_id: Mapped[UUID] = mapped_column(
        ForeignKey("annotation_tasks.id", ondelete="CASCADE"),
        nullable=False,
    )
    asset_id: Mapped[UUID] = mapped_column(
        ForeignKey("assets.id", ondelete="RESTRICT"),
        nullable=False,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)


class VideoExtractionJob(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Asynchronous conversion of one source video into training-image assets."""

    __tablename__ = "video_extraction_jobs"
    __table_args__ = (
        UniqueConstraint("dataset_id", "idempotency_key"),
        Index(
            "ix_video_extraction_jobs_dataset_status_created_at",
            "dataset_id",
            "status",
            "created_at",
        ),
        Index("ix_video_extraction_jobs_status_heartbeat_at", "status", "heartbeat_at"),
    )

    dataset_id: Mapped[UUID] = mapped_column(
        ForeignKey("datasets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_asset_id: Mapped[UUID] = mapped_column(
        ForeignKey("assets.id", ondelete="RESTRICT"),
        nullable=False,
    )
    idempotency_key: Mapped[str] = mapped_column(String(120), nullable=False)
    frame_interval_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    deduplicate: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="queued")
    progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    frames_created: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_code: Mapped[str | None] = mapped_column(String(80))
    error_message: Mapped[str | None] = mapped_column(Text)
    artifact_prefix: Mapped[str | None] = mapped_column(Text)
    execution_token: Mapped[UUID | None] = mapped_column(index=True)
    execution_attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class VideoExtractionOutput(UUIDPrimaryKeyMixin, Base):
    """A stable link from one extraction frame to its registered dataset asset."""

    __tablename__ = "video_extraction_outputs"
    __table_args__ = (
        UniqueConstraint("job_id", "asset_id"),
        UniqueConstraint("job_id", "frame_index"),
        Index("ix_video_extraction_outputs_job_frame", "job_id", "frame_index"),
    )

    job_id: Mapped[UUID] = mapped_column(
        ForeignKey("video_extraction_jobs.id", ondelete="CASCADE"),
        nullable=False,
    )
    asset_id: Mapped[UUID] = mapped_column(
        ForeignKey("assets.id", ondelete="RESTRICT"),
        nullable=False,
    )
    frame_index: Mapped[int] = mapped_column(Integer, nullable=False)
    timestamp_ms: Mapped[int] = mapped_column(Integer, nullable=False)


class DataMarketplaceListing(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "data_marketplace_listings"
    __table_args__ = (
        Index(
            "ix_data_marketplace_listings_status_published_at",
            "status",
            "published_at",
        ),
    )

    provider_workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    dataset_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("dataset_versions.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    )
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    source_summary: Mapped[str] = mapped_column(Text, nullable=False)
    collection_method: Mapped[str] = mapped_column(Text, nullable=False)
    coverage_summary: Mapped[str] = mapped_column(Text, nullable=False)
    known_limitations: Mapped[str] = mapped_column(Text, nullable=False)
    license_code: Mapped[str] = mapped_column(String(64), nullable=False)
    custom_license_terms: Mapped[str | None] = mapped_column(Text)
    allow_commercial_use: Mapped[bool] = mapped_column(Boolean, nullable=False)
    allow_model_training: Mapped[bool] = mapped_column(Boolean, nullable=False)
    allow_derivative_models: Mapped[bool] = mapped_column(Boolean, nullable=False)
    allow_redistribution: Mapped[bool] = mapped_column(Boolean, nullable=False)
    contains_personal_data: Mapped[bool] = mapped_column(Boolean, nullable=False)
    privacy_treatment: Mapped[str] = mapped_column(Text, nullable=False)
    rights_confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    review_basis: Mapped[str] = mapped_column(
        String(48), nullable=False, default="provider_attestation"
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="published")
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class DataDeliverySpec(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "data_delivery_specs"
    __table_args__ = (
        Index(
            "ix_data_delivery_specs_status_created_at",
            "delivery_status",
            "created_at",
        ),
    )

    listing_id: Mapped[UUID] = mapped_column(
        ForeignKey("data_marketplace_listings.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    schema_version: Mapped[str] = mapped_column(String(16), nullable=False)
    delivery_mode: Mapped[str] = mapped_column(String(80), nullable=False)
    delivery_status: Mapped[str] = mapped_column(String(32), nullable=False)
    access_boundary: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    activation_requirements: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, default=list
    )
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    spec_uri: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Run(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "runs"
    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "idempotency_key",
            name="uq_runs_project_id_idempotency_key",
        ),
        Index("ix_runs_project_status_created_at", "project_id", "status", "created_at"),
        Index("ix_runs_status_heartbeat_at", "status", "heartbeat_at"),
    )

    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    dataset_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("dataset_versions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    run_type: Mapped[str] = mapped_column(String(32), nullable=False, default="training")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued")
    engine: Mapped[str] = mapped_column(String(80), nullable=False)
    executor: Mapped[str] = mapped_column(String(80), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(120), nullable=False)
    recipe: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    artifact_prefix: Mapped[str | None] = mapped_column(Text)
    spec_uri: Mapped[str | None] = mapped_column(Text)
    error_code: Mapped[str | None] = mapped_column(String(80))
    error_message: Mapped[str | None] = mapped_column(Text)
    execution_token: Mapped[UUID | None] = mapped_column(index=True)
    execution_attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RunEvent(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "run_events"
    __table_args__ = (
        UniqueConstraint("run_id", "sequence", name="uq_run_events_run_id_sequence"),
        UniqueConstraint("run_id", "event_id", name="uq_run_events_run_id_event_id"),
        Index("ix_run_events_run_id_sequence", "run_id", "sequence"),
    )

    run_id: Mapped[UUID] = mapped_column(
        ForeignKey("runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    event_id: Mapped[UUID] = mapped_column(nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class BatchInferenceResult(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "batch_inference_results"
    __table_args__ = (
        Index("ix_batch_inference_results_deployment_completed_at", "deployment_id", "completed_at"),
    )

    run_id: Mapped[UUID] = mapped_column(
        ForeignKey("runs.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    deployment_id: Mapped[UUID] = mapped_column(
        ForeignKey("deployments.id", ondelete="RESTRICT"), nullable=False
    )
    output_uri: Mapped[str] = mapped_column(Text, nullable=False)
    report_uri: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Model(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "models"
    __table_args__ = (UniqueConstraint("project_id", "name"),)

    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    task_type: Mapped[str] = mapped_column(String(40), nullable=False)


class ModelVersion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "model_versions"
    __table_args__ = (UniqueConstraint("model_id", "version_number"),)

    model_id: Mapped[UUID] = mapped_column(
        ForeignKey("models.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    run_id: Mapped[UUID] = mapped_column(
        ForeignKey("runs.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="candidate")
    artifact_uri: Mapped[str] = mapped_column(Text, nullable=False)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)


class EvaluationPolicy(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "evaluation_policies"
    __table_args__ = (
        UniqueConstraint("project_id", "version_number"),
        Index("ix_evaluation_policies_project_active", "project_id", "is_active"),
    )

    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    rules: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class Evaluation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "evaluations"
    __table_args__ = (
        UniqueConstraint(
            "model_version_id",
            "policy_id",
            "source",
            "dataset_version_id",
            name="uq_evaluations_model_policy_source_dataset",
        ),
        Index("ix_evaluations_model_evaluated_at", "model_version_id", "evaluated_at"),
    )

    model_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("model_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    dataset_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("dataset_versions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    policy_id: Mapped[UUID] = mapped_column(
        ForeignKey("evaluation_policies.id", ondelete="RESTRICT"),
        nullable=False,
    )
    source: Mapped[str] = mapped_column(String(48), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="completed")
    verdict: Mapped[str] = mapped_column(String(32), nullable=False)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    rule_results: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    report_uri: Mapped[str] = mapped_column(Text, nullable=False)
    evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Deployment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "deployments"
    __table_args__ = (
        UniqueConstraint("workspace_id", "endpoint_slug"),
        Index("ix_deployments_workspace_status", "workspace_id", "status"),
    )

    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    model_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("model_versions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    evaluation_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("evaluations.id", ondelete="RESTRICT"),
    )
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    endpoint_slug: Mapped[str] = mapped_column(String(120), nullable=False)
    environment: Mapped[str] = mapped_column(String(32), nullable=False, default="production")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="provisioning")
    spec_uri: Mapped[str | None] = mapped_column(Text)
    api_key_prefix: Mapped[str | None] = mapped_column(String(24))
    api_key_hash: Mapped[str | None] = mapped_column(String(64))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    disabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CapabilitySpec(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "capability_specs"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "capability_slug",
            "version_number",
            name="uq_capability_specs_workspace_slug_version",
        ),
        UniqueConstraint("deployment_id", name="uq_capability_specs_deployment"),
        Index(
            "ix_capability_specs_workspace_slug_version",
            "workspace_id",
            "capability_slug",
            "version_number",
        ),
    )

    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    deployment_id: Mapped[UUID] = mapped_column(
        ForeignKey("deployments.id", ondelete="RESTRICT"), nullable=False
    )
    capability_slug: Mapped[str] = mapped_column(String(80), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    display_name: Mapped[str] = mapped_column(String(180), nullable=False)
    problem_definition: Mapped[str] = mapped_column(Text, nullable=False)
    input_spec: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    output_spec: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    applicability: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    delivery: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="published")
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    spec_uri: Mapped[str] = mapped_column(Text, nullable=False)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class WorkflowSpec(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "workflow_specs"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "workflow_slug",
            "version_number",
            name="uq_workflow_specs_workspace_slug_version",
        ),
        Index(
            "ix_workflow_specs_workspace_slug_version",
            "workspace_id",
            "workflow_slug",
            "version_number",
        ),
    )

    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    capability_spec_id: Mapped[UUID] = mapped_column(
        ForeignKey("capability_specs.id", ondelete="RESTRICT"), nullable=False
    )
    workflow_slug: Mapped[str] = mapped_column(String(80), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    display_name: Mapped[str] = mapped_column(String(180), nullable=False)
    template_key: Mapped[str] = mapped_column(String(80), nullable=False)
    event_types: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    deduplication_window_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    webhook_url: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="published")
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    spec_uri: Mapped[str] = mapped_column(Text, nullable=False)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class VisionEvent(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "vision_events"
    __table_args__ = (
        UniqueConstraint(
            "workflow_spec_id",
            "idempotency_key",
            name="uq_vision_events_workflow_idempotency",
        ),
        Index("ix_vision_events_workspace_occurred_at", "workspace_id", "occurred_at"),
        Index(
            "ix_vision_events_workflow_event_dedupe_occurred_at",
            "workflow_spec_id",
            "event_type",
            "deduplication_key",
            "occurred_at",
        ),
    )

    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    workflow_spec_id: Mapped[UUID] = mapped_column(
        ForeignKey("workflow_specs.id", ondelete="RESTRICT"), nullable=False
    )
    capability_spec_id: Mapped[UUID] = mapped_column(
        ForeignKey("capability_specs.id", ondelete="RESTRICT"), nullable=False
    )
    request_id: Mapped[str] = mapped_column(String(100), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(120), nullable=False)
    deduplication_key: Mapped[str] = mapped_column(String(160), nullable=False)
    event_type: Mapped[str] = mapped_column(String(120), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class WebhookDelivery(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "webhook_deliveries"
    __table_args__ = (
        UniqueConstraint("vision_event_id", name="uq_webhook_deliveries_vision_event"),
        Index(
            "ix_webhook_deliveries_status_next_attempt_at",
            "status",
            "next_attempt_at",
        ),
    )

    vision_event_id: Mapped[UUID] = mapped_column(
        ForeignKey("vision_events.id", ondelete="RESTRICT"), nullable=False
    )
    workflow_spec_id: Mapped[UUID] = mapped_column(
        ForeignKey("workflow_specs.id", ondelete="RESTRICT"), nullable=False
    )
    target_url: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class MarketplaceListing(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "marketplace_listings"
    __table_args__ = (
        Index("ix_marketplace_listings_status_published_at", "status", "published_at"),
    )

    provider_workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    deployment_id: Mapped[UUID] = mapped_column(
        ForeignKey("deployments.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    )
    capability_spec_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("capability_specs.id", ondelete="RESTRICT"),
        unique=True,
    )
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    pricing_unit: Mapped[str] = mapped_column(String(32), nullable=False, default="image")
    price_per_1000_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    monthly_quota_units: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pending_review"
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class MarketplaceListingReview(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "marketplace_listing_reviews"
    __table_args__ = (
        Index(
            "ix_marketplace_listing_reviews_listing_reviewed_at",
            "listing_id",
            "reviewed_at",
        ),
    )

    listing_id: Mapped[UUID] = mapped_column(
        ForeignKey("marketplace_listings.id", ondelete="RESTRICT"),
        nullable=False,
    )
    decision: Mapped[str] = mapped_column(String(32), nullable=False)
    reviewer_identity: Mapped[str] = mapped_column(String(160), nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
    reviewed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class MarketplaceSubscription(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "marketplace_subscriptions"
    __table_args__ = (
        UniqueConstraint("listing_id", "buyer_workspace_id"),
        Index(
            "ix_marketplace_subscriptions_buyer_status",
            "buyer_workspace_id",
            "status",
        ),
    )

    listing_id: Mapped[UUID] = mapped_column(
        ForeignKey("marketplace_listings.id", ondelete="RESTRICT"),
        nullable=False,
    )
    buyer_workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pending_payment"
    )
    quota_units: Mapped[int] = mapped_column(Integer, nullable=False)
    reserved_units: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    consumed_units: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    price_per_1000_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    api_key_prefix: Mapped[str | None] = mapped_column(String(24))
    api_key_hash: Mapped[str | None] = mapped_column(String(64), unique=True)
    credential_claimed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class MarketplaceOrder(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "marketplace_orders"
    __table_args__ = (
        Index(
            "ix_marketplace_orders_buyer_created_at",
            "buyer_workspace_id",
            "created_at",
        ),
        Index(
            "ix_marketplace_orders_provider_created_at",
            "provider_workspace_id",
            "created_at",
        ),
    )

    order_number: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    listing_id: Mapped[UUID] = mapped_column(
        ForeignKey("marketplace_listings.id", ondelete="RESTRICT"), nullable=False
    )
    subscription_id: Mapped[UUID] = mapped_column(
        ForeignKey("marketplace_subscriptions.id", ondelete="RESTRICT"), nullable=False
    )
    buyer_workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="RESTRICT"), nullable=False
    )
    provider_workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="RESTRICT"), nullable=False
    )
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="CNY")
    price_per_1000_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    quota_units: Mapped[int] = mapped_column(Integer, nullable=False)
    authorization_amount_micros: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="payment_pending"
    )
    payment_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="not_collected"
    )
    entitlement_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    entitlement_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )


class MarketplacePaymentIntent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "marketplace_payment_intents"
    __table_args__ = (UniqueConstraint("provider", "provider_payment_id"),)

    order_id: Mapped[UUID] = mapped_column(
        ForeignKey("marketplace_orders.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    )
    expected_amount_micros: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="CNY")
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="requires_provider"
    )
    provider: Mapped[str | None] = mapped_column(String(64))
    provider_payment_id: Mapped[str | None] = mapped_column(String(180))
    paid_amount_micros: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    refunded_amount_micros: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0
    )
    last_event_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class MarketplacePaymentEvent(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "marketplace_payment_events"
    __table_args__ = (UniqueConstraint("provider", "external_event_id"),)

    payment_intent_id: Mapped[UUID] = mapped_column(
        ForeignKey("marketplace_payment_intents.id", ondelete="RESTRICT"),
        nullable=False,
    )
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    external_event_id: Mapped[str] = mapped_column(String(180), nullable=False)
    provider_payment_id: Mapped[str] = mapped_column(String(180), nullable=False)
    event_type: Mapped[str] = mapped_column(String(48), nullable=False)
    amount_micros: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    payload_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    processing_status: Mapped[str] = mapped_column(String(32), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    verified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class MarketplaceRefund(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "marketplace_refunds"
    __table_args__ = (UniqueConstraint("provider", "provider_refund_id"),)

    payment_intent_id: Mapped[UUID] = mapped_column(
        ForeignKey("marketplace_payment_intents.id", ondelete="RESTRICT"),
        nullable=False,
    )
    order_id: Mapped[UUID] = mapped_column(
        ForeignKey("marketplace_orders.id", ondelete="RESTRICT"), nullable=False
    )
    payment_event_id: Mapped[UUID] = mapped_column(
        ForeignKey("marketplace_payment_events.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    )
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    provider_refund_id: Mapped[str] = mapped_column(String(180), nullable=False)
    amount_micros: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(240))
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="succeeded")
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class UsageReservation(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "usage_reservations"
    __table_args__ = (
        Index("ix_usage_reservations_subscription_status", "subscription_id", "status"),
        Index("ix_usage_reservations_status_created_at", "status", "created_at"),
    )

    subscription_id: Mapped[UUID] = mapped_column(
        ForeignKey("marketplace_subscriptions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    deployment_id: Mapped[UUID] = mapped_column(
        ForeignKey("deployments.id", ondelete="RESTRICT"),
        nullable=False,
    )
    request_id: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    units: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class UsageRecord(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "usage_records"
    __table_args__ = (
        Index("ix_usage_records_workspace_occurred_at", "workspace_id", "occurred_at"),
        Index(
            "ix_usage_records_subscription_occurred_at",
            "subscription_id",
            "occurred_at",
        ),
    )

    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="RESTRICT"),
        nullable=False,
    )
    deployment_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("deployments.id", ondelete="SET NULL")
    )
    listing_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("marketplace_listings.id", ondelete="SET NULL")
    )
    subscription_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("marketplace_subscriptions.id", ondelete="SET NULL")
    )
    request_id: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    capability_id: Mapped[str] = mapped_column(String(64), nullable=False)
    billable_units: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    unit: Mapped[str] = mapped_column(String(32), nullable=False)
    dimensions: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class MarketplaceLedgerEntry(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "marketplace_ledger_entries"
    __table_args__ = (
        Index(
            "ix_marketplace_ledger_provider_status_occurred_at",
            "provider_workspace_id",
            "settlement_status",
            "occurred_at",
        ),
    )

    usage_record_id: Mapped[UUID] = mapped_column(
        ForeignKey("usage_records.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    )
    listing_id: Mapped[UUID] = mapped_column(
        ForeignKey("marketplace_listings.id", ondelete="RESTRICT"), nullable=False
    )
    subscription_id: Mapped[UUID] = mapped_column(
        ForeignKey("marketplace_subscriptions.id", ondelete="RESTRICT"), nullable=False
    )
    buyer_workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="RESTRICT"), nullable=False
    )
    provider_workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="RESTRICT"), nullable=False
    )
    entry_type: Mapped[str] = mapped_column(
        String(32), nullable=False, default="usage_accrual"
    )
    amount_micros: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="CNY")
    settlement_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="unsettled"
    )
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
