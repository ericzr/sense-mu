from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Header, Response, status
from sqlalchemy.orm import Session

from sensemu_api import batch_inference_service
from sensemu_api.batch_inference_schemas import (
    BatchInferenceRunCreate,
    BatchInferenceRunResponse,
    WorkerBatchInferenceCompletion,
)
from sensemu_api.db.session import get_session
from sensemu_api.dependencies import WorkspaceId
from sensemu_api.storage import Storage, get_storage
from sensemu_api.training_dispatch import TrainingDispatcherDep
from sensemu_api.worker_auth import WorkerAuth

router = APIRouter(prefix="/api/v1", tags=["batch-inference"])
SessionDep = Annotated[Session, Depends(get_session)]
StorageDep = Annotated[Storage, Depends(get_storage)]
IdempotencyKey = Annotated[
    str,
    Header(alias="Idempotency-Key", min_length=8, max_length=120),
]


@router.post(
    "/projects/{project_id}/batch-inference-runs",
    response_model=BatchInferenceRunResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_batch_inference_run(
    project_id: UUID,
    payload: BatchInferenceRunCreate,
    idempotency_key: IdempotencyKey,
    workspace_id: WorkspaceId,
    session: SessionDep,
    storage: StorageDep,
    background_tasks: BackgroundTasks,
    dispatcher: TrainingDispatcherDep,
) -> BatchInferenceRunResponse:
    run, reused = batch_inference_service.create_batch_inference_run(
        session,
        storage,
        workspace_id,
        project_id,
        idempotency_key,
        payload,
    )
    if run.status == "queued":
        background_tasks.add_task(dispatcher.submit_batch_inference, workspace_id, run.id)
    return run.model_copy(update={"reused": reused})


@router.get(
    "/projects/{project_id}/batch-inference-runs",
    response_model=list[BatchInferenceRunResponse],
)
def list_batch_inference_runs(
    project_id: UUID,
    workspace_id: WorkspaceId,
    session: SessionDep,
) -> list[BatchInferenceRunResponse]:
    return batch_inference_service.list_batch_inference_runs(
        session, workspace_id, project_id
    )


@router.get(
    "/batch-inference-runs/{run_id}/output",
    response_class=Response,
)
def download_batch_inference_output(
    run_id: UUID,
    workspace_id: WorkspaceId,
    session: SessionDep,
    storage: StorageDep,
) -> Response:
    output = batch_inference_service.get_batch_inference_output(
        session, storage, workspace_id, run_id
    )
    return Response(
        content=output,
        media_type="application/x-ndjson",
        headers={
            "Content-Disposition": f'attachment; filename="batch-inference-{run_id}.ndjson"'
        },
    )


@router.post(
    "/internal/batch-inference-runs/{run_id}/complete",
    response_model=BatchInferenceRunResponse,
    include_in_schema=False,
)
def receive_batch_inference_completion(
    run_id: UUID,
    payload: WorkerBatchInferenceCompletion,
    workspace_id: WorkspaceId,
    session: SessionDep,
    _worker_auth: WorkerAuth,
) -> BatchInferenceRunResponse:
    run, _ = batch_inference_service.complete_batch_inference_run(
        session, workspace_id, run_id, payload
    )
    return run
