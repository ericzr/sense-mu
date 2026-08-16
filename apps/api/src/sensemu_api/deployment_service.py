from datetime import UTC, datetime
from decimal import Decimal
from hashlib import sha256
from secrets import compare_digest, token_urlsafe
from typing import Any
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from sensemu_api.catalog_service import conflict, require_active_project, require_project
from sensemu_api.config import get_settings
from sensemu_api.db.models import (
    Deployment,
    Evaluation,
    EvaluationPolicy,
    MarketplaceLedgerEntry,
    MarketplaceListing,
    MarketplaceSubscription,
    Model,
    ModelVersion,
    Project,
    UsageRecord,
    UsageReservation,
    Workspace,
)
from sensemu_api.deployment_schemas import (
    DeploymentCreate,
    DeploymentResponse,
    GatewayDeploymentResponse,
    UsageRecordCreate,
    UsageRecordResponse,
)
from sensemu_api.storage import Storage
from sensemu_api.workflow_service import event_bindings_for_deployment


def _key_hash(api_key: str) -> str:
    return sha256(api_key.encode()).hexdigest()


def _new_api_key() -> tuple[str, str, str]:
    api_key = f"smu_live_{token_urlsafe(32)}"
    return api_key, api_key[:16], _key_hash(api_key)


def _contract_for(task_type: str) -> str:
    return {
        "object-detection": "detections.v1",
        "classification": "classification.v1",
        "segmentation": "mask.v1",
        "pose": "keypoints.v1",
        "ocr": "text.v1",
    }.get(task_type, "predictions.v1")


def _require_model_for_project(
    session: Session,
    workspace_id: UUID,
    project_id: UUID,
    model_version_id: UUID,
) -> tuple[ModelVersion, Model, Project]:
    record = session.execute(
        select(ModelVersion, Model, Project)
        .join(Model, Model.id == ModelVersion.model_id)
        .join(Project, Project.id == Model.project_id)
        .where(
            ModelVersion.id == model_version_id,
            Model.project_id == project_id,
            Project.workspace_id == workspace_id,
        )
        .with_for_update()
    ).one_or_none()
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="未找到模型版本")
    return record


def _current_approval(
    session: Session,
    model_version_id: UUID,
) -> tuple[Evaluation, EvaluationPolicy] | None:
    return session.execute(
        select(Evaluation, EvaluationPolicy)
        .join(EvaluationPolicy, EvaluationPolicy.id == Evaluation.policy_id)
        .where(
            Evaluation.model_version_id == model_version_id,
            Evaluation.source == "acceptance-dataset",
            Evaluation.verdict == "approved",
            EvaluationPolicy.is_active.is_(True),
        )
        .order_by(Evaluation.evaluated_at.desc())
        .limit(1)
    ).one_or_none()


def create_deployment(
    session: Session,
    storage: Storage,
    workspace_id: UUID,
    project_id: UUID,
    payload: DeploymentCreate,
) -> tuple[Deployment, str]:
    require_active_project(session, workspace_id, project_id)
    model_version, model, project = _require_model_for_project(
        session, workspace_id, project_id, payload.model_version_id
    )
    approval = _current_approval(session, model_version.id)
    if approval is None:
        raise conflict("只能发布通过当前评测门禁的模型版本")
    evaluation, policy = approval
    existing = session.scalar(
        select(Deployment).where(
            Deployment.workspace_id == workspace_id,
            Deployment.endpoint_slug == payload.endpoint_slug,
        )
    )
    if existing is not None:
        raise conflict("当前工作区已存在相同的服务地址")

    deployment_id = uuid4()
    api_key, key_prefix, key_hash = _new_api_key()
    published_at = datetime.now(UTC)
    spec = {
        "schema_version": "1.0",
        "deployment_id": str(deployment_id),
        "workspace_id": str(workspace_id),
        "project_id": str(project_id),
        "endpoint_slug": payload.endpoint_slug,
        "environment": payload.environment,
        "capability_id": "vision.predict",
        "contract": _contract_for(project.task_type),
        "model": {
            "id": str(model.id),
            "version_id": str(model_version.id),
            "version_number": model_version.version_number,
            "artifact_uri": model_version.artifact_uri,
            "task_type": project.task_type,
        },
        "gate": {
            "evaluation_id": str(evaluation.id),
            "policy_id": str(policy.id),
            "policy_version": policy.version_number,
            "verdict": evaluation.verdict,
        },
        "published_at": published_at.isoformat(),
    }
    spec_uri = storage.put_json(
        (
            f"workspaces/{workspace_id}/projects/{project_id}/deployments/"
            f"{deployment_id}/deployment-spec.json"
        ),
        spec,
    )
    deployment = Deployment(
        id=deployment_id,
        workspace_id=workspace_id,
        model_version_id=model_version.id,
        evaluation_id=evaluation.id,
        name=payload.name,
        endpoint_slug=payload.endpoint_slug,
        environment=payload.environment,
        status="published",
        spec_uri=spec_uri,
        api_key_prefix=key_prefix,
        api_key_hash=key_hash,
        published_at=published_at,
    )
    session.add(deployment)
    session.flush()
    return deployment, api_key


