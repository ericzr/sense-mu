"""add trusted data marketplace cards

Revision ID: 20260809_0017
Revises: 20260809_0016
Create Date: 2026-08-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260809_0017"
down_revision: str | None = "20260809_0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "data_marketplace_listings",
        sa.Column("provider_workspace_id", sa.Uuid(), nullable=False),
        sa.Column("dataset_version_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=180), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("source_summary", sa.Text(), nullable=False),
        sa.Column("collection_method", sa.Text(), nullable=False),
        sa.Column("coverage_summary", sa.Text(), nullable=False),
        sa.Column("known_limitations", sa.Text(), nullable=False),
        sa.Column("license_code", sa.String(length=64), nullable=False),
        sa.Column("custom_license_terms", sa.Text(), nullable=True),
        sa.Column("allow_commercial_use", sa.Boolean(), nullable=False),
        sa.Column("allow_model_training", sa.Boolean(), nullable=False),
        sa.Column("allow_derivative_models", sa.Boolean(), nullable=False),
        sa.Column("allow_redistribution", sa.Boolean(), nullable=False),
        sa.Column("contains_personal_data", sa.Boolean(), nullable=False),
        sa.Column("privacy_treatment", sa.Text(), nullable=False),
        sa.Column("rights_confirmed", sa.Boolean(), nullable=False),
        sa.Column("review_basis", sa.String(length=48), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
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
            ["dataset_version_id"], ["dataset_versions.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["provider_workspace_id"], ["workspaces.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("dataset_version_id"),
    )
    op.create_index(
        "ix_data_marketplace_listings_provider_workspace_id",
        "data_marketplace_listings",
        ["provider_workspace_id"],
    )
    op.create_index(
        "ix_data_marketplace_listings_status_published_at",
        "data_marketplace_listings",
        ["status", "published_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_data_marketplace_listings_status_published_at",
        table_name="data_marketplace_listings",
    )
    op.drop_index(
        "ix_data_marketplace_listings_provider_workspace_id",
        table_name="data_marketplace_listings",
    )
    op.drop_table("data_marketplace_listings")
