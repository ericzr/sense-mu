import json
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from hmac import new as hmac_new
from urllib.parse import urlparse
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from sensemu_api.catalog_service import require_project
from sensemu_api.config import get_settings
from sensemu_api.db.models import (
    CapabilitySpec,
    Deployment,
    Model,
    ModelVersion,
    Project,
    VisionEvent,
    WebhookDelivery,
    WorkflowSpec,
)
from sensemu_api.vision_event_schemas import (
    VisionEventCreate,
    VisionEventListItem,
    VisionEventReplayDecision,
    VisionEventReplayDelivery,
    VisionEventReplayResponse,
    VisionEventReplaySample,
    VisionEventResponse,
    WebhookDeliveryClaimResponse,
    WebhookDeliveryComplete,
    WebhookDeliveryRecoveryResponse,
    WebhookDeliveryResponse,
)

MAX_WEBHOOK_ATTEMPTS = 8
DELIVERY_LEASE_SECONDS = 120
PPE_VIOLATION_WEBHOOK_TEMPLATE = "ppe-violation-webhook.v1"
PPE_EVENT_REQUIREMENTS = {
    "missing_hardhat": "hardhat",
    "missing_safety_vest": "safety_vest",
}


def _as_utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def _response(event: VisionEvent, delivery: WebhookDelivery, *, reused: bool) -> VisionEventResponse:
    return VisionEventResponse(
        id=event.id,
        workspace_id=event.workspace_id,
        project_id=event.project_id,
        workflow_spec_id=event.workflow_spec_id,
        capability_spec_id=event.capability_spec_id,
        request_id=event.request_id,
        deduplication_key=event.deduplication_key,
        event_type=event.event_type,
        payload=event.payload,
        occurred_at=_as_utc(event.occurred_at),
        delivery_id=delivery.id,
        delivery_status=delivery.status,
        reused=reused,
    )


def _workflow_record(
    session: Session,
    workflow_id: UUID,
) -> tuple[WorkflowSpec, CapabilitySpec, Project]:
    record = session.execute(
        select(WorkflowSpec, CapabilitySpec, Project)
        .join(CapabilitySpec, CapabilitySpec.id == WorkflowSpec.capability_spec_id)
        .join(Deployment, Deployment.id == CapabilitySpec.deployment_id)
        .join(ModelVersion, ModelVersion.id == Deployment.model_version_id)
        .join(Model, Model.id == ModelVersion.model_id)
        .join(Project, Project.id == Model.project_id)
        .where(WorkflowSpec.id == workflow_id)
        .with_for_update()
    ).one_or_none()
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="未找到工作流契约")
    return record


