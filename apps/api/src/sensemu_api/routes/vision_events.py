from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from sqlalchemy.orm import Session

from sensemu_api import vision_event_service
from sensemu_api.db.session import get_session
from sensemu_api.dependencies import WorkspaceId
from sensemu_api.gateway_auth import GatewayAuth
from sensemu_api.vision_event_schemas import (
    VisionEventCreate,
    VisionEventListItem,
    VisionEventReplayResponse,
    VisionEventResponse,
    WebhookDeliveryClaimResponse,
    WebhookDeliveryComplete,
    WebhookDeliveryRecoveryResponse,
    WebhookDeliveryResponse,
)
from sensemu_api.webhook_dispatch import WebhookDispatcherDep
from sensemu_api.worker_auth import WorkerAuth

router = APIRouter(prefix="/api/v1", tags=["vision-events"])
SessionDep = Annotated[Session, Depends(get_session)]
EventLimit = Annotated[int, Query(ge=1, le=100)]


@router.get(
    "/projects/{project_id}/vision-events",
    response_model=list[VisionEventListItem],
)
def list_vision_events(
    project_id: UUID,
    workspace_id: WorkspaceId,
    session: SessionDep,
    limit: EventLimit = 50,
) -> list[VisionEventListItem]:
    return vision_event_service.list_events(
        session,
        workspace_id,
        project_id,
        limit=limit,
    )


@router.get(
    "/projects/{project_id}/vision-events/{event_id}/replay",
    response_model=VisionEventReplayResponse,
)
def replay_vision_event(
    project_id: UUID,
    event_id: UUID,
    workspace_id: WorkspaceId,
    session: SessionDep,
) -> VisionEventReplayResponse:
    return vision_event_service.replay_event(
        session,
        workspace_id,
        project_id,
        event_id,
    )


@router.post(
    "/internal/workflow-specs/{workflow_id}/vision-events",
    response_model=VisionEventResponse,
)
def emit_vision_event(
    workflow_id: UUID,
    payload: VisionEventCreate,
    background_tasks: BackgroundTasks,
    session: SessionDep,
    dispatcher: WebhookDispatcherDep,
    _gateway_auth: GatewayAuth,
) -> VisionEventResponse:
    event = vision_event_service.emit(session, workflow_id, payload)
    if not event.reused and event.delivery_status == "pending":
        background_tasks.add_task(dispatcher.submit, event.delivery_id)
    return event


@router.post(
    "/internal/webhook-deliveries/{delivery_id}:claim",
    response_model=WebhookDeliveryClaimResponse,
)
def claim_webhook_delivery(
    delivery_id: UUID,
    session: SessionDep,
    _worker_auth: WorkerAuth,
) -> WebhookDeliveryClaimResponse:
    return vision_event_service.claim_delivery(session, delivery_id)


@router.post(
    "/internal/webhook-deliveries/{delivery_id}:complete",
    response_model=WebhookDeliveryResponse,
)
def complete_webhook_delivery(
    delivery_id: UUID,
    payload: WebhookDeliveryComplete,
    session: SessionDep,
    _worker_auth: WorkerAuth,
) -> WebhookDeliveryResponse:
    return vision_event_service.complete_delivery(session, delivery_id, payload)


@router.post(
    "/internal/webhook-deliveries:recover",
    response_model=WebhookDeliveryRecoveryResponse,
)
def recover_webhook_deliveries(
    background_tasks: BackgroundTasks,
    session: SessionDep,
    dispatcher: WebhookDispatcherDep,
    _worker_auth: WorkerAuth,
) -> WebhookDeliveryRecoveryResponse:
    recovered = vision_event_service.recover_deliveries(session)
    for delivery_id in recovered.queued_delivery_ids:
        background_tasks.add_task(dispatcher.submit, delivery_id)
    return recovered
