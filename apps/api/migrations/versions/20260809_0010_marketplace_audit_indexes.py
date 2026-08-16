"""add marketplace reservation recovery and usage audit indexes

Revision ID: 20260809_0010
Revises: 20260809_0009
Create Date: 2026-08-09
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260809_0010"
down_revision: str | None = "20260809_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_usage_reservations_status_created_at",
        "usage_reservations",
        ["status", "created_at"],
    )
    op.create_index(
        "ix_usage_records_subscription_occurred_at",
        "usage_records",
        ["subscription_id", "occurred_at"],
    )
    if op.get_bind().dialect.name == "sqlite":
        op.execute("PRAGMA optimize")


def downgrade() -> None:
    op.drop_index(
        "ix_usage_records_subscription_occurred_at", table_name="usage_records"
    )
    op.drop_index(
        "ix_usage_reservations_status_created_at", table_name="usage_reservations"
    )
