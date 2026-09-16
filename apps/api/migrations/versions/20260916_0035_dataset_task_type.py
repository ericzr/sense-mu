"""persist task type on datasets and frozen versions

Revision ID: 20260916_0035
Revises: 20260814_0034
Create Date: 2026-09-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260916_0035"
down_revision: str | None = "20260814_0034"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("datasets") as batch_op:
        batch_op.add_column(
            sa.Column(
                "task_type",
                sa.String(length=40),
                nullable=False,
                server_default="object-detection",
            )
        )
    op.execute(
        """
        UPDATE datasets
        SET task_type = COALESCE(
            (SELECT projects.task_type FROM projects WHERE projects.id = datasets.project_id),
            'object-detection'
        )
        """
    )

    with op.batch_alter_table("dataset_versions") as batch_op:
        batch_op.add_column(
            sa.Column(
                "task_type",
                sa.String(length=40),
                nullable=False,
                server_default="object-detection",
            )
        )
    op.execute(
        """
        UPDATE dataset_versions
        SET task_type = COALESCE(
            (
                SELECT datasets.task_type
                FROM datasets
                WHERE datasets.id = dataset_versions.dataset_id
            ),
            'object-detection'
        )
        """
    )


def downgrade() -> None:
    with op.batch_alter_table("dataset_versions") as batch_op:
        batch_op.drop_column("task_type")
    with op.batch_alter_table("datasets") as batch_op:
        batch_op.drop_column("task_type")
