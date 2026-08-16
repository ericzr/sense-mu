import math
from collections.abc import Callable
from datetime import UTC, datetime
from operator import ge, gt, le, lt
from typing import Any
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from sensemu_api.catalog_service import conflict, require_project
from sensemu_api.db.models import (
    Evaluation,
    EvaluationPolicy,
    Model,
    ModelVersion,
    Project,
    Run,
)
from sensemu_api.evaluation_schemas import (
    EvaluationPolicyCreate,
    EvaluationResponse,
    EvaluationRule,
)
from sensemu_api.storage import Storage

RuleOperator = Callable[[float, float], bool]
OPERATORS: dict[str, RuleOperator] = {">=": ge, "<=": le, ">": gt, "<": lt}


def create_policy(
    session: Session,
    workspace_id: UUID,
    project_id: UUID,
    payload: EvaluationPolicyCreate,
) -> EvaluationPolicy:
    require_project(session, workspace_id, project_id)
    session.scalar(select(Project.id).where(Project.id == project_id).with_for_update())
    session.execute(
        update(EvaluationPolicy)
        .where(
            EvaluationPolicy.project_id == project_id,
            EvaluationPolicy.is_active.is_(True),
        )
        .values(is_active=False)
    )
    session.execute(
        update(ModelVersion)
        .where(
            ModelVersion.model_id.in_(
                select(Model.id).where(Model.project_id == project_id)
            ),
            ModelVersion.status.in_({"approved", "rejected"}),
        )
        .values(status="candidate")
    )
    next_version = (
        session.scalar(
            select(func.max(EvaluationPolicy.version_number)).where(
                EvaluationPolicy.project_id == project_id
            )
        )
        or 0
    ) + 1
    policy = EvaluationPolicy(
        project_id=project_id,
        version_number=next_version,
        name=payload.name,
        rules=[rule.model_dump() for rule in payload.rules],
        is_active=True,
    )
    session.add(policy)
    session.flush()
    return policy


def list_policies(
    session: Session,
    workspace_id: UUID,
    project_id: UUID,
) -> list[EvaluationPolicy]:
    require_project(session, workspace_id, project_id)
    return list(
        session.scalars(
            select(EvaluationPolicy)
            .where(EvaluationPolicy.project_id == project_id)
            .order_by(
                EvaluationPolicy.is_active.desc(),
                EvaluationPolicy.version_number.desc(),
            )
        ).all()
    )


def active_policy(session: Session, project_id: UUID) -> EvaluationPolicy | None:
    return session.scalar(
        select(EvaluationPolicy)
        .where(
            EvaluationPolicy.project_id == project_id,
            EvaluationPolicy.is_active.is_(True),
        )
        .order_by(EvaluationPolicy.version_number.desc())
    )


def evaluate_rules(
    rules: list[dict[str, Any]],
    metrics: dict[str, Any],
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for raw_rule in rules:
        rule = EvaluationRule.model_validate(raw_rule)
        value = metrics.get(rule.metric)
        numeric = (
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and math.isfinite(float(value))
        )
        actual = float(value) if numeric else None
        passed = bool(
            numeric and OPERATORS[rule.operator](actual, float(rule.threshold))
        )
        results.append(
            {
                **rule.model_dump(),
                "actual": actual,
                "passed": passed,
                "reason": None if numeric else "模型产物缺少可比较的指标",
            }
        )
    return results


def _require_model_version(
    session: Session,
    workspace_id: UUID,
    model_version_id: UUID,
) -> tuple[ModelVersion, Model, Run]:
    record = session.execute(
        select(ModelVersion, Model, Run)
        .join(Model, Model.id == ModelVersion.model_id)
        .join(Project, Project.id == Model.project_id)
        .join(Run, Run.id == ModelVersion.run_id)
        .where(
            ModelVersion.id == model_version_id,
            Project.workspace_id == workspace_id,
        )
        .with_for_update()
    ).one_or_none()
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="未找到模型版本")
    return record