def _usage_totals(session: Session, deployment_id: UUID) -> tuple[int, float]:
    row = session.execute(
        select(
            func.count(UsageRecord.id),
            func.coalesce(func.sum(UsageRecord.billable_units), 0),
        ).where(UsageRecord.deployment_id == deployment_id)
    ).one()
    return int(row[0]), float(row[1])


def to_response(
    session: Session,
    deployment: Deployment,
    model_version: ModelVersion | None = None,
    model: Model | None = None,
    policy: EvaluationPolicy | None = None,
) -> DeploymentResponse:
    resolved_version = model_version or session.get(ModelVersion, deployment.model_version_id)
    if resolved_version is None:
        raise conflict("在线服务关联的模型版本不存在")
    resolved_model = model or session.get(Model, resolved_version.model_id)
    if resolved_model is None:
        raise conflict("在线服务关联的模型不存在")
    resolved_project = session.get(Project, resolved_model.project_id)
    if resolved_project is None:
        raise conflict("在线服务关联的项目不存在")
    resolved_policy = policy
    if resolved_policy is None and deployment.evaluation_id:
        resolved_policy = session.scalar(
            select(EvaluationPolicy)
            .join(Evaluation, Evaluation.policy_id == EvaluationPolicy.id)
            .where(Evaluation.id == deployment.evaluation_id)
        )
    request_count, billable_units = _usage_totals(session, deployment.id)
    workspace = session.get(Workspace, deployment.workspace_id)
    if workspace is None:
        raise conflict("在线服务关联的工作区不存在")
    settings = get_settings()
    return DeploymentResponse(
        id=deployment.id,
        workspace_id=deployment.workspace_id,
        workspace_slug=workspace.slug,
        project_id=resolved_model.project_id,
        model_version_id=deployment.model_version_id,
        model_name=resolved_model.name,
        model_version_number=resolved_version.version_number,
        task_type=resolved_project.task_type,
        evaluation_id=deployment.evaluation_id,
        evaluation_policy_version=(
            resolved_policy.version_number if resolved_policy else None
        ),
        name=deployment.name,
        endpoint_slug=deployment.endpoint_slug,
        endpoint_url=(
            f"{settings.inference_gateway_public_url.rstrip('/')}/inference/v1/workspaces/"
            f"{workspace.slug}/endpoints/{deployment.endpoint_slug}:predict"
        ),
        environment=deployment.environment,
        status=deployment.status,
        spec_uri=deployment.spec_uri,
        api_key_prefix=deployment.api_key_prefix,
        request_count=request_count,
        billable_units=billable_units,
        published_at=deployment.published_at,
        disabled_at=deployment.disabled_at,
        created_at=deployment.created_at,
        updated_at=deployment.updated_at,
    )


def list_deployments(
    session: Session,
    workspace_id: UUID,
    project_id: UUID,
) -> list[DeploymentResponse]:
    require_project(session, workspace_id, project_id)
    statement = (
        select(Deployment, ModelVersion, Model)
        .join(ModelVersion, ModelVersion.id == Deployment.model_version_id)
        .join(Model, Model.id == ModelVersion.model_id)
        .where(
            Deployment.workspace_id == workspace_id,
            Model.project_id == project_id,
        )
        .order_by(Deployment.created_at.desc())
    )
    return [
        to_response(session, deployment, model_version, model)
        for deployment, model_version, model in session.execute(statement)
    ]


def require_deployment(
    session: Session,
    workspace_id: UUID,
    deployment_id: UUID,
    *,
    for_update: bool = False,
) -> Deployment:
    statement = select(Deployment).where(
        Deployment.id == deployment_id,
        Deployment.workspace_id == workspace_id,
    )
    if for_update:
        statement = statement.with_for_update()
    deployment = session.scalar(statement)
    if deployment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="未找到在线服务")
    return deployment


def set_deployment_enabled(
    session: Session,
    workspace_id: UUID,
    deployment_id: UUID,
    *,
    enabled: bool,
) -> Deployment:
    deployment = require_deployment(session, workspace_id, deployment_id, for_update=True)
    now = datetime.now(UTC)
    if enabled:
        if _current_approval(session, deployment.model_version_id) is None:
            raise conflict("模型没有通过当前评测门禁，无法重新启用")
        deployment.status = "published"
        deployment.disabled_at = None
        deployment.published_at = deployment.published_at or now
    else:
        deployment.status = "disabled"
        deployment.disabled_at = now
    session.flush()
    return deployment


def rotate_api_key(
    session: Session,
    workspace_id: UUID,
    deployment_id: UUID,
) -> tuple[Deployment, str]:
    deployment = require_deployment(session, workspace_id, deployment_id, for_update=True)
    api_key, key_prefix, key_hash = _new_api_key()
    deployment.api_key_prefix = key_prefix
    deployment.api_key_hash = key_hash
    session.flush()
    return deployment, api_key


