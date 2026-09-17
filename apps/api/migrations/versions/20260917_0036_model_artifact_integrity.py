"""persist model artifact integrity metadata

Revision ID: 20260917_0036
Revises: 20260916_0035
Create Date: 2026-09-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260917_0036"
down_revision: str | None = "20260916_0035"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("model_versions") as batch_op:
        batch_op.add_column(sa.Column("artifact_size_bytes", sa.BigInteger(), nullable=True))
        batch_op.add_column(sa.Column("checksum_sha256", sa.String(length=64), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("model_versions") as batch_op:
        batch_op.drop_column("checksum_sha256")
        batch_op.drop_column("artifact_size_bytes")
