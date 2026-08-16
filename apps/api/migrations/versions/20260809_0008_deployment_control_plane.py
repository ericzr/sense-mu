"""complete deployment control-plane records

Revision ID: 20260809_0008
Revises: 20260809_0007
Create Date: 2026-08-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260809_0008"
down_revision: str | None = "20260809_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("deployments") as batch_op:
        batch_op.add_column(sa.Column("evaluation_id", sa.Uuid(), nullable=True))
        batch_op.add_column(sa.Column("spec_uri", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("api_key_prefix", sa.String(length=24), nullable=True))
        batch_op.add_column(sa.Column("api_key_hash", sa.String(length=64), nullable=True))
        batch_op.add_column(
            sa.Column("published_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(
            sa.Column("disabled_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.create_foreign_key(
            "fk_deployments_evaluation_id_evaluations",
            "evaluations",
            ["evaluation_id"],
            ["id"],
            ondelete="RESTRICT",
        )


def downgrade() -> None:
    with op.batch_alter_table("deployments") as batch_op:
        batch_op.drop_constraint(
            "fk_deployments_evaluation_id_evaluations",
            type_="foreignkey",
        )
        batch_op.drop_column("disabled_at")
        batch_op.drop_column("published_at")
        batch_op.drop_column("api_key_hash")
        batch_op.drop_column("api_key_prefix")
        batch_op.drop_column("spec_uri")
        batch_op.drop_column("evaluation_id")
