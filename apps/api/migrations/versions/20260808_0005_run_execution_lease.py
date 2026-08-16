"""add run execution lease

Revision ID: 20260808_0005
Revises: 20260808_0004
Create Date: 2026-08-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260808_0005"
down_revision: str | None = "20260808_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("runs") as batch_op:
        batch_op.add_column(sa.Column("execution_token", sa.Uuid(), nullable=True))
        batch_op.add_column(
            sa.Column(
                "execution_attempt",
                sa.Integer(),
                nullable=False,
                server_default="0",
            )
        )
        batch_op.add_column(sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.create_index("ix_runs_execution_token", ["execution_token"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("runs") as batch_op:
        batch_op.drop_index("ix_runs_execution_token")
        batch_op.drop_column("heartbeat_at")
        batch_op.drop_column("claimed_at")
        batch_op.drop_column("execution_attempt")
        batch_op.drop_column("execution_token")