def emit(
    session: Session,
    workflow_id: UUID,
    payload: VisionEventCreate,
) -> VisionEventResponse:
    workflow, capability, project = _workflow_record(session, workflow_id)
    if workflow.status != "published" or capability.status != "published":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="工作流或能力契约未发布")
    if payload.event_type not in workflow.event_types:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="事件不在工作流输出范围内")
    existing = session.scalar(
        select(VisionEvent)
        .where(
            VisionEvent.workflow_spec_id == workflow.id,
            VisionEvent.idempotency_key == payload.idempotency_key,
        )
        .with_for_update()
    )
    if existing is not None:
        delivery = session.scalar(
            select(WebhookDelivery).where(WebhookDelivery.vision_event_id == existing.id)
        )
        if delivery is None:
            raise RuntimeError("视觉事件缺少 Webhook 投递记录")
        if (
            existing.request_id != payload.request_id
            or existing.event_type != payload.event_type
            or existing.deduplication_key != payload.deduplication_key
            or existing.payload != payload.payload
            or _as_utc(existing.occurred_at) != _as_utc(payload.occurred_at)
        ):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="事件幂等键冲突")
        return _response(existing, delivery, reused=True)
    window_start = _as_utc(payload.occurred_at) - timedelta(
        seconds=workflow.deduplication_window_seconds
    )
    deduplicated = session.scalar(
        select(VisionEvent)
        .where(
            VisionEvent.workflow_spec_id == workflow.id,
            VisionEvent.event_type == payload.event_type,
            VisionEvent.deduplication_key == payload.deduplication_key,
            VisionEvent.occurred_at >= window_start,
        )
        .order_by(VisionEvent.occurred_at.desc())
        .with_for_update()
    )
    if deduplicated is not None:
        delivery = session.scalar(
            select(WebhookDelivery).where(WebhookDelivery.vision_event_id == deduplicated.id)
        )
        if delivery is None:
            raise RuntimeError("视觉事件缺少 Webhook 投递记录")
        return _response(deduplicated, delivery, reused=True)
    event = VisionEvent(
        id=uuid4(),
        workspace_id=workflow.workspace_id,
        project_id=project.id,
        workflow_spec_id=workflow.id,
        capability_spec_id=capability.id,
        request_id=payload.request_id,
        idempotency_key=payload.idempotency_key,
        deduplication_key=payload.deduplication_key,
        event_type=payload.event_type,
        payload=payload.payload,
        occurred_at=_as_utc(payload.occurred_at),
    )
    delivery = WebhookDelivery(
        id=uuid4(),
        vision_event_id=event.id,
        workflow_spec_id=workflow.id,
        target_url=workflow.webhook_url,
        status="pending",
        attempt_count=0,
        next_attempt_at=datetime.now(UTC),
    )
    session.add_all([event, delivery])
    session.flush()
    return _response(event, delivery, reused=False)


def list_events(
    session: Session,
    workspace_id: UUID,
    project_id: UUID,
    *,
    limit: int,
) -> list[VisionEventListItem]:
    require_project(session, workspace_id, project_id)
    records = session.execute(
        select(VisionEvent, WebhookDelivery, WorkflowSpec)
        .join(WebhookDelivery, WebhookDelivery.vision_event_id == VisionEvent.id)
        .join(WorkflowSpec, WorkflowSpec.id == VisionEvent.workflow_spec_id)
        .where(
            VisionEvent.workspace_id == workspace_id,
            VisionEvent.project_id == project_id,
        )
        .order_by(VisionEvent.occurred_at.desc())
        .limit(limit)
    ).all()
    return [
        VisionEventListItem(
            id=event.id,
            request_id=event.request_id,
            event_type=event.event_type,
            occurred_at=_as_utc(event.occurred_at),
            workflow_spec_id=workflow.id,
            workflow_slug=workflow.workflow_slug,
            workflow_name=workflow.display_name,
            delivery_id=delivery.id,
            delivery_status=delivery.status,
            attempt_count=delivery.attempt_count,
            last_error=delivery.last_error,
            delivered_at=(
                _as_utc(delivery.delivered_at) if delivery.delivered_at is not None else None
            ),
        )
        for event, delivery, workflow in records
    ]


def _as_nonnegative_int(value: object) -> int | None:
    return value if isinstance(value, int) and value >= 0 else None


