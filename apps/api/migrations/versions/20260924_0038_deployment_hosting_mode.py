"""persist deployment hosting mode"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260924_0038"
down_revision: str | None = "20260924_0037"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("deployments") as batch_op:
        batch_op.add_column(
            sa.Column(
                "hosting_mode",
                sa.String(length=32),
                nullable=False,
                server_default="sensemu_managed",
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("deployments") as batch_op:
        batch_op.drop_column("hosting_mode")
