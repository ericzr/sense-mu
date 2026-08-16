"""add video extraction jobs

Revision ID: 20260813_0031
Revises: 20260813_0030
Create Date: 2026-08-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260813_0031"
down_revision: str | None = "20260813_0030"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "dataset_items",
        sa.Column(
            "item_role",
            sa.String(length=24),
            nullable=False,
            server_default="training_asset",
        ),
    )
    op.create_table(
        "video_extraction_jobs",
        sa.Column("dataset_id", sa.Uuid(), nullable=False),
        sa.Column("source_asset_id", sa.Uuid(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=120), nullable=False),
        sa.Column("frame_interval_ms", sa.Integer(), nullable=False),
        sa.Column("deduplicate", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="queued"),
        sa.Column("progress", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("frames_created", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("artifact_prefix", sa.Text(), nullable=True),
        sa.Column("execution_token", sa.Uuid(), nullable=True),
        sa.Column("execution_attempt", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["dataset_id"], ["datasets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_asset_id"], ["assets.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("dataset_id", "idempotency_key"),
    )
    op.create_index("ix_video_extraction_jobs_dataset_id", "video_extraction_jobs", ["dataset_id"])
    op.create_index(
        "ix_video_extraction_jobs_dataset_status_created_at",
        "video_extraction_jobs",
        ["dataset_id", "status", "created_at"],
    )
    op.create_index(
        "ix_video_extraction_jobs_status_heartbeat_at",
        "video_extraction_jobs",
        ["status", "heartbeat_at"],
    )
    op.create_index("ix_video_extraction_jobs_execution_token", "video_extraction_jobs", ["execution_token"])


def downgrade() -> None:
    op.drop_index("ix_video_extraction_jobs_execution_token", table_name="video_extraction_jobs")
    op.drop_index("ix_video_extraction_jobs_status_heartbeat_at", table_name="video_extraction_jobs")
    op.drop_index(
        "ix_video_extraction_jobs_dataset_status_created_at",
        table_name="video_extraction_jobs",
    )
    op.drop_index("ix_video_extraction_jobs_dataset_id", table_name="video_extraction_jobs")
    op.drop_table("video_extraction_jobs")
    op.drop_column("dataset_items", "item_role")
