"""gate marketplace entitlements on verified payment

Revision ID: 20260809_0020
Revises: 20260809_0019
Create Date: 2026-08-09
"""

from collections.abc import Sequence
from hashlib import sha256

import sqlalchemy as sa
from alembic import op

revision: str = "20260809_0020"
down_revision: str | None = "20260809_0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("marketplace_subscriptions") as batch_op:
        batch_op.alter_column(
            "api_key_prefix",
            existing_type=sa.String(length=24),
            nullable=True,
        )
        batch_op.alter_column(
            "api_key_hash",
            existing_type=sa.String(length=64),
            nullable=True,
        )
        batch_op.alter_column(
            "started_at",
            existing_type=sa.DateTime(timezone=True),
            nullable=True,
        )
        batch_op.alter_column(
            "expires_at",
            existing_type=sa.DateTime(timezone=True),
            nullable=True,
        )
        batch_op.add_column(
            sa.Column(
                "credential_claimed_at",
                sa.DateTime(timezone=True),
                nullable=True,
            )
        )
    with op.batch_alter_table("marketplace_orders") as batch_op:
        batch_op.alter_column(
            "entitlement_started_at",
            existing_type=sa.DateTime(timezone=True),
            nullable=True,
        )
        batch_op.alter_column(
            "entitlement_expires_at",
            existing_type=sa.DateTime(timezone=True),
            nullable=True,
        )

    connection = op.get_bind()
    connection.execute(
        sa.text(
            "UPDATE marketplace_subscriptions "
            "SET credential_claimed_at = started_at "
            "WHERE api_key_hash IS NOT NULL"
        )
    )
    latest_orders = list(
        connection.execute(
            sa.text(
                """
            SELECT marketplace_subscriptions.id AS subscription_id,
                   marketplace_orders.payment_status AS payment_status
            FROM marketplace_subscriptions
            JOIN marketplace_orders
              ON marketplace_orders.subscription_id = marketplace_subscriptions.id
            WHERE marketplace_orders.id = (
                SELECT latest.id
                FROM marketplace_orders AS latest
                WHERE latest.subscription_id = marketplace_subscriptions.id
                ORDER BY latest.created_at DESC, latest.id DESC
                LIMIT 1
            )
                """
            )
        ).mappings()
    )
    for row in latest_orders:
        if row["payment_status"] == "not_collected":
            connection.execute(
                sa.text(
                    "UPDATE marketplace_subscriptions "
                    "SET status = 'pending_payment', "
                    "api_key_prefix = NULL, api_key_hash = NULL, "
                    "credential_claimed_at = NULL, "
                    "started_at = NULL, expires_at = NULL, reserved_units = 0 "
                    "WHERE id = :subscription_id"
                ),
                {"subscription_id": row["subscription_id"]},
            )
        elif row["payment_status"] == "refunded":
            connection.execute(
                sa.text(
                    "UPDATE marketplace_subscriptions "
                    "SET status = 'refunded', "
                    "api_key_prefix = NULL, api_key_hash = NULL, "
                    "credential_claimed_at = NULL, reserved_units = 0 "
                    "WHERE id = :subscription_id"
                ),
                {"subscription_id": row["subscription_id"]},
            )
    connection.execute(
        sa.text(
            "UPDATE marketplace_orders "
            "SET status = 'payment_pending', "
            "entitlement_started_at = NULL, entitlement_expires_at = NULL "
            "WHERE payment_status = 'not_collected'"
        )
    )
    connection.execute(
        sa.text(
            "UPDATE marketplace_orders SET status = 'entitlement_revoked' "
            "WHERE payment_status = 'refunded'"
        )
    )
    if connection.dialect.name == "sqlite":
        op.execute("PRAGMA optimize")


def downgrade() -> None:
    connection = op.get_bind()
    subscriptions = list(
        connection.execute(
            sa.text(
                "SELECT id FROM marketplace_subscriptions "
                "WHERE api_key_hash IS NULL OR started_at IS NULL OR expires_at IS NULL"
            )
        ).mappings()
    )
    for row in subscriptions:
        disabled_hash = sha256(
            f"downgrade-disabled:{row['id']}".encode()
        ).hexdigest()
        connection.execute(
            sa.text(
                "UPDATE marketplace_subscriptions "
                "SET status = 'cancelled', "
                "api_key_prefix = COALESCE(api_key_prefix, 'disabled'), "
                "api_key_hash = COALESCE(api_key_hash, :disabled_hash), "
                "started_at = COALESCE(started_at, created_at), "
                "expires_at = COALESCE(expires_at, created_at) "
                "WHERE id = :subscription_id"
            ),
            {
                "disabled_hash": disabled_hash,
                "subscription_id": row["id"],
            },
        )
    connection.execute(
        sa.text(
            "UPDATE marketplace_orders "
            "SET entitlement_started_at = COALESCE(entitlement_started_at, created_at), "
            "entitlement_expires_at = COALESCE(entitlement_expires_at, created_at)"
        )
    )
    with op.batch_alter_table("marketplace_orders") as batch_op:
        batch_op.alter_column(
            "entitlement_expires_at",
            existing_type=sa.DateTime(timezone=True),
            nullable=False,
        )
        batch_op.alter_column(
            "entitlement_started_at",
            existing_type=sa.DateTime(timezone=True),
            nullable=False,
        )
    with op.batch_alter_table("marketplace_subscriptions") as batch_op:
        batch_op.drop_column("credential_claimed_at")
        batch_op.alter_column(
            "expires_at",
            existing_type=sa.DateTime(timezone=True),
            nullable=False,
        )
        batch_op.alter_column(
            "started_at",
            existing_type=sa.DateTime(timezone=True),
            nullable=False,
        )
        batch_op.alter_column(
            "api_key_hash",
            existing_type=sa.String(length=64),
            nullable=False,
        )
        batch_op.alter_column(
            "api_key_prefix",
            existing_type=sa.String(length=24),
            nullable=False,
        )
