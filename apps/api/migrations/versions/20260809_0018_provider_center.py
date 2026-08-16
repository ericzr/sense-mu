"""add provider profiles and provider sales index

Revision ID: 20260809_0018
Revises: 20260809_0017
Create Date: 2026-08-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260809_0018"
down_revision: str | None = "20260809_0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "provider_profiles",
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("public_name", sa.String(length=160), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("provider_type", sa.String(length=32), nullable=False),
        sa.Column("support_email", sa.String(length=320), nullable=False),
        sa.Column("website_url", sa.Text(), nullable=True),
        sa.Column("service_regions", sa.JSON(), nullable=False),
        sa.Column("support_commitment", sa.Text(), nullable=False),
        sa.Column("onboarding_status", sa.String(length=32), nullable=False),
        sa.Column("identity_verification_status", sa.String(length=32), nullable=False),
        sa.Column("payout_onboarding_status", sa.String(length=32), nullable=False),
        sa.Column("review_status", sa.String(length=32), nullable=False),
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
            ["workspace_id"], ["workspaces.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id"),
    )
    op.create_index(
        "ix_marketplace_orders_provider_created_at",
        "marketplace_orders",
        ["provider_workspace_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_marketplace_orders_provider_created_at",
        table_name="marketplace_orders",
    )
    op.drop_table("provider_profiles")
