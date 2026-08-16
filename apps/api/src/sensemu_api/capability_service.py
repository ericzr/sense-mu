import json
from datetime import UTC, datetime
from hashlib import sha256
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from sensemu_api.capability_schemas import (
    CapabilitySpecCreate,
    CapabilitySpecResponse,
)
from sensemu_api.catalog_service import conflict, require_project
from sensemu_api.db.models import (
    CapabilitySpec,
    Deployment,
    Evaluation,
    EvaluationPolicy,
    Model,
    ModelVersion,
    Project,
)
from sensemu_api.deployment_service import _contract_for, require_deployment
from sensemu_api.storage import Storage


def _response(
    capability: CapabilitySpec,
    project_id: UUID,
) -> CapabilitySpecResponse:
    return CapabilitySpecResponse(
        id=capability.id,
        workspace_id=capability.workspace_id,
        project_id=project_id,
        deployment_id=capability.deployment_id,
        capability_slug=capability.capability_slug,
        version_number=capability.version_number,
        display_name=capability.display_name,
        problem_definition=capability.problem_definition,
        input=capability.input_spec,
        output=capability.output_spec,
        applicability=capability.applicability,
        delivery=capability.delivery,
        evidence=capability.evidence,
        status=capability.status,
        content_hash=capability.content_hash,
        spec_uri=capability.spec_uri,
        published_at=capability.published_at,
        created_at=capability.created_at,
    )


def _deployment_record(
    session: Session,
    deployment_id: UUID,
) -> tuple[Deployment, ModelVersion, Model, Project, Evaluation | None, EvaluationPolicy | None]:
    record = session.execute(
        select(Deployment, ModelVersion, Model, Project, Evaluation, EvaluationPolicy)
        .join(ModelVersion, ModelVersion.id == Deployment.model_version_id)
        .join(Model, Model.id == ModelVersion.model_id)
        .join(Project, Project.id == Model.project_id)
        .outerjoin(Evaluation, Evaluation.id == Deployment.evaluation_id)
        .outerjoin(EvaluationPolicy, EvaluationPolicy.id == Evaluation.policy_id)
        .where(Deployment.id == deployment_id)
    ).one_or_none()
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="未找到在线服务")
    return record


def create_spec(
    session: Session,
    storage: Storage,
    workspace_id: UUID,
    deployment_id: UUID,
    payload: CapabilitySpecCreate,
) -> CapabilitySpecResponse:
    deployment = require_deployment(session, workspace_id, deployment_id, for_update=True)
    if deployment.status != "published" or deployment.environment != "production":
        raise conflict("只有已发布的生产服务可以固化能力契约")
    existing = session.scalar(
        select(CapabilitySpec).where(CapabilitySpec.deployment_id == deployment.id)
    )
    if existing is not None:
        raise conflict("该在线服务已经固化能力契约；修改请发布新服务版本")

    (
        _,
        model_version,
        model,
        project,
        evaluation,
        policy,
    ) = _deployment_record(session, deployment.id)
    if project.status == "paused":
        raise conflict("项目已暂停，请先继续项目")
    expected_contract = _contract_for(project.task_type)
    if payload.output.contract != expected_contract:
        raise conflict(f"当前任务的输出协议必须为 {expected_contract}")
    version_number = (
        session.scalar(
            select(func.coalesce(func.max(CapabilitySpec.version_number), 0)).where(
                CapabilitySpec.workspace_id == workspace_id,
                CapabilitySpec.capability_slug == payload.capability_slug,
            )
        )
        + 1
    )
    published_at = datetime.now(UTC)
    evidence = {
        "deployment_id": str(deployment.id),
        "model_id": str(model.id),
        "model_version_id": str(model_version.id),
        "model_version_number": model_version.version_number,
        "evaluation_id": str(evaluation.id) if evaluation else None,
        "evaluation_policy_id": str(policy.id) if policy else None,
        "evaluation_policy_version": policy.version_number if policy else None,
        "evaluation_metrics": model_version.metrics,
    }
    document = {
        "apiVersion": "sensemu.ai/v1",
        "kind": "CapabilitySpec",
        "metadata": {
            "id": payload.capability_slug,
            "version": version_number,
            "workspace_id": str(workspace_id),
            "status": "published",
        },
        "spec": {
            "display_name": payload.display_name,
            "problem_definition": payload.problem_definition,
            "input": payload.input.model_dump(mode="json"),
            "output": payload.output.model_dump(mode="json"),
            "applicability": payload.applicability.model_dump(mode="json"),
            "evidence": evidence,
            "implementation": {
                "deployment_id": str(deployment.id),
                "model_version_id": str(model_version.id),
                "artifact_uri": model_version.artifact_uri,
            },
            "delivery": payload.delivery.model_dump(mode="json"),
        },
    }
    encoded_document = json.dumps(
        document,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    content_hash = sha256(encoded_document).hexdigest()
    spec_uri = storage.put_json(
        (
            f"workspaces/{workspace_id}/capabilities/{payload.capability_slug}/"
            f"v{version_number}/capability-spec.json"
        ),
        document,
    )
    capability = CapabilitySpec(
        id=uuid4(),
        workspace_id=workspace_id,
        deployment_id=deployment.id,
        capability_slug=payload.capability_slug,
        version_number=version_number,
        display_name=payload.display_name,
        problem_definition=payload.problem_definition,
        input_spec=payload.input.model_dump(mode="json"),
        output_spec=payload.output.model_dump(mode="json"),
        applicability=payload.applicability.model_dump(mode="json"),
        delivery=payload.delivery.model_dump(mode="json"),
        evidence=evidence,
        status="published",
        content_hash=content_hash,
        spec_uri=spec_uri,
        published_at=published_at,
    )
    session.add(capability)
    session.flush()
    return _response(capability, project.id)


def list_specs(
    session: Session,
    workspace_id: UUID,
    project_id: UUID,
) -> list[CapabilitySpecResponse]:
    require_project(session, workspace_id, project_id)
    records = session.execute(
        select(CapabilitySpec, Project.id)
        .join(Deployment, Deployment.id == CapabilitySpec.deployment_id)
        .join(ModelVersion, ModelVersion.id == Deployment.model_version_id)
        .join(Model, Model.id == ModelVersion.model_id)
        .join(Project, Project.id == Model.project_id)
        .where(
            CapabilitySpec.workspace_id == workspace_id,
            Project.id == project_id,
        )
        .order_by(
            CapabilitySpec.capability_slug.asc(),
            CapabilitySpec.version_number.desc(),
        )
    ).all()
    return [_response(capability, resolved_project_id) for capability, resolved_project_id in records]
