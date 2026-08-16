from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from sensemu_api.db.models import (
    Asset,
    Dataset,
    DatasetItem,
    DatasetVersion,
    Deployment,
    Evaluation,
    EvaluationPolicy,
    Model,
    ModelVersion,
    Project,
    Run,
    UsageRecord,
)
from sensemu_api.db.session import get_session
from sensemu_api.dependencies import WorkspaceId
from sensemu_api.schemas import (
    ActiveRunSummary,
    MetricSummary,
    OverviewResponse,
    WorkspaceDatasetSummary,
    WorkspaceProjectSummary,
)

router = APIRouter(prefix="/api/v1", tags=["overview"])
SessionDep = Annotated[Session, Depends(get_session)]
ACTIVE_RUN_STATUSES = {"queued", "preparing", "running", "cancel_requested"}


def _run_summary(
    run: Run,
    project: Project,
    dataset_version: DatasetVersion,
) -> ActiveRunSummary:
    return ActiveRunSummary(
        run_id=str(run.id),
        project_name=project.name,
        dataset_version_number=dataset_version.version_number,
        status=run.status,
        progress=run.progress,
        engine=run.engine,
        model=str(run.recipe.get("model", run.engine)),
        executor=run.executor,
        created_at=run.created_at,
        error_message=run.error_message,
    )


