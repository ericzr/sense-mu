"""link video extraction outputs to annotation tasks

Revision ID: 20260814_0032
Revises: 20260813_0031
Create Date: 2026-08-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260814_0032"
down_revision: str | None = "20260813_0031"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "video_extraction_outputs",
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("asset_id", sa.Uuid(), nullable=False),
        sa.Column("frame_index", sa.Integer(), nullable=False),
        sa.Column("timestamp_ms", sa.Integer(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["job_id"],
            ["video_extraction_jobs.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_id", "asset_id"),
        sa.UniqueConstraint("job_id", "frame_index"),
    )
    op.create_index(
        "ix_video_extraction_outputs_job_frame",
        "video_extraction_outputs",
        ["job_id", "frame_index"],
    )
    with op.batch_alter_table("annotation_tasks") as batch_op:
        batch_op.add_column(
            sa.Column("source_video_extraction_job_id", sa.Uuid(), nullable=True)
        )
        batch_op.create_foreign_key(
            "fk_annotation_tasks_source_video_extraction_job_id",
            "video_extraction_jobs",
            ["source_video_extraction_job_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_unique_constraint(
            "uq_annotation_tasks_source_video_extraction_job_id",
            ["source_video_extraction_job_id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("annotation_tasks") as batch_op:
        batch_op.drop_constraint(
            "uq_annotation_tasks_source_video_extraction_job_id",
            type_="unique",
        )
        batch_op.drop_constraint(
            "fk_annotation_tasks_source_video_extraction_job_id",
            type_="foreignkey",
        )
        batch_op.drop_column("source_video_extraction_job_id")
    op.drop_index(
        "ix_video_extraction_outputs_job_frame",
        table_name="video_extraction_outputs",
    )
    op.drop_table("video_extraction_outputs")