def evaluate_model_version(
    session: Session,
    storage: Storage,
    workspace_id: UUID,
    model_version: ModelVersion,
    project_id: UUID,
    dataset_version_id: UUID,
    policy: EvaluationPolicy | None = None,
) -> Evaluation | None:
    selected_policy = policy or active_policy(session, project_id)
    if selected_policy is None:
        return None
    existing = session.scalar(
        select(Evaluation).where(
            Evaluation.model_version_id == model_version.id,
            Evaluation.policy_id == selected_policy.id,
            Evaluation.source == "training-validation",
            Evaluation.dataset_version_id == dataset_version_id,
        )
    )
    if existing is not None:
        return existing

    evaluated_at = datetime.now(UTC)
    rule_results = evaluate_rules(selected_policy.rules, model_version.metrics)
    verdict = "approved" if all(item["passed"] for item in rule_results) else "rejected"
    evaluation_id = uuid4()
    report = {
        "schema_version": "1.0",
        "evaluation_id": str(evaluation_id),
        "source": "training-validation",
        "workspace_id": str(workspace_id),
        "project_id": str(project_id),
        "model_version_id": str(model_version.id),
        "dataset_version_id": str(dataset_version_id),
        "policy": {
            "id": str(selected_policy.id),
            "name": selected_policy.name,
            "version_number": selected_policy.version_number,
            "rules": selected_policy.rules,
        },
        "metrics": model_version.metrics,
        "rule_results": rule_results,
        "verdict": verdict,
        "evaluated_at": evaluated_at.isoformat(),
    }
    report_uri = storage.put_json(
        (
            f"workspaces/{workspace_id}/projects/{project_id}/evaluations/"
            f"{evaluation_id}/report.json"
        ),
        report,
    )
    evaluation = Evaluation(
        id=evaluation_id,
        model_version_id=model_version.id,
        dataset_version_id=dataset_version_id,
        policy_id=selected_policy.id,
        source="training-validation",
        status="completed",
        verdict=verdict,
        metrics=model_version.metrics,
        rule_results=rule_results,
        report_uri=report_uri,
        evaluated_at=evaluated_at,
    )
    session.add(evaluation)
    acceptance = session.scalar(
        select(Evaluation)
        .where(
            Evaluation.model_version_id == model_version.id,
            Evaluation.policy_id == selected_policy.id,
            Evaluation.source == "acceptance-dataset",
        )
        .order_by(Evaluation.evaluated_at.desc())
        .limit(1)
    )
    model_version.status = (
        acceptance.verdict
        if acceptance is not None
        else "validation_passed" if verdict == "approved" else "validation_failed"
    )
    session.flush()
    return evaluation


def evaluate_current_policy(
    session: Session,
    storage: Storage,
    workspace_id: UUID,
    model_version_id: UUID,
) -> Evaluation:
    model_version, model, run = _require_model_version(
        session, workspace_id, model_version_id
    )
    policy = active_policy(session, model.project_id)
    if policy is None:
        raise conflict("项目尚未配置有效的评测门禁")
    evaluation = evaluate_model_version(
        session,
        storage,
        workspace_id,
        model_version,
        model.project_id,
        run.dataset_version_id,
        policy,
    )
    if evaluation is None:
        raise conflict("项目尚未配置有效的评测门禁")
    return evaluation


def list_evaluations(
    session: Session,
    workspace_id: UUID,
    project_id: UUID,
) -> list[EvaluationResponse]:
    require_project(session, workspace_id, project_id)
    statement = (
        select(Evaluation, EvaluationPolicy, ModelVersion, Model)
        .join(EvaluationPolicy, EvaluationPolicy.id == Evaluation.policy_id)
        .join(ModelVersion, ModelVersion.id == Evaluation.model_version_id)
        .join(Model, Model.id == ModelVersion.model_id)
        .where(Model.project_id == project_id)
        .order_by(Evaluation.evaluated_at.desc())
    )
    return [
        to_response(evaluation, policy, model_version, model)
        for evaluation, policy, model_version, model in session.execute(statement)
    ]


def to_response(
    evaluation: Evaluation,
    policy: EvaluationPolicy,
    model_version: ModelVersion,
    model: Model,
) -> EvaluationResponse:
    return EvaluationResponse(
        id=evaluation.id,
        model_version_id=evaluation.model_version_id,
        model_name=model.name,
        model_version_number=model_version.version_number,
        dataset_version_id=evaluation.dataset_version_id,
        policy_id=evaluation.policy_id,
        policy_name=policy.name,
        policy_version=policy.version_number,
        source=evaluation.source,
        status=evaluation.status,
        verdict=evaluation.verdict,
        metrics=evaluation.metrics,
        rule_results=evaluation.rule_results,
        report_uri=evaluation.report_uri,
        evaluated_at=evaluation.evaluated_at,
        created_at=evaluation.created_at,
    )


def response_for_evaluation(session: Session, evaluation: Evaluation) -> EvaluationResponse:
    policy = session.get(EvaluationPolicy, evaluation.policy_id)
    model_version = session.get(ModelVersion, evaluation.model_version_id)
    if policy is None or model_version is None:
        raise conflict("评测记录的关联对象不存在")
    model = session.get(Model, model_version.model_id)
    if model is None:
        raise conflict("评测记录的模型不存在")
    return to_response(evaluation, policy, model_version, model)
