"""add project lifecycle status

Revision ID: 20260811_0029
Revises: 20260811_0028
Create Date: 2026-08-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260811_0029"
down_revision: str | None = "20260811_0028"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "projects",
        sa.Column("status", sa.String(length=24), nullable=False, server_default="active"),
    )


def downgrade() -> None:
    op.drop_column("projects", "status")
