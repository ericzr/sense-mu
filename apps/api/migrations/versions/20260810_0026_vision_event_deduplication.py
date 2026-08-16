"""add time-window event deduplication

Revision ID: 20260810_0026
Revises: 20260810_0025
Create Date: 2026-08-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260810_0026"
down_revision: str | None = "20260810_0025"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("vision_events") as batch_op:
        batch_op.add_column(sa.Column("deduplication_key", sa.String(length=160), nullable=True))
    op.execute(
        "UPDATE vision_events SET deduplication_key = request_id "
        "WHERE deduplication_key IS NULL"
    )
    with op.batch_alter_table("vision_events") as batch_op:
        batch_op.alter_column("deduplication_key", nullable=False)
    op.create_index(
        "ix_vision_events_workflow_event_dedupe_occurred_at",
        "vision_events",
        ["workflow_spec_id", "event_type", "deduplication_key", "occurred_at"],
    )
    if op.get_bind().dialect.name == "sqlite":
        op.execute("PRAGMA optimize")


def downgrade() -> None:
    op.drop_index(
        "ix_vision_events_workflow_event_dedupe_occurred_at",
        table_name="vision_events",
    )
    with op.batch_alter_table("vision_events") as batch_op:
        batch_op.drop_column("deduplication_key")
