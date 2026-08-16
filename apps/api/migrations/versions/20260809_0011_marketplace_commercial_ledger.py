"""add immutable marketplace orders and usage accrual ledger

Revision ID: 20260809_0011
Revises: 20260809_0010
Create Date: 2026-08-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260809_0011"
down_revision: str | None = "20260809_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "marketplace_orders",
        sa.Column("order_number", sa.String(length=40), nullable=False),
        sa.Column("listing_id", sa.Uuid(), nullable=False),
        sa.Column("subscription_id", sa.Uuid(), nullable=False),
        sa.Column("buyer_workspace_id", sa.Uuid(), nullable=False),
        sa.Column("provider_workspace_id", sa.Uuid(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("price_per_1000_cents", sa.Integer(), nullable=False),
        sa.Column("quota_units", sa.Integer(), nullable=False),
        sa.Column("authorization_amount_micros", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("payment_status", sa.String(length=32), nullable=False),
        sa.Column("entitlement_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("entitlement_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["listing_id"], ["marketplace_listings.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["subscription_id"], ["marketplace_subscriptions.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["buyer_workspace_id"], ["workspaces.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["provider_workspace_id"], ["workspaces.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("order_number"),
    )
    op.create_index(
        "ix_marketplace_orders_buyer_created_at",
        "marketplace_orders",
        ["buyer_workspace_id", "created_at"],
    )
    op.create_table(
        "marketplace_ledger_entries",
        sa.Column("usage_record_id", sa.Uuid(), nullable=False),
        sa.Column("listing_id", sa.Uuid(), nullable=False),
        sa.Column("subscription_id", sa.Uuid(), nullable=False),
        sa.Column("buyer_workspace_id", sa.Uuid(), nullable=False),
        sa.Column("provider_workspace_id", sa.Uuid(), nullable=False),
        sa.Column("entry_type", sa.String(length=32), nullable=False),
        sa.Column("amount_micros", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("settlement_status", sa.String(length=32), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["usage_record_id"], ["usage_records.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["listing_id"], ["marketplace_listings.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["subscription_id"], ["marketplace_subscriptions.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["buyer_workspace_id"], ["workspaces.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["provider_workspace_id"], ["workspaces.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("usage_record_id"),
    )
    op.create_index(
        "ix_marketplace_ledger_provider_status_occurred_at",
        "marketplace_ledger_entries",
        ["provider_workspace_id", "settlement_status", "occurred_at"],
    )
    if op.get_bind().dialect.name == "sqlite":
        op.execute("PRAGMA optimize")


def downgrade() -> None:
    op.drop_index(
        "ix_marketplace_ledger_provider_status_occurred_at",
        table_name="marketplace_ledger_entries",
    )
    op.drop_table("marketplace_ledger_entries")
    op.drop_index(
        "ix_marketplace_orders_buyer_created_at", table_name="marketplace_orders"
    )
    op.drop_table("marketplace_orders")
