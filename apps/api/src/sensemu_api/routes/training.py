from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Response, status
from sqlalchemy.orm import Session

from sensemu_api import training_service
from sensemu_api.config import get_settings
from sensemu_api.db.session import get_session
from sensemu_api.dependencies import WorkspaceId
from sensemu_api.storage import Storage, get_storage
from sensemu_api.training_dispatch import TrainingDispatcherDep
from sensemu_api.training_schemas import (
    ExecutionRecoveryResponse,
    ModelVersionResponse,
    RunEventResponse,
    TrainingClassMetricsResponse,
    TrainingEngineResponse,
    TrainingReportResponse,
    TrainingRunCreate,
    TrainingRunResponse,
    WorkerExecutionClaim,
    WorkerExecutionHeartbeat,
    WorkerExecutionResponse,
    WorkerRunCompletion,
    WorkerRunEventCreate,
)
from sensemu_api.worker_auth import WorkerAuth

router = APIRouter(prefix="/api/v1", tags=["training"])
SessionDep = Annotated[Session, Depends(get_session)]
StorageDep = Annotated[Storage, Depends(get_storage)]
IdempotencyKey = Annotated[
    str,
    Header(alias="Idempotency-Key", min_length=8, max_length=120),
]


@router.get("/training/engines", response_model=list[TrainingEngineResponse])
def list_training_engines() -> list[TrainingEngineResponse]:
    return training_service.training_engines()


@router.post(
    "/projects/{project_id}/training-runs",
    response_model=TrainingRunResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_training_run(
    project_id: UUID,
    payload: TrainingRunCreate,
    idempotency_key: IdempotencyKey,
    workspace_id: WorkspaceId,
    session: SessionDep,
    storage: StorageDep,
    background_tasks: BackgroundTasks,
    dispatcher: TrainingDispatcherDep,
) -> TrainingRunResponse:
    run, reused = training_service.create_training_run(
        session,
        storage,
        workspace_id,
        project_id,
        idempotency_key,
        payload,
    )
    # A worker or an immediate client refresh must never observe a queued run
    # before its row and job specification are durable.
    session.commit()
    if run.status == "queued":
        background_tasks.add_task(dispatcher.submit, workspace_id, run.id)
    return TrainingRunResponse.model_validate(run).model_copy(update={"reused": reused})


@router.get(
    "/projects/{project_id}/training-runs",
    response_model=list[TrainingRunResponse],
)
def list_training_runs(
    project_id: UUID,
    workspace_id: WorkspaceId,
    session: SessionDep,
) -> list[TrainingRunResponse]:
    return [
        TrainingRunResponse.model_validate(run)
        for run in training_service.list_training_runs(session, workspace_id, project_id)
    ]


@router.get("/training-runs/{run_id}", response_model=TrainingRunResponse)
def get_training_run(
    run_id: UUID,
    workspace_id: WorkspaceId,
    session: SessionDep,
) -> TrainingRunResponse:
    return TrainingRunResponse.model_validate(
        training_service.require_run(session, workspace_id, run_id)
    )


@router.get("/training-runs/{run_id}/events", response_model=list[RunEventResponse])
def list_run_events(
    run_id: UUID,
    workspace_id: WorkspaceId,
    session: SessionDep,
) -> list[RunEventResponse]:
    return [
        RunEventResponse.model_validate(event)
        for event in training_service.list_run_events(session, workspace_id, run_id)
    ]


@router.get("/training-runs/{run_id}/report", response_model=TrainingReportResponse)
def get_training_report(
    run_id: UUID,
    workspace_id: WorkspaceId,
    session: SessionDep,
    storage: StorageDep,
) -> TrainingReportResponse:
    return training_service.get_training_report(session, storage, workspace_id, run_id)


@router.get(
    "/training-runs/{run_id}/class-metrics",
    response_model=TrainingClassMetricsResponse,
)
def get_training_class_metrics(
    run_id: UUID,
    workspace_id: WorkspaceId,
    session: SessionDep,
    storage: StorageDep,
) -> TrainingClassMetricsResponse:
    return training_service.get_training_class_metrics(session, storage, workspace_id, run_id)


@router.get("/training-runs/{run_id}/visualizations/{visualization}")
def get_training_visualization(
    run_id: UUID,
    visualization: str,
    workspace_id: WorkspaceId,
    session: SessionDep,
    storage: StorageDep,
) -> Response:
    payload = training_service.get_training_visualization(
        session,
        storage,
        workspace_id,
        run_id,
        visualization,
    )
    return Response(
        content=payload,
        media_type="image/png",
        headers={"Cache-Control": "private, max-age=300"},
    )


@router.post(
    "/training-runs/{run_id}:cancel",
    response_model=TrainingRunResponse,
)
def cancel_training_run(
    run_id: UUID,
    workspace_id: WorkspaceId,
    session: SessionDep,
) -> TrainingRunResponse:
    run = training_service.cancel_training_run(session, workspace_id, run_id)
    return TrainingRunResponse.model_validate(run)


@router.post(
    "/training-runs/{run_id}:dispatch",
    response_model=TrainingRunResponse,
)
def dispatch_training_run(
    run_id: UUID,
    workspace_id: WorkspaceId,
    session: SessionDep,
    background_tasks: BackgroundTasks,
    dispatcher: TrainingDispatcherDep,
) -> TrainingRunResponse:
    run = training_service.require_run(session, workspace_id, run_id)
    if run.status != "queued":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"只能重新入队 queued 状态的任务，当前为 {run.status}",
        )
    background_tasks.add_task(dispatcher.submit, workspace_id, run.id)
    return TrainingRunResponse.model_validate(run)


