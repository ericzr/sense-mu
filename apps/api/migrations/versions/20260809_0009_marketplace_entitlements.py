"""add marketplace listings, subscriptions and quota reservations

Revision ID: 20260809_0009
Revises: 20260809_0008
Create Date: 2026-08-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260809_0009"
down_revision: str | None = "20260809_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "marketplace_listings",
        sa.Column("provider_workspace_id", sa.Uuid(), nullable=False),
        sa.Column("deployment_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=180), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.Column("pricing_unit", sa.String(length=32), nullable=False),
        sa.Column("price_per_1000_cents", sa.Integer(), nullable=False),
        sa.Column("monthly_quota_units", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["provider_workspace_id"], ["workspaces.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["deployment_id"], ["deployments.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("deployment_id"),
    )
    op.create_index(
        "ix_marketplace_listings_provider_workspace_id",
        "marketplace_listings",
        ["provider_workspace_id"],
    )
    op.create_index(
        "ix_marketplace_listings_status_published_at",
        "marketplace_listings",
        ["status", "published_at"],
    )
    op.create_table(
        "marketplace_subscriptions",
        sa.Column("listing_id", sa.Uuid(), nullable=False),
        sa.Column("buyer_workspace_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("quota_units", sa.Integer(), nullable=False),
        sa.Column("reserved_units", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("consumed_units", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("price_per_1000_cents", sa.Integer(), nullable=False),
        sa.Column("api_key_prefix", sa.String(length=24), nullable=False),
        sa.Column("api_key_hash", sa.String(length=64), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["listing_id"], ["marketplace_listings.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["buyer_workspace_id"], ["workspaces.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("api_key_hash"),
        sa.UniqueConstraint("listing_id", "buyer_workspace_id"),
    )
    op.create_index(
        "ix_marketplace_subscriptions_buyer_status",
        "marketplace_subscriptions",
        ["buyer_workspace_id", "status"],
    )
    op.create_table(
        "usage_reservations",
        sa.Column("subscription_id", sa.Uuid(), nullable=False),
        sa.Column("deployment_id", sa.Uuid(), nullable=False),
        sa.Column("request_id", sa.String(length=100), nullable=False),
        sa.Column("units", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("finalized_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["subscription_id"], ["marketplace_subscriptions.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["deployment_id"], ["deployments.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("request_id"),
    )
    op.create_index(
        "ix_usage_reservations_subscription_status",
        "usage_reservations",
        ["subscription_id", "status"],
    )
    with op.batch_alter_table("usage_records") as batch_op:
        batch_op.add_column(sa.Column("listing_id", sa.Uuid(), nullable=True))
        batch_op.add_column(sa.Column("subscription_id", sa.Uuid(), nullable=True))
        batch_op.create_foreign_key(
            "fk_usage_records_listing_id_marketplace_listings",
            "marketplace_listings",
            ["listing_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_foreign_key(
            "fk_usage_records_subscription_id_marketplace_subscriptions",
            "marketplace_subscriptions",
            ["subscription_id"],
            ["id"],
            ondelete="SET NULL",
        )
    if op.get_bind().dialect.name == "sqlite":
        op.execute("PRAGMA optimize")


def downgrade() -> None:
    with op.batch_alter_table("usage_records") as batch_op:
        batch_op.drop_constraint(
            "fk_usage_records_subscription_id_marketplace_subscriptions",
            type_="foreignkey",
        )
        batch_op.drop_constraint(
            "fk_usage_records_listing_id_marketplace_listings", type_="foreignkey"
        )
        batch_op.drop_column("subscription_id")
        batch_op.drop_column("listing_id")
    op.drop_index(
        "ix_usage_reservations_subscription_status", table_name="usage_reservations"
    )
    op.drop_table("usage_reservations")
    op.drop_index(
        "ix_marketplace_subscriptions_buyer_status",
        table_name="marketplace_subscriptions",
    )
    op.drop_table("marketplace_subscriptions")
    op.drop_index(
        "ix_marketplace_listings_status_published_at", table_name="marketplace_listings"
    )
    op.drop_index(
        "ix_marketplace_listings_provider_workspace_id", table_name="marketplace_listings"
    )
    op.drop_table("marketplace_listings")
