"""index active run leases for stale recovery

Revision ID: 20260809_0006
Revises: 20260808_0005
Create Date: 2026-08-09
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260809_0006"
down_revision: str | None = "20260808_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_runs_status_heartbeat_at",
        "runs",
        ["status", "heartbeat_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_runs_status_heartbeat_at", table_name="runs")
