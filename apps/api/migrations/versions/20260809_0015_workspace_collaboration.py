"""add workspace invitations and access audit

Revision ID: 20260809_0015
Revises: 20260809_0014
Create Date: 2026-08-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260809_0015"
down_revision: str | None = "20260809_0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "workspace_invitations",
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("normalized_email", sa.String(length=320), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("token_prefix", sa.String(length=24), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("invited_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
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
            ["accepted_by_user_id"], ["user_accounts.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["invited_by_user_id"], ["user_accounts.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspaces.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index(
        "ix_workspace_invitations_workspace_status_created_at",
        "workspace_invitations",
        ["workspace_id", "status", "created_at"],
    )
    op.create_table(
        "workspace_access_events",
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("target_user_id", sa.Uuid(), nullable=True),
        sa.Column("invitation_id", sa.Uuid(), nullable=True),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["actor_user_id"], ["user_accounts.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["invitation_id"], ["workspace_invitations.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["target_user_id"], ["user_accounts.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspaces.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_workspace_access_events_workspace_occurred_at",
        "workspace_access_events",
        ["workspace_id", "occurred_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_workspace_access_events_workspace_occurred_at",
        table_name="workspace_access_events",
    )
    op.drop_table("workspace_access_events")
    op.drop_index(
        "ix_workspace_invitations_workspace_status_created_at",
        table_name="workspace_invitations",
    )
    op.drop_table("workspace_invitations")
