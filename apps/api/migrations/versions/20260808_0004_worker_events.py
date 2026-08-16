"""add idempotent worker event identifiers

Revision ID: 20260808_0004
Revises: 20260808_0003
Create Date: 2026-08-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260808_0004"
down_revision: str | None = "20260808_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("run_events") as batch_op:
        batch_op.add_column(sa.Column("event_id", sa.Uuid(), nullable=True))

    op.execute(sa.text("UPDATE run_events SET event_id = id WHERE event_id IS NULL"))

    with op.batch_alter_table("run_events") as batch_op:
        batch_op.alter_column("event_id", existing_type=sa.Uuid(), nullable=False)
        batch_op.create_unique_constraint(
            "uq_run_events_run_id_event_id",
            ["run_id", "event_id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("run_events") as batch_op:
        batch_op.drop_constraint("uq_run_events_run_id_event_id", type_="unique")
        batch_op.drop_column("event_id")
