"""backfill payment intents for existing marketplace orders

Revision ID: 20260809_0013
Revises: 20260809_0012
Create Date: 2026-08-09
"""

from collections.abc import Sequence
from uuid import uuid4

import sqlalchemy as sa
from alembic import op

revision: str = "20260809_0013"
down_revision: str | None = "20260809_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    connection = op.get_bind()
    orders = connection.execute(
        sa.text(
            "SELECT marketplace_orders.id, "
            "marketplace_orders.authorization_amount_micros, "
            "marketplace_orders.currency "
            "FROM marketplace_orders "
            "LEFT JOIN marketplace_payment_intents "
            "ON marketplace_payment_intents.order_id = marketplace_orders.id "
            "WHERE marketplace_payment_intents.id IS NULL"
        )
    ).mappings()
    payment_intents = sa.table(
        "marketplace_payment_intents",
        sa.column("id", sa.Uuid()),
        sa.column("order_id", sa.Uuid()),
        sa.column("expected_amount_micros", sa.BigInteger()),
        sa.column("currency", sa.String()),
        sa.column("status", sa.String()),
        sa.column("provider", sa.String()),
        sa.column("provider_payment_id", sa.String()),
        sa.column("paid_amount_micros", sa.BigInteger()),
        sa.column("refunded_amount_micros", sa.BigInteger()),
        sa.column("last_event_at", sa.DateTime(timezone=True)),
    )
    rows = [
        {
            "id": uuid4(),
            "order_id": row["id"],
            "expected_amount_micros": row["authorization_amount_micros"],
            "currency": row["currency"],
            "status": "requires_provider",
            "provider": None,
            "provider_payment_id": None,
            "paid_amount_micros": 0,
            "refunded_amount_micros": 0,
            "last_event_at": None,
        }
        for row in orders
    ]
    if rows:
        op.bulk_insert(payment_intents, rows)
    if connection.dialect.name == "sqlite":
        op.execute("PRAGMA optimize")


def downgrade() -> None:
    # 支付意图与后续真实支付事件可能已关联，不在数据迁移回退时删除。
    pass
