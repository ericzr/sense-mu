"""persist dataset draft class maps

Revision ID: 20260814_0034
Revises: 20260814_0033
Create Date: 2026-08-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260814_0034"
down_revision: str | None = "20260814_0033"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("datasets") as batch_op:
        batch_op.add_column(
            sa.Column(
                "class_map",
                sa.JSON(),
                nullable=False,
                server_default=sa.text("'{}'"),
            )
        )
    op.execute(
        """
        UPDATE datasets
        SET class_map = COALESCE(
            (
                SELECT dataset_versions.class_map
                FROM dataset_versions
                WHERE dataset_versions.dataset_id = datasets.id
                ORDER BY dataset_versions.version_number DESC
                LIMIT 1
            ),
            '{}'
        )
        """
    )


def downgrade() -> None:
    with op.batch_alter_table("datasets") as batch_op:
        batch_op.drop_column("class_map")