def replay_event(
    session: Session,
    workspace_id: UUID,
    project_id: UUID,
    event_id: UUID,
) -> VisionEventReplayResponse:
    require_project(session, workspace_id, project_id)
    record = session.execute(
        select(VisionEvent, WebhookDelivery, WorkflowSpec)
        .join(WebhookDelivery, WebhookDelivery.vision_event_id == VisionEvent.id)
        .join(WorkflowSpec, WorkflowSpec.id == VisionEvent.workflow_spec_id)
        .where(
            VisionEvent.id == event_id,
            VisionEvent.workspace_id == workspace_id,
            VisionEvent.project_id == project_id,
        )
    ).one_or_none()
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="未找到视觉事件")
    event, delivery, workflow = record

    payload = event.payload if isinstance(event.payload, dict) else {}
    source = payload.get("source") if isinstance(payload.get("source"), dict) else {}
    condition = (
        payload.get("condition") if isinstance(payload.get("condition"), dict) else {}
    )
    frame = payload.get("frame") if isinstance(payload.get("frame"), dict) else {}
    sample = VisionEventReplaySample(
        source_id=source.get("id") if isinstance(source.get("id"), str) else None,
        source_type=source.get("type") if isinstance(source.get("type"), str) else None,
        input_index=_as_nonnegative_int(source.get("input_index")),
        condition_kind=(
            condition.get("kind") if isinstance(condition.get("kind"), str) else None
        ),
        required_class=(
            condition.get("required_class")
            if isinstance(condition.get("required_class"), str)
            else None
        ),
        person_count=_as_nonnegative_int(condition.get("person_count")),
        required_class_count=_as_nonnegative_int(condition.get("required_class_count")),
        detection_count=_as_nonnegative_int(frame.get("detection_count")),
        width=_as_nonnegative_int(frame.get("width")),
        height=_as_nonnegative_int(frame.get("height")),
    )

    expected_class = PPE_EVENT_REQUIREMENTS.get(event.event_type)
    matched = (
        workflow.template_key == PPE_VIOLATION_WEBHOOK_TEMPLATE
        and expected_class is not None
        and event.event_type in workflow.event_types
        and sample.condition_kind == "frame-class-absence.v1"
        and sample.required_class == expected_class
        and sample.person_count is not None
        and sample.person_count > 0
        and sample.required_class_count == 0
    )
    if matched:
        reasons = [
            f"模板已启用 {event.event_type} 事件。",
            f"当前帧检测到 {sample.person_count} 名人员。",
            f"当前帧未检测到 {expected_class}。",
        ]
    else:
        reasons = [
            "该事件样本无法按当前固定 PPE 模板确认命中。",
            "回放只使用事件中已保存的受限统计信息，不会重新读取或推理原始图片。",
        ]
        if workflow.template_key != PPE_VIOLATION_WEBHOOK_TEMPLATE:
            reasons.append("工作流模板不是当前支持的 PPE Webhook 模板。")
        elif expected_class is None or event.event_type not in workflow.event_types:
            reasons.append("事件类型不在当前工作流的固定输出范围内。")
        else:
            reasons.append("事件缺少完整的帧级缺失条件，可能来自早期事件格式。")

    parsed_target = urlparse(delivery.target_url)
    return VisionEventReplayResponse(
        event_id=event.id,
        request_id=event.request_id,
        event_type=event.event_type,
        occurred_at=_as_utc(event.occurred_at),
        workflow_slug=workflow.workflow_slug,
        workflow_name=workflow.display_name,
        workflow_version=workflow.version_number,
        template_key=workflow.template_key,
        sample=sample,
        decision=VisionEventReplayDecision(
            matched=matched,
            reasons=reasons,
            deduplication_key=event.deduplication_key,
            deduplication_window_seconds=workflow.deduplication_window_seconds,
        ),
        delivery=VisionEventReplayDelivery(
            id=delivery.id,
            status=delivery.status,
            attempt_count=delivery.attempt_count,
            target_host=parsed_target.hostname,
            next_attempt_at=_as_utc(delivery.next_attempt_at),
            last_error=delivery.last_error,
            delivered_at=(
                _as_utc(delivery.delivered_at) if delivery.delivered_at is not None else None
            ),
        ),
    )


def _delivery_record(
    session: Session,
    delivery_id: UUID,
) -> tuple[WebhookDelivery, VisionEvent, WorkflowSpec, CapabilitySpec]:
    record = session.execute(
        select(WebhookDelivery, VisionEvent, WorkflowSpec, CapabilitySpec)
        .join(VisionEvent, VisionEvent.id == WebhookDelivery.vision_event_id)
        .join(WorkflowSpec, WorkflowSpec.id == WebhookDelivery.workflow_spec_id)
        .join(CapabilitySpec, CapabilitySpec.id == VisionEvent.capability_spec_id)
        .where(WebhookDelivery.id == delivery_id)
        .with_for_update()
    ).one_or_none()
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="未找到 Webhook 投递")
    return record


