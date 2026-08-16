"""Add persisted training run control-plane fields and events.

Revision ID: 20260808_0003
Revises: 20260808_0002
Create Date: 2026-08-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260808_0003"
down_revision: str | None = "20260808_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("runs") as batch:
        batch.add_column(sa.Column("engine", sa.String(length=80), nullable=True))
        batch.add_column(sa.Column("idempotency_key", sa.String(length=120), nullable=True))
        batch.add_column(sa.Column("spec_uri", sa.Text(), nullable=True))
        batch.add_column(sa.Column("error_code", sa.String(length=80), nullable=True))
        batch.add_column(sa.Column("error_message", sa.Text(), nullable=True))

    op.execute(sa.text("UPDATE runs SET engine = 'ultralytics' WHERE engine IS NULL"))
    op.execute(
        sa.text(
            "UPDATE runs SET idempotency_key = "
            "'legacy-' || CAST(id AS VARCHAR) WHERE idempotency_key IS NULL"
        )
    )

    with op.batch_alter_table("runs") as batch:
        batch.alter_column("engine", existing_type=sa.String(length=80), nullable=False)
        batch.alter_column(
            "idempotency_key",
            existing_type=sa.String(length=120),
            nullable=False,
        )
        batch.create_unique_constraint(
            "uq_runs_project_id_idempotency_key",
            ["project_id", "idempotency_key"],
        )

    op.create_table(
        "run_events",
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("progress", sa.Integer(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["runs.id"],
            name="fk_run_events_run_id_runs",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_run_events"),
        sa.UniqueConstraint(
            "run_id",
            "sequence",
            name="uq_run_events_run_id_sequence",
        ),
    )
    op.create_index(
        "ix_run_events_run_id_sequence",
        "run_events",
        ["run_id", "sequence"],
    )


def downgrade() -> None:
    op.drop_index("ix_run_events_run_id_sequence", table_name="run_events")
    op.drop_table("run_events")
    with op.batch_alter_table("runs") as batch:
        batch.drop_constraint("uq_runs_project_id_idempotency_key", type_="unique")
        batch.drop_column("error_message")
        batch.drop_column("error_code")
        batch.drop_column("spec_uri")
        batch.drop_column("idempotency_key")
        batch.drop_column("engine")