def resolve_endpoint(
    session: Session,
    workspace_slug: str,
    endpoint_slug: str,
    api_key: str,
) -> GatewayDeploymentResponse:
    record = session.execute(
        select(Deployment, ModelVersion, Model, Project, Workspace)
        .join(ModelVersion, ModelVersion.id == Deployment.model_version_id)
        .join(Model, Model.id == ModelVersion.model_id)
        .join(Project, Project.id == Model.project_id)
        .join(Workspace, Workspace.id == Deployment.workspace_id)
        .where(
            Workspace.slug == workspace_slug,
            Deployment.endpoint_slug == endpoint_slug,
        )
    ).one_or_none()
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="未找到推理端点")
    deployment, model_version, _, project, workspace = record
    if deployment.status != "published":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="未找到推理端点")
    if not deployment.api_key_hash or not compare_digest(
        deployment.api_key_hash, _key_hash(api_key)
    ):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="API 密钥无效")
    return GatewayDeploymentResponse(
        deployment_id=deployment.id,
        workspace_id=deployment.workspace_id,
        workspace_slug=workspace.slug,
        endpoint_slug=deployment.endpoint_slug,
        model_version_id=model_version.id,
        artifact_uri=model_version.artifact_uri,
        task_type=project.task_type,
        contract=_contract_for(project.task_type),
        workflow_bindings=event_bindings_for_deployment(session, deployment.id),
    )


def record_usage(
    session: Session,
    payload: UsageRecordCreate,
) -> UsageRecordResponse:
    deployment = session.get(Deployment, payload.deployment_id)
    if deployment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="未找到在线服务")
    existing = session.scalar(
        select(UsageRecord).where(UsageRecord.request_id == payload.request_id)
    )
    requested_units = Decimal(str(payload.billable_units))
    if existing is not None:
        same_usage = (
            existing.deployment_id == payload.deployment_id
            and existing.capability_id == payload.capability_id
            and existing.billable_units == requested_units
            and existing.unit == payload.unit
        )
        if not same_usage:
            raise conflict("请求编号已用于另一条不同的计量记录")
        return UsageRecordResponse(
            **_usage_payload(existing),
            reused=True,
        )
    listing_id: UUID | None = None
    subscription_id: UUID | None = None
    listing: MarketplaceListing | None = None
    subscription: MarketplaceSubscription | None = None
    if payload.reservation_id is not None:
        reservation = session.scalar(
            select(UsageReservation)
            .where(UsageReservation.id == payload.reservation_id)
            .with_for_update()
        )
        if reservation is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="未找到额度预留")
        if (
            reservation.request_id != payload.request_id
            or reservation.deployment_id != deployment.id
            or Decimal(reservation.units) != requested_units
        ):
            raise conflict("额度预留与调用计量不一致")
        if reservation.status == "released":
            raise conflict("额度预留已经释放")
        subscription = session.scalar(
            select(MarketplaceSubscription)
            .where(MarketplaceSubscription.id == reservation.subscription_id)
            .with_for_update()
        )
        if subscription is None:
            raise conflict("额度预留关联的调用授权不存在")
        listing = session.get(MarketplaceListing, subscription.listing_id)
        if listing is None:
            raise conflict("调用授权关联的算法商品不存在")
        if reservation.status == "pending":
            subscription.reserved_units = max(
                0, subscription.reserved_units - reservation.units
            )
            subscription.consumed_units += reservation.units
            reservation.status = "consumed"
            reservation.finalized_at = datetime.now(UTC)
        listing_id = listing.id
        subscription_id = subscription.id
    usage = UsageRecord(
        workspace_id=deployment.workspace_id,
        deployment_id=deployment.id,
        listing_id=listing_id,
        subscription_id=subscription_id,
        request_id=payload.request_id,
        capability_id=payload.capability_id,
        billable_units=requested_units,
        unit=payload.unit,
        dimensions=payload.dimensions,
        occurred_at=payload.occurred_at,
    )
    session.add(usage)
    session.flush()
    if listing is not None and subscription is not None:
        session.add(
            MarketplaceLedgerEntry(
                usage_record_id=usage.id,
                listing_id=listing.id,
                subscription_id=subscription.id,
                buyer_workspace_id=subscription.buyer_workspace_id,
                provider_workspace_id=listing.provider_workspace_id,
                entry_type="usage_accrual",
                amount_micros=(
                    int(requested_units)
                    * subscription.price_per_1000_cents
                    * 10
                ),
                currency="CNY",
                settlement_status="unsettled",
                occurred_at=usage.occurred_at,
            )
        )
        session.flush()
    return UsageRecordResponse(**_usage_payload(usage), reused=False)


def _usage_payload(usage: UsageRecord) -> dict[str, Any]:
    return {
        "id": usage.id,
        "deployment_id": usage.deployment_id,
        "listing_id": usage.listing_id,
        "subscription_id": usage.subscription_id,
        "request_id": usage.request_id,
        "capability_id": usage.capability_id,
        "billable_units": float(usage.billable_units),
        "unit": usage.unit,
        "dimensions": usage.dimensions,
        "occurred_at": usage.occurred_at,
    }
