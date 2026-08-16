"""add provider-neutral marketplace payment state

Revision ID: 20260809_0012
Revises: 20260809_0011
Create Date: 2026-08-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260809_0012"
down_revision: str | None = "20260809_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "marketplace_payment_intents",
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("expected_amount_micros", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=True),
        sa.Column("provider_payment_id", sa.String(length=180), nullable=True),
        sa.Column("paid_amount_micros", sa.BigInteger(), nullable=False),
        sa.Column("refunded_amount_micros", sa.BigInteger(), nullable=False),
        sa.Column("last_event_at", sa.DateTime(timezone=True), nullable=True),
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
            ["order_id"], ["marketplace_orders.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("order_id"),
        sa.UniqueConstraint("provider", "provider_payment_id"),
    )
    op.create_table(
        "marketplace_payment_events",
        sa.Column("payment_intent_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("external_event_id", sa.String(length=180), nullable=False),
        sa.Column("provider_payment_id", sa.String(length=180), nullable=False),
        sa.Column("event_type", sa.String(length=48), nullable=False),
        sa.Column("amount_micros", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("payload_sha256", sa.String(length=64), nullable=False),
        sa.Column("processing_status", sa.String(length=32), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["payment_intent_id"],
            ["marketplace_payment_intents.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "external_event_id"),
    )
    op.create_table(
        "marketplace_refunds",
        sa.Column("payment_intent_id", sa.Uuid(), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("payment_event_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("provider_refund_id", sa.String(length=180), nullable=False),
        sa.Column("amount_micros", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("reason", sa.String(length=240), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["order_id"], ["marketplace_orders.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["payment_event_id"],
            ["marketplace_payment_events.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["payment_intent_id"],
            ["marketplace_payment_intents.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("payment_event_id"),
        sa.UniqueConstraint("provider", "provider_refund_id"),
    )
    if op.get_bind().dialect.name == "sqlite":
        op.execute("PRAGMA optimize")


def downgrade() -> None:
    op.drop_table("marketplace_refunds")
    op.drop_table("marketplace_payment_events")
    op.drop_table("marketplace_payment_intents")
