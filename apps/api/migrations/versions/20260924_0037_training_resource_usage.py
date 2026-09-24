"""persist immutable training resource usage snapshot

Revision ID: 20260924_0037
Revises: 20260917_0036
Create Date: 2026-09-24
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260924_0037"
down_revision: str | None = "20260917_0036"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "runs",
        sa.Column("resource_usage", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("runs", "resource_usage")
