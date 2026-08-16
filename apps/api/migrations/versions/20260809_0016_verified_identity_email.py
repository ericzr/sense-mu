"""persist verified identity email state

Revision ID: 20260809_0016
Revises: 20260809_0015
Create Date: 2026-08-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260809_0016"
down_revision: str | None = "20260809_0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "user_accounts",
        sa.Column(
            "email_verified",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
    )
    op.execute(
        sa.text(
            "UPDATE user_accounts SET email_verified = :verified "
            "WHERE issuer = :issuer"
        ).bindparams(verified=True, issuer="urn:sensemu:development")
    )


def downgrade() -> None:
    op.drop_column("user_accounts", "email_verified")
