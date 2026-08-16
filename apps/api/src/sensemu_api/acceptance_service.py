from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from sensemu_api.catalog_service import conflict, require_active_project, require_project
from sensemu_api.config import get_settings
from sensemu_api.db.models import (
    DatasetVersion,
    Evaluation,
    EvaluationPolicy,
    Model,
    ModelVersion,
    Project,
    Run,
)
from sensemu_api.evaluation_schemas import AcceptanceRunCreate, WorkerAcceptanceCompletion
from sensemu_api.evaluation_service import active_policy, evaluate_rules
from sensemu_api.storage import Storage
from sensemu_api.training_service import (
    append_run_event,
    require_dataset_version,
    require_run,
)

RUN_TYPE = "model.acceptance-evaluate"


def _require_model_version(
    session: Session,
    workspace_id: UUID,
    project_id: UUID,
    model_version_id: UUID,
) -> tuple[ModelVersion, Model, Run]:
    record = session.execute(
        select(ModelVersion, Model, Run)
        .join(Model, Model.id == ModelVersion.model_id)
        .join(Project, Project.id == Model.project_id)
        .join(Run, Run.id == ModelVersion.run_id)
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


def create_acceptance_run(
    session: Session,
    storage: Storage,
    workspace_id: UUID,
    project_id: UUID,
    model_version_id: UUID,
    idempotency_key: str,
    payload: AcceptanceRunCreate,
) -> tuple[Run, bool]:
    project = require_active_project(session, workspace_id, project_id)
    model_version, model, training_run = _require_model_version(
        session, workspace_id, project_id, model_version_id
    )
    acceptance_version = require_dataset_version(
        session, workspace_id, project_id, payload.dataset_version_id
    )
    if acceptance_version.id == training_run.dataset_version_id:
        raise conflict("验收评测必须使用未参与训练的独立数据版本")
    training_version = session.get(DatasetVersion, training_run.dataset_version_id)
    if training_version is None:
        raise conflict("模型的训练数据版本不存在")
    if acceptance_version.class_map != training_version.class_map:
        raise conflict("验收数据的类别定义必须与训练数据完全一致")
    policy = active_policy(session, project_id)
    if policy is None:
        raise conflict("项目尚未配置有效的评测门禁")

    recipe = {
        "model_version_id": str(model_version.id),
        "policy_id": str(policy.id),
        "image_size": payload.image_size,
        "batch_size": payload.batch_size,
    }
    existing = session.scalar(
        select(Run).where(
            Run.project_id == project_id,
            Run.idempotency_key == idempotency_key,
        )
    )
    if existing is not None:
        if (
            existing.run_type != RUN_TYPE
            or existing.dataset_version_id != acceptance_version.id
            or existing.recipe != recipe
        ):
            raise conflict("该幂等键已用于另一个不同的评测请求")
        return existing, True

    completed = session.scalar(
        select(Evaluation.id).where(
            Evaluation.model_version_id == model_version.id,
            Evaluation.policy_id == policy.id,
            Evaluation.source == "acceptance-dataset",
            Evaluation.dataset_version_id == acceptance_version.id,
        )
    )
    if completed is not None:
        raise conflict("该模型已在当前数据版本和门禁下完成验收")

    candidates = session.scalars(
        select(Run).where(
            Run.project_id == project_id,
            Run.run_type == RUN_TYPE,
            Run.dataset_version_id == acceptance_version.id,
            Run.status.in_({"queued", "preparing", "running"}),
        )
    ).all()
    if any(candidate.recipe == recipe for candidate in candidates):
        raise conflict("相同模型、数据版本和门禁已有评测任务在运行")

    run_id = uuid4()
    artifact_prefix = (
        f"workspaces/{workspace_id}/projects/{project_id}/acceptance-runs/{run_id}"
    )
    job_spec = {
        "schema_version": "1.0",
        "run_id": str(run_id),
        "workspace_id": str(workspace_id),
        "project_id": str(project_id),
        "project": {"name": project.name, "task_type": project.task_type},
        "model_version": {
            "id": str(model_version.id),
            "name": model.name,
            "version_number": model_version.version_number,
            "artifact_uri": model_version.artifact_uri,
        },
        "dataset_version": {
            "id": str(acceptance_version.id),
            "manifest_uri": acceptance_version.manifest_uri,
            "asset_count": acceptance_version.asset_count,
        },
        "policy": {
            "id": str(policy.id),
            "name": policy.name,
            "version_number": policy.version_number,
            "rules": policy.rules,
        },
        "engine": "ultralytics",
        "executor": "docker",
        "runtime": {"image": get_settings().ultralytics_docker_image},
        "recipe": recipe,
        "artifact_prefix": artifact_prefix,
        "created_at": datetime.now(UTC).isoformat(),
    }
    spec_uri = storage.put_json(f"{artifact_prefix}/job-spec.json", job_spec)
    run = Run(
        id=run_id,
        project_id=project_id,
        dataset_version_id=acceptance_version.id,
        run_type=RUN_TYPE,
        status="queued",
        engine="ultralytics",
        executor="docker",
        idempotency_key=idempotency_key,
        recipe=recipe,
        progress=0,
        artifact_prefix=artifact_prefix,
        spec_uri=spec_uri,
    )
    session.add(run)
    session.flush()
    append_run_event(
        session,
        run,
        "job.queued",
        {
            "spec_uri": spec_uri,
            "model_version_id": str(model_version.id),
            "dataset_version_id": str(acceptance_version.id),
            "policy_id": str(policy.id),
        },
    )
    return run, False


def list_acceptance_runs(
    session: Session,
    workspace_id: UUID,
    project_id: UUID,
) -> list[Run]:
    require_project(session, workspace_id, project_id)
    return list(
        session.scalars(
            select(Run)
            .where(Run.project_id == project_id, Run.run_type == RUN_TYPE)
            .order_by(Run.created_at.desc())
        ).all()
    )


def complete_acceptance_run(
    session: Session,
    storage: Storage,
    workspace_id: UUID,
    run_id: UUID,
    completion: WorkerAcceptanceCompletion,
) -> tuple[Run, Evaluation, bool]:
    run = require_run(session, workspace_id, run_id, for_update=True)
    if run.run_type != RUN_TYPE:
        raise conflict("该任务不是独立验收评测")
    if run.execution_token != completion.attempt_id:
        raise conflict("执行尝试已失效或不属于当前任务")

    model_version_id = UUID(str(run.recipe["model_version_id"]))
    policy_id = UUID(str(run.recipe["policy_id"]))
    existing = session.scalar(
        select(Evaluation).where(
            Evaluation.model_version_id == model_version_id,
            Evaluation.policy_id == policy_id,
            Evaluation.source == "acceptance-dataset",
            Evaluation.dataset_version_id == run.dataset_version_id,
        )
    )
    if existing is not None:
        return run, existing, True
    if run.status != "running":
        raise conflict(f"无法在 {run.status} 状态登记验收结果")

    model_version = session.get(ModelVersion, model_version_id)
    policy = session.get(EvaluationPolicy, policy_id)
    project = session.get(Project, run.project_id)
    if model_version is None or policy is None or project is None:
        raise conflict("验收任务关联的模型、门禁或项目不存在")

    evaluated_at = completion.occurred_at
    rule_results = evaluate_rules(policy.rules, completion.metrics)
    verdict = "approved" if all(item["passed"] for item in rule_results) else "rejected"
    evaluation_id = uuid4()
    report = {
        "schema_version": "1.0",
        "evaluation_id": str(evaluation_id),
        "source": "acceptance-dataset",
        "workspace_id": str(workspace_id),
        "project_id": str(project.id),
        "run_id": str(run.id),
        "model_version_id": str(model_version.id),
        "dataset_version_id": str(run.dataset_version_id),
        "policy": {
            "id": str(policy.id),
            "name": policy.name,
            "version_number": policy.version_number,
            "rules": policy.rules,
        },
        "runtime": {
            "image": completion.runtime_image,
            "image_size": run.recipe["image_size"],
            "batch_size": run.recipe["batch_size"],
        },
        "evaluated_asset_count": completion.evaluated_asset_count,
        "metrics": completion.metrics,
        "rule_results": rule_results,
        "verdict": verdict,
        "evaluated_at": evaluated_at.isoformat(),
    }
    report_uri = storage.put_json(f"{run.artifact_prefix}/report.json", report)
    evaluation = Evaluation(
        id=evaluation_id,
        model_version_id=model_version.id,
        dataset_version_id=run.dataset_version_id,
        policy_id=policy.id,
        source="acceptance-dataset",
        status="completed",
        verdict=verdict,
        metrics=completion.metrics,
        rule_results=rule_results,
        report_uri=report_uri,
        evaluated_at=evaluated_at,
    )
    session.add(evaluation)
    if policy.is_active:
        model_version.status = verdict
    else:
        current_acceptance = session.scalar(
            select(Evaluation)
            .join(EvaluationPolicy, EvaluationPolicy.id == Evaluation.policy_id)
            .where(
                Evaluation.model_version_id == model_version.id,
                Evaluation.source == "acceptance-dataset",
                EvaluationPolicy.is_active.is_(True),
            )
            .order_by(Evaluation.evaluated_at.desc())
            .limit(1)
        )
        model_version.status = (
            current_acceptance.verdict
            if current_acceptance is not None
            else "candidate"
        )
    run.status = "succeeded"
    run.progress = 100
    run.started_at = run.started_at or evaluated_at
    run.finished_at = evaluated_at
    run.heartbeat_at = evaluated_at
    run.error_code = None
    run.error_message = None
    session.flush()
    append_run_event(
        session,
        run,
        "job.succeeded",
        {
            "evaluation_id": str(evaluation.id),
            "report_uri": report_uri,
            "verdict": verdict,
            "attempt_id": str(completion.attempt_id),
        },
        event_id=completion.event_id,
        occurred_at=evaluated_at,
    )
    return run, evaluation, False
