"""add template workflow specs

Revision ID: 20260810_0023
Revises: 20260810_0022
Create Date: 2026-08-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260810_0023"
down_revision: str | None = "20260810_0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "workflow_specs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("capability_spec_id", sa.Uuid(), nullable=False),
        sa.Column("workflow_slug", sa.String(length=80), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("display_name", sa.String(length=180), nullable=False),
        sa.Column("template_key", sa.String(length=80), nullable=False),
        sa.Column("event_types", sa.JSON(), nullable=False),
        sa.Column("deduplication_window_seconds", sa.Integer(), nullable=False),
        sa.Column("webhook_url", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("spec_uri", sa.Text(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspaces.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["capability_spec_id"], ["capability_specs.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "workspace_id",
            "workflow_slug",
            "version_number",
            name="uq_workflow_specs_workspace_slug_version",
        ),
        sa.UniqueConstraint("content_hash"),
    )
    op.create_index(
        "ix_workflow_specs_workspace_slug_version",
        "workflow_specs",
        ["workspace_id", "workflow_slug", "version_number"],
    )
    if op.get_bind().dialect.name == "sqlite":
        op.execute("PRAGMA optimize")


def downgrade() -> None:
    op.drop_index(
        "ix_workflow_specs_workspace_slug_version",
        table_name="workflow_specs",
    )
    op.drop_table("workflow_specs")