@router.get("/overview", response_model=OverviewResponse)
def overview(workspace_id: WorkspaceId, session: SessionDep) -> OverviewResponse:
    """Return a workspace-scoped snapshot derived only from persisted state."""
    dataset_count = session.scalar(
        select(func.count(Dataset.id))
        .join(Project, Project.id == Dataset.project_id)
        .where(Project.workspace_id == workspace_id)
    ) or 0
    asset_count = session.scalar(
        select(func.count(Asset.id)).where(Asset.workspace_id == workspace_id)
    ) or 0
    active_run_count = session.scalar(
        select(func.count(Run.id))
        .join(Project, Project.id == Run.project_id)
        .where(
            Project.workspace_id == workspace_id,
            Run.run_type == "model.train",
            Run.status.in_(ACTIVE_RUN_STATUSES),
        )
    ) or 0
    model_version_count = session.scalar(
        select(func.count(func.distinct(ModelVersion.id)))
        .join(Model, Model.id == ModelVersion.model_id)
        .join(Project, Project.id == Model.project_id)
        .join(Evaluation, Evaluation.model_version_id == ModelVersion.id)
        .join(EvaluationPolicy, EvaluationPolicy.id == Evaluation.policy_id)
        .where(
            Project.workspace_id == workspace_id,
            Evaluation.source == "acceptance-dataset",
            Evaluation.verdict == "approved",
            EvaluationPolicy.is_active.is_(True),
        )
    ) or 0
    now = datetime.now(UTC)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    inference_call_count = session.scalar(
        select(func.count(UsageRecord.id)).where(
            UsageRecord.workspace_id == workspace_id,
            UsageRecord.occurred_at >= month_start,
        )
    ) or 0

    version_counts = (
        select(
            Dataset.project_id.label("project_id"),
            func.count(DatasetVersion.id).label("dataset_version_count"),
        )
        .outerjoin(DatasetVersion, DatasetVersion.dataset_id == Dataset.id)
        .group_by(Dataset.project_id)
        .subquery()
    )
    active_run_counts = (
        select(
            Run.project_id.label("project_id"),
            func.count(Run.id).label("active_run_count"),
        )
        .where(
            Run.run_type == "model.train",
            Run.status.in_(ACTIVE_RUN_STATUSES),
        )
        .group_by(Run.project_id)
        .subquery()
    )
    published_service_counts = (
        select(
            Model.project_id.label("project_id"),
            func.count(Deployment.id).label("published_service_count"),
        )
        .join(ModelVersion, ModelVersion.model_id == Model.id)
        .join(Deployment, Deployment.model_version_id == ModelVersion.id)
        .where(Deployment.status == "published")
        .group_by(Model.project_id)
        .subquery()
    )
    project_rows = session.execute(
        select(
            Project,
            func.coalesce(version_counts.c.dataset_version_count, 0),
            func.coalesce(active_run_counts.c.active_run_count, 0),
            func.coalesce(published_service_counts.c.published_service_count, 0),
        )
        .outerjoin(version_counts, version_counts.c.project_id == Project.id)
        .outerjoin(active_run_counts, active_run_counts.c.project_id == Project.id)
        .outerjoin(
            published_service_counts,
            published_service_counts.c.project_id == Project.id,
        )
        .where(Project.workspace_id == workspace_id, Project.archived_at.is_(None))
        .order_by(Project.created_at.desc())
    ).all()
    projects = [
        WorkspaceProjectSummary(
            id=project.id,
            name=project.name,
            task_type=project.task_type,
            description=project.description,
            status=project.status,
            dataset_version_count=int(dataset_version_count or 0),
            active_run_count=int(active_run_count or 0),
            published_service_count=int(published_service_count or 0),
            created_at=project.created_at,
        )
        for project, dataset_version_count, active_run_count, published_service_count in project_rows
    ]

    dataset_rows = session.execute(
        select(
            Dataset,
            Project,
            func.count(func.distinct(DatasetItem.asset_id)).label("asset_count"),
            func.count(func.distinct(DatasetVersion.id)).label("version_count"),
        )
        .join(Project, Project.id == Dataset.project_id)
        .outerjoin(
            DatasetItem,
            (DatasetItem.dataset_id == Dataset.id)
            & (DatasetItem.item_role == "training_asset"),
        )
        .outerjoin(DatasetVersion, DatasetVersion.dataset_id == Dataset.id)
        .where(Project.workspace_id == workspace_id, Project.archived_at.is_(None))
        .group_by(Dataset.id, Project.id)
        .order_by(Dataset.created_at.desc())
    ).all()
    datasets = [
        WorkspaceDatasetSummary(
            id=dataset.id,
            project_id=project.id,
            project_name=project.name,
            name=dataset.name,
            description=dataset.description,
            asset_count=int(asset_count or 0),
            version_count=int(version_count or 0),
            created_at=dataset.created_at,
        )
        for dataset, project, asset_count, version_count in dataset_rows
    ]

    recent_rows = session.execute(
        select(Run, Project, DatasetVersion)
        .join(Project, Project.id == Run.project_id)
        .join(DatasetVersion, DatasetVersion.id == Run.dataset_version_id)
        .where(Project.workspace_id == workspace_id, Run.run_type == "model.train")
        .order_by(Run.created_at.desc())
        .limit(8)
    ).all()
    recent_runs = [
        _run_summary(run, project, dataset_version)
        for run, project, dataset_version in recent_rows
    ]
    active_rows = session.execute(
        select(Run, Project, DatasetVersion)
        .join(Project, Project.id == Run.project_id)
        .join(DatasetVersion, DatasetVersion.id == Run.dataset_version_id)
        .where(
            Project.workspace_id == workspace_id,
            Run.run_type == "model.train",
            Run.status.in_(ACTIVE_RUN_STATUSES),
        )
        .order_by(Run.created_at.desc())
        .limit(8)
    ).all()
    active_runs = [
        _run_summary(run, project, dataset_version)
        for run, project, dataset_version in active_rows
    ]

    return OverviewResponse(
        workspace_id=workspace_id,
        metrics=MetricSummary(
            datasets=dataset_count,
            assets=asset_count,
            training_jobs_running=active_run_count,
            model_versions_ready=model_version_count,
            inference_calls_month=inference_call_count,
        ),
        projects=projects,
        datasets=datasets,
        active_runs=active_runs,
        recent_runs=recent_runs,
    )
