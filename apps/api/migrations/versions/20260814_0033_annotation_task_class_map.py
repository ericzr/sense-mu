"""persist annotation task class maps

Revision ID: 20260814_0033
Revises: 20260814_0032
Create Date: 2026-08-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260814_0033"
down_revision: str | None = "20260814_0032"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("annotation_tasks") as batch_op:
        batch_op.add_column(
            sa.Column(
                "class_map",
                sa.JSON(),
                nullable=False,
                server_default=sa.text("'{}'"),
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("annotation_tasks") as batch_op:
        batch_op.drop_column("class_map")
