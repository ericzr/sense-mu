"""require platform review before marketplace publication

Revision ID: 20260810_0021
Revises: 20260809_0020
Create Date: 2026-08-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260810_0021"
down_revision: str | None = "20260809_0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("marketplace_listings") as batch_op:
        batch_op.alter_column(
            "published_at",
            existing_type=sa.DateTime(timezone=True),
            nullable=True,
        )
    op.create_table(
        "marketplace_listing_reviews",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("listing_id", sa.Uuid(), nullable=False),
        sa.Column("decision", sa.String(length=32), nullable=False),
        sa.Column("reviewer_identity", sa.String(length=160), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["listing_id"],
            ["marketplace_listings.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_marketplace_listing_reviews_listing_reviewed_at",
        "marketplace_listing_reviews",
        ["listing_id", "reviewed_at"],
    )
    op.execute(
        "UPDATE marketplace_listings SET status = 'pending_review', published_at = NULL "
        "WHERE status = 'published'"
    )
    if op.get_bind().dialect.name == "sqlite":
        op.execute("PRAGMA optimize")


def downgrade() -> None:
    op.execute(
        "UPDATE marketplace_listings SET published_at = created_at "
        "WHERE published_at IS NULL"
    )
    op.execute(
        "UPDATE marketplace_listings SET status = 'published' "
        "WHERE status IN ('pending_review', 'rejected')"
    )
    op.drop_index(
        "ix_marketplace_listing_reviews_listing_reviewed_at",
        table_name="marketplace_listing_reviews",
    )
    op.drop_table("marketplace_listing_reviews")
    with op.batch_alter_table("marketplace_listings") as batch_op:
        batch_op.alter_column(
            "published_at",
            existing_type=sa.DateTime(timezone=True),
            nullable=False,
        )
