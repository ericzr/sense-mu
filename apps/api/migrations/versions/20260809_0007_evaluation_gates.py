"""add immutable evaluation policies and reports

Revision ID: 20260809_0007
Revises: 20260809_0006
Create Date: 2026-08-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260809_0007"
down_revision: str | None = "20260809_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def timestamps() -> list[sa.Column]:
    return [
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
    ]


def upgrade() -> None:
    op.create_table(
        "evaluation_policies",
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("rules", sa.JSON(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        *timestamps(),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name="fk_evaluation_policies_project_id_projects",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_evaluation_policies"),
        sa.UniqueConstraint(
            "project_id",
            "version_number",
            name="uq_evaluation_policies_project_id",
        ),
    )
    op.create_index(
        "ix_evaluation_policies_project_active",
        "evaluation_policies",
        ["project_id", "is_active"],
    )

    op.create_table(
        "evaluations",
        sa.Column("model_version_id", sa.Uuid(), nullable=False),
        sa.Column("dataset_version_id", sa.Uuid(), nullable=False),
        sa.Column("policy_id", sa.Uuid(), nullable=False),
        sa.Column("source", sa.String(length=48), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("verdict", sa.String(length=32), nullable=False),
        sa.Column("metrics", sa.JSON(), nullable=False),
        sa.Column("rule_results", sa.JSON(), nullable=False),
        sa.Column("report_uri", sa.Text(), nullable=False),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        *timestamps(),
        sa.ForeignKeyConstraint(
            ["dataset_version_id"],
            ["dataset_versions.id"],
            name="fk_evaluations_dataset_version_id_dataset_versions",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["model_version_id"],
            ["model_versions.id"],
            name="fk_evaluations_model_version_id_model_versions",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["policy_id"],
            ["evaluation_policies.id"],
            name="fk_evaluations_policy_id_evaluation_policies",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_evaluations"),
        sa.UniqueConstraint(
            "model_version_id",
            "policy_id",
            name="uq_evaluations_model_version_id",
        ),
    )
    op.create_index(
        "ix_evaluations_model_evaluated_at",
        "evaluations",
        ["model_version_id", "evaluated_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_evaluations_model_evaluated_at", table_name="evaluations")
    op.drop_table("evaluations")
    op.drop_index(
        "ix_evaluation_policies_project_active",
        table_name="evaluation_policies",
    )
    op.drop_table("evaluation_policies")
