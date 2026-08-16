import json
from datetime import UTC, datetime
from hashlib import sha256
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from sensemu_api.catalog_service import conflict, require_active_project, require_project
from sensemu_api.db.models import (
    CapabilitySpec,
    Deployment,
    Model,
    ModelVersion,
    Project,
    WorkflowSpec,
)
from sensemu_api.deployment_schemas import WorkflowEventBinding
from sensemu_api.storage import Storage
from sensemu_api.workflow_schemas import WorkflowSpecCreate, WorkflowSpecResponse

TEMPLATE_KEY = "ppe-violation-webhook.v1"


def event_bindings_for_deployment(
    session: Session,
    deployment_id: UUID,
) -> list[WorkflowEventBinding]:
    workflows = session.scalars(
        select(WorkflowSpec)
        .join(CapabilitySpec, CapabilitySpec.id == WorkflowSpec.capability_spec_id)
        .where(
            CapabilitySpec.deployment_id == deployment_id,
            CapabilitySpec.status == "published",
            WorkflowSpec.status == "published",
        )
        .order_by(WorkflowSpec.workflow_slug.asc(), WorkflowSpec.version_number.desc())
    ).all()
    return [
        WorkflowEventBinding(
            workflow_id=workflow.id,
            workflow_slug=workflow.workflow_slug,
            workflow_version=workflow.version_number,
            template_key=workflow.template_key,
            event_types=workflow.event_types,
            deduplication_window_seconds=workflow.deduplication_window_seconds,
        )
        for workflow in workflows
    ]


def _response(
    workflow: WorkflowSpec,
    capability: CapabilitySpec,
    project_id: UUID,
) -> WorkflowSpecResponse:
    return WorkflowSpecResponse(
        id=workflow.id,
        workspace_id=workflow.workspace_id,
        project_id=project_id,
        capability_spec_id=capability.id,
        capability_slug=capability.capability_slug,
        capability_version_number=capability.version_number,
        workflow_slug=workflow.workflow_slug,
        version_number=workflow.version_number,
        display_name=workflow.display_name,
        template_key=workflow.template_key,
        event_types=workflow.event_types,
        deduplication_window_seconds=workflow.deduplication_window_seconds,
        webhook_url=workflow.webhook_url,
        status=workflow.status,
        content_hash=workflow.content_hash,
        spec_uri=workflow.spec_uri,
        published_at=workflow.published_at,
        created_at=workflow.created_at,
    )


def _capability_record(
    session: Session,
    workspace_id: UUID,
    capability_spec_id: UUID,
) -> tuple[CapabilitySpec, Project]:
    record = session.execute(
        select(CapabilitySpec, Project)
        .join(Deployment, Deployment.id == CapabilitySpec.deployment_id)
        .join(ModelVersion, ModelVersion.id == Deployment.model_version_id)
        .join(Model, Model.id == ModelVersion.model_id)
        .join(Project, Project.id == Model.project_id)
        .where(
            CapabilitySpec.id == capability_spec_id,
            CapabilitySpec.workspace_id == workspace_id,
        )
        .with_for_update()
    ).one_or_none()
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="未找到能力契约")
    return record


def create_spec(
    session: Session,
    storage: Storage,
    workspace_id: UUID,
    project_id: UUID,
    payload: WorkflowSpecCreate,
) -> WorkflowSpecResponse:
    require_active_project(session, workspace_id, project_id)
    capability, capability_project = _capability_record(
        session, workspace_id, payload.capability_spec_id
    )
    if capability_project.id != project_id:
        raise conflict("工作流必须引用当前项目中的能力契约")
    if capability.status != "published":
        raise conflict("只有已发布的能力契约可以创建工作流")
    supported_events = set(capability.output_spec.get("business_events", []))
    unsupported_events = sorted(set(payload.event_types) - supported_events)
    if unsupported_events:
        raise conflict(f"能力契约未声明业务事件：{', '.join(unsupported_events)}")
    version_number = (
        session.scalar(
            select(func.coalesce(func.max(WorkflowSpec.version_number), 0)).where(
                WorkflowSpec.workspace_id == workspace_id,
                WorkflowSpec.workflow_slug == payload.workflow_slug,
            )
        )
        + 1
    )
    published_at = datetime.now(UTC)
    document = {
        "apiVersion": "sensemu.ai/v1",
        "kind": "WorkflowSpec",
        "metadata": {
            "id": payload.workflow_slug,
            "version": version_number,
            "workspace_id": str(workspace_id),
            "status": "published",
        },
        "spec": {
            "template": TEMPLATE_KEY,
            "capability": {
                "id": str(capability.id),
                "slug": capability.capability_slug,
                "version": capability.version_number,
                "content_hash": capability.content_hash,
            },
            "blocks": [
                {"id": "invoke", "type": "capability.invoke"},
                {
                    "id": "deduplicate",
                    "type": "temporal.deduplicate",
                    "window_seconds": payload.deduplication_window_seconds,
                },
                {"id": "emit", "type": "sink.webhook"},
            ],
            "events": payload.event_types,
            "webhook": {"url": payload.webhook_url, "signature": "pending"},
        },
    }
    content_hash = sha256(
        json.dumps(
            document,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode()
    ).hexdigest()
    spec_uri = storage.put_json(
        (
            f"workspaces/{workspace_id}/workflows/{payload.workflow_slug}/"
            f"v{version_number}/workflow-spec.json"
        ),
        document,
    )
    workflow = WorkflowSpec(
        id=uuid4(),
        workspace_id=workspace_id,
        capability_spec_id=capability.id,
        workflow_slug=payload.workflow_slug,
        version_number=version_number,
        display_name=payload.display_name,
        template_key=TEMPLATE_KEY,
        event_types=payload.event_types,
        deduplication_window_seconds=payload.deduplication_window_seconds,
        webhook_url=payload.webhook_url,
        status="published",
        content_hash=content_hash,
        spec_uri=spec_uri,
        published_at=published_at,
    )
    session.add(workflow)
    session.flush()
    return _response(workflow, capability, project_id)


def list_specs(
    session: Session,
    workspace_id: UUID,
    project_id: UUID,
) -> list[WorkflowSpecResponse]:
    require_project(session, workspace_id, project_id)
    records = session.execute(
        select(WorkflowSpec, CapabilitySpec, Project.id)
        .join(CapabilitySpec, CapabilitySpec.id == WorkflowSpec.capability_spec_id)
        .join(Deployment, Deployment.id == CapabilitySpec.deployment_id)
        .join(ModelVersion, ModelVersion.id == Deployment.model_version_id)
        .join(Model, Model.id == ModelVersion.model_id)
        .join(Project, Project.id == Model.project_id)
        .where(
            WorkflowSpec.workspace_id == workspace_id,
            Project.id == project_id,
        )
        .order_by(WorkflowSpec.workflow_slug.asc(), WorkflowSpec.version_number.desc())
    ).all()
    return [
        _response(workflow, capability, resolved_project_id)
        for workflow, capability, resolved_project_id in records
    ]