@router.get(
    "/projects/{project_id}/model-versions",
    response_model=list[ModelVersionResponse],
)
def list_model_versions(
    project_id: UUID,
    workspace_id: WorkspaceId,
    session: SessionDep,
) -> list[ModelVersionResponse]:
    return training_service.list_model_versions(session, workspace_id, project_id)


@router.post(
    "/internal/training-runs/{run_id}/execution:claim",
    response_model=WorkerExecutionResponse,
    include_in_schema=False,
)
def get_worker_execution(
    run_id: UUID,
    payload: WorkerExecutionClaim,
    workspace_id: WorkspaceId,
    session: SessionDep,
    storage: StorageDep,
    _worker_auth: WorkerAuth,
) -> WorkerExecutionResponse:
    run, job_spec = training_service.claim_worker_execution(
        session,
        storage,
        workspace_id,
        run_id,
        payload,
    )
    return WorkerExecutionResponse(
        run_id=run.id,
        attempt_id=payload.attempt_id,
        status=run.status,
        job_spec=job_spec,
    )


@router.post(
    "/internal/training-runs/{run_id}/execution:heartbeat",
    response_model=TrainingRunResponse,
    include_in_schema=False,
)
def heartbeat_worker_execution(
    run_id: UUID,
    payload: WorkerExecutionHeartbeat,
    workspace_id: WorkspaceId,
    session: SessionDep,
    _worker_auth: WorkerAuth,
) -> TrainingRunResponse:
    return TrainingRunResponse.model_validate(
        training_service.heartbeat_worker_execution(
            session,
            workspace_id,
            run_id,
            payload,
        )
    )


@router.post(
    "/internal/training-runs/executions:recover-stale",
    response_model=ExecutionRecoveryResponse,
    include_in_schema=False,
)
def recover_stale_worker_executions(
    session: SessionDep,
    background_tasks: BackgroundTasks,
    dispatcher: TrainingDispatcherDep,
    _worker_auth: WorkerAuth,
) -> ExecutionRecoveryResponse:
    settings = get_settings()
    recovered = training_service.recover_stale_executions(
        session,
        lease_timeout_seconds=settings.training_execution_lease_timeout_seconds,
        max_attempts=settings.training_execution_max_attempts,
    )
    for item in recovered:
        if item["action"] == "requeued":
            background_tasks.add_task(
                (
                    dispatcher.submit_acceptance
                    if item.get("run_type") == "model.acceptance-evaluate"
                    else dispatcher.submit_batch_inference
                    if item.get("run_type") == "inference.batch"
                    else dispatcher.submit
                ),
                item["workspace_id"],
                item["run_id"],
            )
    return ExecutionRecoveryResponse.model_validate({"recovered": recovered})


@router.post(
    "/internal/training-runs/{run_id}/events",
    response_model=TrainingRunResponse,
    include_in_schema=False,
)
def receive_worker_event(
    run_id: UUID,
    payload: WorkerRunEventCreate,
    workspace_id: WorkspaceId,
    session: SessionDep,
    _worker_auth: WorkerAuth,
) -> TrainingRunResponse:
    run, _ = training_service.apply_worker_event(
        session,
        workspace_id,
        run_id,
        payload,
    )
    return TrainingRunResponse.model_validate(run)


@router.post(
    "/internal/training-runs/{run_id}/complete",
    response_model=ModelVersionResponse,
    include_in_schema=False,
)
def receive_worker_completion(
    run_id: UUID,
    payload: WorkerRunCompletion,
    workspace_id: WorkspaceId,
    session: SessionDep,
    storage: StorageDep,
    _worker_auth: WorkerAuth,
) -> ModelVersionResponse:
    _, version, _ = training_service.complete_training_run(
        session,
        storage,
        workspace_id,
        run_id,
        payload,
    )
    return ModelVersionResponse(
        id=version.id,
        model_id=version.model_id,
        model_name=payload.model_name,
        run_id=version.run_id,
        version_number=version.version_number,
        status=version.status,
        artifact_uri=version.artifact_uri,
        metrics=version.metrics,
        created_at=version.created_at,
    )
