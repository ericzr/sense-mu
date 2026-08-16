"""add immutable data delivery specifications

Revision ID: 20260811_0027
Revises: 20260810_0026
Create Date: 2026-08-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260811_0027"
down_revision: str | None = "20260810_0026"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "data_delivery_specs",
        sa.Column("listing_id", sa.Uuid(), nullable=False),
        sa.Column("schema_version", sa.String(length=16), nullable=False),
        sa.Column("delivery_mode", sa.String(length=80), nullable=False),
        sa.Column("delivery_status", sa.String(length=32), nullable=False),
        sa.Column("access_boundary", sa.JSON(), nullable=False),
        sa.Column("activation_requirements", sa.JSON(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("spec_uri", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["listing_id"], ["data_marketplace_listings.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("listing_id"),
    )
    op.create_index(
        "ix_data_delivery_specs_status_created_at",
        "data_delivery_specs",
        ["delivery_status", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_data_delivery_specs_status_created_at",
        table_name="data_delivery_specs",
    )
    op.drop_table("data_delivery_specs")
