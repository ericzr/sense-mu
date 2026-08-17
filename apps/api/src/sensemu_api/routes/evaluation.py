from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Header, status
from sqlalchemy.orm import Session

from sensemu_api import acceptance_service, evaluation_service
from sensemu_api.db.session import get_session
from sensemu_api.dependencies import WorkspaceId
from sensemu_api.evaluation_schemas import (
    AcceptanceRunCreate,
    EvaluationPolicyCreate,
    EvaluationPolicyResponse,
    EvaluationResponse,
    WorkerAcceptanceCompletion,
)
from sensemu_api.storage import Storage, get_storage
from sensemu_api.training_dispatch import TrainingDispatcherDep
from sensemu_api.training_schemas import TrainingRunResponse
from sensemu_api.worker_auth import WorkerAuth

router = APIRouter(prefix="/api/v1", tags=["evaluation"])
SessionDep = Annotated[Session, Depends(get_session)]
StorageDep = Annotated[Storage, Depends(get_storage)]
IdempotencyKey = Annotated[
    str,
    Header(alias="Idempotency-Key", min_length=8, max_length=120),
]


@router.post(
    "/projects/{project_id}/evaluation-policies",
    response_model=EvaluationPolicyResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_evaluation_policy(
    project_id: UUID,
    payload: EvaluationPolicyCreate,
    workspace_id: WorkspaceId,
    session: SessionDep,
) -> EvaluationPolicyResponse:
    policy = evaluation_service.create_policy(
        session, workspace_id, project_id, payload
    )
    return EvaluationPolicyResponse.model_validate(policy)


@router.get(
    "/projects/{project_id}/evaluation-policies",
    response_model=list[EvaluationPolicyResponse],
)
def list_evaluation_policies(
    project_id: UUID,
    workspace_id: WorkspaceId,
    session: SessionDep,
) -> list[EvaluationPolicyResponse]:
    return [
        EvaluationPolicyResponse.model_validate(policy)
        for policy in evaluation_service.list_policies(
            session, workspace_id, project_id
        )
    ]


@router.get(
    "/projects/{project_id}/evaluations",
    response_model=list[EvaluationResponse],
)
def list_evaluations(
    project_id: UUID,
    workspace_id: WorkspaceId,
    session: SessionDep,
) -> list[EvaluationResponse]:
    return evaluation_service.list_evaluations(
        session, workspace_id, project_id
    )


@router.post(
    "/model-versions/{model_version_id}:evaluate",
    response_model=EvaluationResponse,
)
def evaluate_model_version(
    model_version_id: UUID,
    workspace_id: WorkspaceId,
    session: SessionDep,
    storage: StorageDep,
) -> EvaluationResponse:
    evaluation = evaluation_service.evaluate_current_policy(
        session, storage, workspace_id, model_version_id
    )
    return evaluation_service.response_for_evaluation(session, evaluation)


@router.post(
    "/projects/{project_id}/model-versions/{model_version_id}/acceptance-runs",
    response_model=TrainingRunResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_acceptance_run(
    project_id: UUID,
    model_version_id: UUID,
    payload: AcceptanceRunCreate,
    idempotency_key: IdempotencyKey,
    workspace_id: WorkspaceId,
    session: SessionDep,
    storage: StorageDep,
    background_tasks: BackgroundTasks,
    dispatcher: TrainingDispatcherDep,
) -> TrainingRunResponse:
    run, reused = acceptance_service.create_acceptance_run(
        session,
        storage,
        workspace_id,
        project_id,
        model_version_id,
        idempotency_key,
        payload,
    )
    # Dispatch only after the run can be read by a worker or a client refresh.
    session.commit()
    if run.status == "queued":
        background_tasks.add_task(dispatcher.submit_acceptance, workspace_id, run.id)
    return TrainingRunResponse.model_validate(run).model_copy(update={"reused": reused})


@router.get(
    "/projects/{project_id}/acceptance-runs",
    response_model=list[TrainingRunResponse],
)
def list_acceptance_runs(
    project_id: UUID,
    workspace_id: WorkspaceId,
    session: SessionDep,
) -> list[TrainingRunResponse]:
    return [
        TrainingRunResponse.model_validate(run)
        for run in acceptance_service.list_acceptance_runs(
            session, workspace_id, project_id
        )
    ]


@router.post(
    "/internal/acceptance-runs/{run_id}/complete",
    response_model=EvaluationResponse,
    include_in_schema=False,
)
def receive_acceptance_completion(
    run_id: UUID,
    payload: WorkerAcceptanceCompletion,
    workspace_id: WorkspaceId,
    session: SessionDep,
    storage: StorageDep,
    _worker_auth: WorkerAuth,
) -> EvaluationResponse:
    _, evaluation, _ = acceptance_service.complete_acceptance_run(
        session, storage, workspace_id, run_id, payload
    )
    return evaluation_service.response_for_evaluation(session, evaluation)