def _webhook_payload(
    event: VisionEvent,
    workflow: WorkflowSpec,
    capability: CapabilitySpec,
) -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "event_id": str(event.id),
        "event_type": event.event_type,
        "occurred_at": event.occurred_at.isoformat(),
        "request_id": event.request_id,
        "workflow": {
            "id": str(workflow.id),
            "slug": workflow.workflow_slug,
            "version": workflow.version_number,
        },
        "capability": {
            "id": str(capability.id),
            "slug": capability.capability_slug,
            "version": capability.version_number,
        },
        "data": event.payload,
    }


def claim_delivery(session: Session, delivery_id: UUID) -> WebhookDeliveryClaimResponse:
    delivery, event, workflow, capability = _delivery_record(session, delivery_id)
    now = datetime.now(UTC)
    if delivery.status == "delivered":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Webhook 已完成投递")
    if delivery.status == "failed":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Webhook 已达到最大重试次数")
    if delivery.status == "delivering" and delivery.claimed_at and _as_utc(delivery.claimed_at) > now - timedelta(seconds=DELIVERY_LEASE_SECONDS):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Webhook 正在投递")
    if delivery.status == "retrying" and _as_utc(delivery.next_attempt_at) > now:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Webhook 尚未到达重试时间")
    delivery.status = "delivering"
    delivery.claimed_at = now
    delivery.attempt_count += 1
    body = _webhook_payload(event, workflow, capability)
    encoded = json.dumps(body, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()
    signature = hmac_new(
        get_settings().webhook_signing_secret.encode(), encoded, sha256
    ).hexdigest()
    session.flush()
    return WebhookDeliveryClaimResponse(
        id=delivery.id,
        target_url=delivery.target_url,
        payload=body,
        signature=signature,
        attempt_count=delivery.attempt_count,
    )


def complete_delivery(
    session: Session,
    delivery_id: UUID,
    payload: WebhookDeliveryComplete,
) -> WebhookDeliveryResponse:
    delivery, _, _, _ = _delivery_record(session, delivery_id)
    if delivery.status != "delivering":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Webhook 未处于投递中状态")
    now = datetime.now(UTC)
    if payload.succeeded:
        delivery.status = "delivered"
        delivery.delivered_at = now
        delivery.last_error = None
        delivery.next_attempt_at = now
    else:
        error = payload.error or f"Webhook 返回 HTTP {payload.status_code or 0}"
        delivery.last_error = error[:2_000]
        delivery.claimed_at = None
        if delivery.attempt_count >= MAX_WEBHOOK_ATTEMPTS:
            delivery.status = "failed"
            delivery.next_attempt_at = now
        else:
            delivery.status = "retrying"
            delivery.next_attempt_at = now + timedelta(
                seconds=min(300, 2 ** delivery.attempt_count)
            )
    session.flush()
    return WebhookDeliveryResponse(
        id=delivery.id,
        vision_event_id=delivery.vision_event_id,
        status=delivery.status,
        attempt_count=delivery.attempt_count,
        next_attempt_at=delivery.next_attempt_at,
        last_error=delivery.last_error,
        delivered_at=delivery.delivered_at,
    )


def recover_deliveries(session: Session) -> WebhookDeliveryRecoveryResponse:
    now = datetime.now(UTC)
    stale_before = now - timedelta(seconds=DELIVERY_LEASE_SECONDS)
    deliveries = session.scalars(
        select(WebhookDelivery)
        .where(
            (WebhookDelivery.status == "pending")
            | (WebhookDelivery.status == "retrying")
            | ((WebhookDelivery.status == "delivering") & (WebhookDelivery.claimed_at < stale_before))
        )
        .where(WebhookDelivery.next_attempt_at <= now)
        .with_for_update()
    ).all()
    queued_ids: list[UUID] = []
    for delivery in deliveries:
        if delivery.attempt_count >= MAX_WEBHOOK_ATTEMPTS:
            delivery.status = "failed"
            continue
        delivery.status = "pending"
        delivery.claimed_at = None
        queued_ids.append(delivery.id)
    session.flush()
    return WebhookDeliveryRecoveryResponse(queued_delivery_ids=queued_ids)
