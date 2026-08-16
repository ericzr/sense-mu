"""add vision events and webhook deliveries

Revision ID: 20260810_0024
Revises: 20260810_0023
Create Date: 2026-08-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260810_0024"
down_revision: str | None = "20260810_0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "vision_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("workflow_spec_id", sa.Uuid(), nullable=False),
        sa.Column("capability_spec_id", sa.Uuid(), nullable=False),
        sa.Column("request_id", sa.String(length=100), nullable=False),
        sa.Column("idempotency_key", sa.String(length=120), nullable=False),
        sa.Column("event_type", sa.String(length=120), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workflow_spec_id"], ["workflow_specs.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["capability_spec_id"], ["capability_specs.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "workflow_spec_id", "idempotency_key", name="uq_vision_events_workflow_idempotency"
        ),
    )
    op.create_index(
        "ix_vision_events_workspace_occurred_at",
        "vision_events",
        ["workspace_id", "occurred_at"],
    )
    op.create_table(
        "webhook_deliveries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("vision_event_id", sa.Uuid(), nullable=False),
        sa.Column("workflow_spec_id", sa.Uuid(), nullable=False),
        sa.Column("target_url", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["vision_event_id"], ["vision_events.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["workflow_spec_id"], ["workflow_specs.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("vision_event_id", name="uq_webhook_deliveries_vision_event"),
    )
    op.create_index(
        "ix_webhook_deliveries_status_next_attempt_at",
        "webhook_deliveries",
        ["status", "next_attempt_at"],
    )
    if op.get_bind().dialect.name == "sqlite":
        op.execute("PRAGMA optimize")


def downgrade() -> None:
    op.drop_index("ix_webhook_deliveries_status_next_attempt_at", table_name="webhook_deliveries")
    op.drop_table("webhook_deliveries")
    op.drop_index("ix_vision_events_workspace_occurred_at", table_name="vision_events")
    op.drop_table("vision_events")
