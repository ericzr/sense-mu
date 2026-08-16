"""add user accounts and workspace memberships

Revision ID: 20260809_0014
Revises: 20260809_0013
Create Date: 2026-08-09
"""

from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID, uuid4

import sqlalchemy as sa
from alembic import op

revision: str = "20260809_0014"
down_revision: str | None = "20260809_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "user_accounts",
        sa.Column("issuer", sa.String(length=255), nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("display_name", sa.String(length=160), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("issuer", "subject"),
    )
    op.create_table(
        "workspace_memberships",
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["user_accounts.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspaces.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", "user_id"),
    )
    op.create_index(
        "ix_workspace_memberships_user_status",
        "workspace_memberships",
        ["user_id", "status"],
    )

    connection = op.get_bind()
    workspace_ids = list(
        connection.execute(sa.text("SELECT id FROM workspaces")).scalars()
    )
    legacy_user_id = uuid4()
    now = datetime.now(UTC)
    user_accounts = sa.table(
        "user_accounts",
        sa.column("id", sa.Uuid()),
        sa.column("issuer", sa.String()),
        sa.column("subject", sa.String()),
        sa.column("email", sa.String()),
        sa.column("display_name", sa.String()),
        sa.column("status", sa.String()),
        sa.column("last_seen_at", sa.DateTime(timezone=True)),
    )
    op.bulk_insert(
        user_accounts,
        [
            {
                "id": legacy_user_id,
                "issuer": "urn:sensemu:migration",
                "subject": "legacy-workspace-owner",
                "email": None,
                "display_name": "历史工作区托管账号",
                "status": "inactive",
                "last_seen_at": None,
            }
        ],
    )
    memberships = sa.table(
        "workspace_memberships",
        sa.column("id", sa.Uuid()),
        sa.column("workspace_id", sa.Uuid()),
        sa.column("user_id", sa.Uuid()),
        sa.column("role", sa.String()),
        sa.column("status", sa.String()),
        sa.column("joined_at", sa.DateTime(timezone=True)),
    )
    membership_rows = [
        {
            "id": uuid4(),
            "workspace_id": UUID(str(workspace_id)),
            "user_id": legacy_user_id,
            "role": "owner",
            "status": "active",
            "joined_at": now,
        }
        for workspace_id in workspace_ids
    ]
    if membership_rows:
        op.bulk_insert(memberships, membership_rows)
    if connection.dialect.name == "sqlite":
        op.execute("PRAGMA optimize")


def downgrade() -> None:
    op.drop_index(
        "ix_workspace_memberships_user_status",
        table_name="workspace_memberships",
    )
    op.drop_table("workspace_memberships")
    op.drop_table("user_accounts")
