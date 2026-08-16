"""bind marketplace listings to capability specs

Revision ID: 20260810_0025
Revises: 20260810_0024
Create Date: 2026-08-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260810_0025"
down_revision: str | None = "20260810_0024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("marketplace_listings") as batch_op:
        batch_op.add_column(sa.Column("capability_spec_id", sa.Uuid(), nullable=True))
        batch_op.create_foreign_key(
            "fk_marketplace_listings_capability_spec_id_capability_specs",
            "capability_specs",
            ["capability_spec_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch_op.create_unique_constraint(
            "uq_marketplace_listings_capability_spec_id",
            ["capability_spec_id"],
        )
    op.execute(
        "UPDATE marketplace_listings SET capability_spec_id = ("
        "SELECT capability_specs.id FROM capability_specs "
        "WHERE capability_specs.deployment_id = marketplace_listings.deployment_id"
        ") WHERE EXISTS ("
        "SELECT 1 FROM capability_specs "
        "WHERE capability_specs.deployment_id = marketplace_listings.deployment_id"
        ")"
    )
    op.execute(
        "UPDATE marketplace_listings SET status = 'legacy_unbound', published_at = NULL "
        "WHERE capability_spec_id IS NULL"
    )
    if op.get_bind().dialect.name == "sqlite":
        op.execute("PRAGMA optimize")


def downgrade() -> None:
    with op.batch_alter_table("marketplace_listings") as batch_op:
        batch_op.drop_constraint(
            "uq_marketplace_listings_capability_spec_id",
            type_="unique",
        )
        batch_op.drop_constraint(
            "fk_marketplace_listings_capability_spec_id_capability_specs",
            type_="foreignkey",
        )
        batch_op.drop_column("capability_spec_id")
