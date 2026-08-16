"""Add mutable dataset membership before version freezing.

Revision ID: 20260808_0002
Revises: 20260808_0001
Create Date: 2026-08-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260808_0002"
down_revision: str | None = "20260808_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "dataset_items",
        sa.Column("dataset_id", sa.Uuid(), nullable=False),
        sa.Column("asset_id", sa.Uuid(), nullable=False),
        sa.Column("split", sa.String(length=16), nullable=True),
        sa.Column("annotation_uri", sa.Text(), nullable=True),
        sa.Column(
            "added_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["asset_id"],
            ["assets.id"],
            name="fk_dataset_items_asset_id_assets",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["dataset_id"],
            ["datasets.id"],
            name="fk_dataset_items_dataset_id_datasets",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_dataset_items"),
        sa.UniqueConstraint("dataset_id", "asset_id", name="uq_dataset_items_dataset_id"),
    )
    op.create_index(
        "ix_dataset_items_dataset_split",
        "dataset_items",
        ["dataset_id", "split"],
    )


def downgrade() -> None:
    op.drop_index("ix_dataset_items_dataset_split", table_name="dataset_items")
    op.drop_table("dataset_items")

