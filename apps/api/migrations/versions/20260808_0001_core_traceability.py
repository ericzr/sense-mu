"""Create the core traceability chain.

Revision ID: 20260808_0001
Revises:
Create Date: 2026-08-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260808_0001"
down_revision: str | None = None
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
        "workspaces",
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        *timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_workspaces"),
        sa.UniqueConstraint("slug", name="uq_workspaces_slug"),
    )

    op.create_table(
        "projects",
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("task_type", sa.String(length=40), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        *timestamps(),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name="fk_projects_workspace_id_workspaces",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_projects"),
        sa.UniqueConstraint("workspace_id", "slug", name="uq_projects_workspace_id"),
    )
    op.create_index("ix_projects_workspace_id", "projects", ["workspace_id"])

    op.create_table(
        "assets",
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("uri", sa.Text(), nullable=False),
        sa.Column("media_type", sa.String(length=100), nullable=False),
        sa.Column("checksum_sha256", sa.String(length=64), nullable=False),
        sa.Column("byte_size", sa.BigInteger(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        *timestamps(),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name="fk_assets_workspace_id_workspaces",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_assets"),
        sa.UniqueConstraint(
            "workspace_id",
            "checksum_sha256",
            name="uq_assets_workspace_id",
        ),
    )
    op.create_index(
        "ix_assets_workspace_media_type",
        "assets",
        ["workspace_id", "media_type"],
    )

    op.create_table(
        "datasets",
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        *timestamps(),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name="fk_datasets_project_id_projects",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_datasets"),
        sa.UniqueConstraint("project_id", "name", name="uq_datasets_project_id"),
    )
    op.create_index("ix_datasets_project_id", "datasets", ["project_id"])

    op.create_table(
        "dataset_versions",
        sa.Column("dataset_id", sa.Uuid(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("manifest_uri", sa.Text(), nullable=False),
        sa.Column("asset_count", sa.Integer(), nullable=False),
        sa.Column("class_map", sa.JSON(), nullable=False),
        sa.Column("frozen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        *timestamps(),
        sa.ForeignKeyConstraint(
            ["dataset_id"],
            ["datasets.id"],
            name="fk_dataset_versions_dataset_id_datasets",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_dataset_versions"),
        sa.UniqueConstraint(
            "dataset_id",
            "version_number",
            name="uq_dataset_versions_dataset_id",
        ),
    )
    op.create_index(
        "ix_dataset_versions_dataset_id",
        "dataset_versions",
        ["dataset_id"],
    )

    op.create_table(
        "runs",
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("dataset_version_id", sa.Uuid(), nullable=False),
        sa.Column("run_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("executor", sa.String(length=80), nullable=False),
        sa.Column("recipe", sa.JSON(), nullable=False),
        sa.Column("progress", sa.Integer(), nullable=False),
        sa.Column("artifact_prefix", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        *timestamps(),
        sa.ForeignKeyConstraint(
            ["dataset_version_id"],
            ["dataset_versions.id"],
            name="fk_runs_dataset_version_id_dataset_versions",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name="fk_runs_project_id_projects",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_runs"),
    )
    op.create_index(
        "ix_runs_project_status_created_at",
        "runs",
        ["project_id", "status", "created_at"],
    )

    op.create_table(
        "models",
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("task_type", sa.String(length=40), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        *timestamps(),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name="fk_models_project_id_projects",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_models"),
        sa.UniqueConstraint("project_id", "name", name="uq_models_project_id"),
    )
    op.create_index("ix_models_project_id", "models", ["project_id"])

    op.create_table(
        "model_versions",
        sa.Column("model_id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("artifact_uri", sa.Text(), nullable=False),
        sa.Column("metrics", sa.JSON(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        *timestamps(),
        sa.ForeignKeyConstraint(
            ["model_id"],
            ["models.id"],
            name="fk_model_versions_model_id_models",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["runs.id"],
            name="fk_model_versions_run_id_runs",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_model_versions"),
        sa.UniqueConstraint(
            "model_id",
            "version_number",
            name="uq_model_versions_model_id",
        ),
        sa.UniqueConstraint("run_id", name="uq_model_versions_run_id"),
    )
    op.create_index("ix_model_versions_model_id", "model_versions", ["model_id"])

    op.create_table(
        "deployments",
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("model_version_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("endpoint_slug", sa.String(length=120), nullable=False),
        sa.Column("environment", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        *timestamps(),
        sa.ForeignKeyConstraint(
            ["model_version_id"],
            ["model_versions.id"],
            name="fk_deployments_model_version_id_model_versions",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name="fk_deployments_workspace_id_workspaces",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_deployments"),
        sa.UniqueConstraint(
            "workspace_id",
            "endpoint_slug",
            name="uq_deployments_workspace_id",
        ),
    )
    op.create_index(
        "ix_deployments_workspace_status",
        "deployments",
        ["workspace_id", "status"],
    )

    op.create_table(
        "usage_records",
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("deployment_id", sa.Uuid(), nullable=True),
        sa.Column("request_id", sa.String(length=100), nullable=False),
        sa.Column("capability_id", sa.String(length=64), nullable=False),
        sa.Column("billable_units", sa.Numeric(precision=20, scale=6), nullable=False),
        sa.Column("unit", sa.String(length=32), nullable=False),
        sa.Column("dimensions", sa.JSON(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["deployment_id"],
            ["deployments.id"],
            name="fk_usage_records_deployment_id_deployments",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name="fk_usage_records_workspace_id_workspaces",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_usage_records"),
        sa.UniqueConstraint("request_id", name="uq_usage_records_request_id"),
    )
    op.create_index(
        "ix_usage_records_workspace_occurred_at",
        "usage_records",
        ["workspace_id", "occurred_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_usage_records_workspace_occurred_at", table_name="usage_records")
    op.drop_table("usage_records")
    op.drop_index("ix_deployments_workspace_status", table_name="deployments")
    op.drop_table("deployments")
    op.drop_index("ix_model_versions_model_id", table_name="model_versions")
    op.drop_table("model_versions")
    op.drop_index("ix_models_project_id", table_name="models")
    op.drop_table("models")
    op.drop_index("ix_runs_project_status_created_at", table_name="runs")
    op.drop_table("runs")
    op.drop_index("ix_dataset_versions_dataset_id", table_name="dataset_versions")
    op.drop_table("dataset_versions")
    op.drop_index("ix_datasets_project_id", table_name="datasets")
    op.drop_table("datasets")
    op.drop_index("ix_assets_workspace_media_type", table_name="assets")
    op.drop_table("assets")
    op.drop_index("ix_projects_workspace_id", table_name="projects")
    op.drop_table("projects")
    op.drop_table("workspaces")

