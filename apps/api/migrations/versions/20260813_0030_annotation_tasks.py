"""add persistent annotation tasks

Revision ID: 20260813_0030
Revises: 20260811_0029
Create Date: 2026-08-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260813_0030"
down_revision: str | None = "20260811_0029"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "annotation_tasks",
        sa.Column("dataset_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("method", sa.String(length=24), nullable=False),
        sa.Column("asset_scope", sa.String(length=24), nullable=False),
        sa.Column(
            "status",
            sa.String(length=24),
            nullable=False,
            server_default="annotating",
        ),
        sa.Column("assigned_to_user_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["assigned_to_user_id"],
            ["user_accounts.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["dataset_id"], ["datasets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_annotation_tasks_dataset_id",
        "annotation_tasks",
        ["dataset_id"],
    )
    op.create_index(
        "ix_annotation_tasks_dataset_status_created_at",
        "annotation_tasks",
        ["dataset_id", "status", "created_at"],
    )
    op.create_table(
        "annotation_task_items",
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column("asset_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["task_id"], ["annotation_tasks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("task_id", "asset_id"),
    )
    op.create_index(
        "ix_annotation_task_items_task_position",
        "annotation_task_items",
        ["task_id", "position"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_annotation_task_items_task_position",
        table_name="annotation_task_items",
    )
    op.drop_table("annotation_task_items")
    op.drop_index(
        "ix_annotation_tasks_dataset_status_created_at",
        table_name="annotation_tasks",
    )
    op.drop_index("ix_annotation_tasks_dataset_id", table_name="annotation_tasks")
    op.drop_table("annotation_tasks")
