import csv
import io
import json
from datetime import UTC, datetime, timedelta
from math import isfinite
from typing import Any
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from sensemu_api.catalog_service import conflict, require_active_project, require_project
from sensemu_api.config import get_settings
from sensemu_api.db.models import (
    Dataset,
    DatasetVersion,
    Model,
    ModelVersion,
    Project,
    Run,
    RunEvent,
)
from sensemu_api.evaluation_service import evaluate_model_version
from sensemu_api.storage import Storage
from sensemu_api.training_engine import get_engine_adapter, list_engine_descriptors
from sensemu_api.training_schemas import (
    ModelVersionResponse,
    TrainingClassMetric,
    TrainingClassMetricsResponse,
    TrainingEngineResponse,
    TrainingReportResponse,
    TrainingReportRow,
    TrainingRunCreate,
    WorkerExecutionClaim,
    WorkerExecutionHeartbeat,
    WorkerRunCompletion,
    WorkerRunEventCreate,
)

TERMINAL_RUN_STATUSES = {"succeeded", "failed", "cancelled"}
SUPPORTED_EXECUTORS = {"docker"}
MAX_TRAINING_REPORT_BYTES = 1_000_000
MAX_TRAINING_REPORT_ROWS = 2_000
MAX_TRAINING_VISUALIZATION_BYTES = 10_000_000
MAX_TRAINING_CLASS_METRICS_BYTES = 500_000
TRAINING_VISUALIZATION_ARTIFACTS = {
    "confusion_matrix": "metrics/confusion_matrix.png",
    "confusion_matrix_normalized": "metrics/confusion_matrix_normalized.png",
}
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def unprocessable(message: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=message)


def require_dataset_version(
    session: Session,
    workspace_id: UUID,
    project_id: UUID,
    version_id: UUID,
) -> DatasetVersion:
    version = session.scalar(
        select(DatasetVersion)
        .join(Dataset, Dataset.id == DatasetVersion.dataset_id)
        .join(Project, Project.id == Dataset.project_id)
        .where(
            DatasetVersion.id == version_id,
            Dataset.project_id == project_id,
            Project.workspace_id == workspace_id,
        )
    )
    if version is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="未找到数据集版本")
    if version.status != "frozen":
        raise conflict("训练任务必须使用已冻结的不可变数据集版本")
    return version


def append_run_event(
    session: Session,
    run: Run,
    event_type: str,
    payload: dict[str, Any] | None = None,
    *,
    event_id: UUID | None = None,
    occurred_at: datetime | None = None,
) -> RunEvent:
    current_sequence = session.scalar(
        select(func.max(RunEvent.sequence)).where(RunEvent.run_id == run.id)
    )
    event = RunEvent(
        run_id=run.id,
        event_id=event_id or uuid4(),
        sequence=(current_sequence or 0) + 1,
        event_type=event_type,
        status=run.status,
        progress=run.progress,
        payload=payload or {},
        **({"occurred_at": occurred_at} if occurred_at else {}),
    )
    session.add(event)
    session.flush()
    return event


def create_training_run(
    session: Session,
    storage: Storage,
    workspace_id: UUID,
    project_id: UUID,
    idempotency_key: str,
    payload: TrainingRunCreate,
) -> tuple[Run, bool]:
    project = require_active_project(session, workspace_id, project_id)
    version = require_dataset_version(
        session,
        workspace_id,
        project_id,
        payload.dataset_version_id,
    )
    if project.task_type == "object-detection":
        try:
            manifest = storage.get_json(version.manifest_uri)
        except (OSError, ValueError, KeyError) as error:
            raise conflict("无法读取训练数据版本的不可变清单") from error
        assets = manifest.get("assets")
        if not isinstance(assets, list):
            raise conflict("训练数据版本的不可变清单格式不正确")
        splits = {
            "valid" if asset.get("split") == "val" else asset.get("split")
            for asset in assets
            if isinstance(asset, dict)
        }
        if "train" not in splits or "valid" not in splits:
            raise conflict("训练任务必须使用同时包含训练集和验证集的数据版本")
    try:
        adapter = get_engine_adapter(payload.engine)
        canonical_recipe = adapter.validate_recipe(payload.recipe)
    except ValueError as error:
        raise unprocessable(str(error)) from error
    if payload.executor not in SUPPORTED_EXECUTORS:
        raise unprocessable(f"不支持的执行器：{payload.executor}")
    if project.task_type not in adapter.descriptor.task_types:
        raise unprocessable(
            f"训练引擎 {payload.engine} 不支持项目任务类型 {project.task_type}"
        )

    existing = session.scalar(
        select(Run).where(
            Run.project_id == project_id,
            Run.idempotency_key == idempotency_key,
        )
    )
    if existing is not None:
        same_request = (
            existing.dataset_version_id == payload.dataset_version_id
            and existing.engine == payload.engine
            and existing.executor == payload.executor
            and existing.recipe == canonical_recipe
        )
        if not same_request:
            raise conflict("该幂等键已用于另一个不同的训练请求")
        return existing, True

    run_id = uuid4()
    artifact_prefix = f"workspaces/{workspace_id}/projects/{project_id}/runs/{run_id}"
    job_spec = {
        "schema_version": "1.0",
        "run_id": str(run_id),
        "workspace_id": str(workspace_id),
        "project_id": str(project_id),
        "project": {
            "name": project.name,
            "task_type": project.task_type,
        },
        "dataset_version": {
            "id": str(version.id),
            "manifest_uri": version.manifest_uri,
            "asset_count": version.asset_count,
        },
        "engine": payload.engine,
        "executor": payload.executor,
        "runtime": {"image": get_settings().ultralytics_docker_image},
        "recipe": canonical_recipe,
        "artifact_prefix": artifact_prefix,
        "created_at": datetime.now(UTC).isoformat(),
    }
    spec_uri = storage.put_json(f"{artifact_prefix}/job-spec.json", job_spec)
    run = Run(
        id=run_id,
        project_id=project_id,
        dataset_version_id=version.id,
        run_type="model.train",
        status="queued",
        engine=payload.engine,
        executor=payload.executor,
        idempotency_key=idempotency_key,
        recipe=canonical_recipe,
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
        {"spec_uri": spec_uri, "dataset_version_id": str(version.id)},
    )
    return run, False


def list_training_runs(
    session: Session,
    workspace_id: UUID,
    project_id: UUID,
) -> list[Run]:
    require_project(session, workspace_id, project_id)
    statement = (
        select(Run)
        .where(Run.project_id == project_id, Run.run_type == "model.train")
        .order_by(Run.created_at.desc())
    )
    return list(session.scalars(statement).all())


def require_run(
    session: Session,
    workspace_id: UUID,
    run_id: UUID,
    *,
    for_update: bool = False,
) -> Run:
    statement = (
        select(Run)
        .join(Project, Project.id == Run.project_id)
        .where(Run.id == run_id, Project.workspace_id == workspace_id)
    )
    if for_update:
        statement = statement.with_for_update()
    run = session.scalar(statement)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="未找到训练任务")
    return run


def list_run_events(
    session: Session,
    workspace_id: UUID,
    run_id: UUID,
) -> list[RunEvent]:
    require_run(session, workspace_id, run_id)
    return list(
        session.scalars(
            select(RunEvent)
            .where(RunEvent.run_id == run_id)
            .order_by(RunEvent.sequence)
        ).all()
    )


def get_training_report(
    session: Session,
    storage: Storage,
    workspace_id: UUID,
    run_id: UUID,
) -> TrainingReportResponse:
    run = require_run(session, workspace_id, run_id)
    if run.status != "succeeded" or not run.artifact_prefix:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="训练报告尚不可用")

    report_uri = storage.uri_for(f"{run.artifact_prefix}/metrics/results.csv")
    try:
        payload = storage.get_bytes(report_uri)
    except (FileNotFoundError, KeyError, OSError, ValueError) as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="训练报告尚不可用") from error
    if len(payload) > MAX_TRAINING_REPORT_BYTES:
        raise unprocessable("训练报告过大，暂不支持在页面中读取")

    try:
        reader = csv.DictReader(io.StringIO(payload.decode("utf-8-sig")))
        rows: list[TrainingReportRow] = []
        for index, raw_row in enumerate(reader):
            if index >= MAX_TRAINING_REPORT_ROWS:
                raise unprocessable("训练报告行数过多，暂不支持在页面中读取")
            epoch_raw = (raw_row.get("epoch") or "").strip()
            try:
                epoch_number = float(epoch_raw)
                if not isfinite(epoch_number) or epoch_number < 0:
                    raise ValueError
                epoch = int(epoch_number)
            except (OverflowError, ValueError):
                epoch = index

            metrics: dict[str, float] = {}
            for key, value in raw_row.items():
                normalized_key = str(key or "").strip()
                if not normalized_key or normalized_key in {"epoch", "time"} or value is None:
                    continue
                try:
                    number = float(value.strip())
                except (AttributeError, ValueError):
                    continue
                if isfinite(number):
                    metrics[normalized_key] = number
            if metrics:
                rows.append(TrainingReportRow(epoch=epoch, metrics=metrics))
    except (UnicodeDecodeError, csv.Error) as error:
        raise unprocessable("训练报告格式无效") from error

    if not rows:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="训练报告尚不可用")
    return TrainingReportResponse(run_id=run.id, rows=rows)


def get_training_visualization(
    session: Session,
    storage: Storage,
    workspace_id: UUID,
    run_id: UUID,
    visualization: str,
) -> bytes:
    """Return one allow-listed visualization from a completed training run.

    Visualization files stay behind the same workspace authorization boundary as
    the report.  Object-store paths are intentionally never returned to clients.
    """

    artifact_suffix = TRAINING_VISUALIZATION_ARTIFACTS.get(visualization)
    if artifact_suffix is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="训练评估图尚不可用")

    run = require_run(session, workspace_id, run_id)
    if run.status != "succeeded" or not run.artifact_prefix:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="训练评估图尚不可用")

    artifact_uri = storage.uri_for(f"{run.artifact_prefix}/{artifact_suffix}")
    try:
        payload = storage.get_bytes(artifact_uri)
    except (FileNotFoundError, KeyError, OSError, ValueError) as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="训练评估图尚不可用",
        ) from error

    if len(payload) > MAX_TRAINING_VISUALIZATION_BYTES:
        raise unprocessable("训练评估图过大，暂不支持在页面中读取")
    if not payload.startswith(PNG_SIGNATURE):
        raise unprocessable("训练评估图格式无效")
    return payload


def get_training_class_metrics(
    session: Session,
    storage: Storage,
    workspace_id: UUID,
    run_id: UUID,
) -> TrainingClassMetricsResponse:
    run = require_run(session, workspace_id, run_id)
    if run.status != "succeeded" or not run.artifact_prefix:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="类别指标尚不可用")

    report_uri = storage.uri_for(f"{run.artifact_prefix}/metrics/class_metrics.json")
    try:
        raw_payload = storage.get_bytes(report_uri)
    except (FileNotFoundError, KeyError, OSError, ValueError) as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="类别指标尚不可用") from error
    if len(raw_payload) > MAX_TRAINING_CLASS_METRICS_BYTES:
        raise unprocessable("类别指标报告过大，暂不支持在页面中读取")
    try:
        payload = json.loads(raw_payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise unprocessable("类别指标报告格式无效") from error
    raw_classes = payload.get("classes") if isinstance(payload, dict) else None
    if not isinstance(raw_classes, list):
        raise unprocessable("类别指标报告格式无效")

    def metric_value(raw_value: Any) -> float | None:
        if raw_value is None:
            return None
        if isinstance(raw_value, bool):
            raise TypeError
        value = float(raw_value)
        if not isfinite(value):
            raise ValueError
        return value

    classes: list[TrainingClassMetric] = []
    try:
        for raw_class in raw_classes:
            if not isinstance(raw_class, dict):
                raise TypeError
            class_id = raw_class.get("id")
            name = raw_class.get("name")
            if isinstance(class_id, bool) or not isinstance(name, str) or not name.strip():
                raise ValueError
            classes.append(
                TrainingClassMetric(
                    class_id=int(class_id),
                    name=name.strip(),
                    precision=metric_value(raw_class.get("precision")),
                    recall=metric_value(raw_class.get("recall")),
                    map50=metric_value(raw_class.get("map50")),
                    map50_95=metric_value(raw_class.get("map50_95")),
                )
            )
    except (OverflowError, TypeError, ValueError) as error:
        raise unprocessable("类别指标报告格式无效") from error

    if not classes:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="类别指标尚不可用")
    return TrainingClassMetricsResponse(run_id=run.id, classes=classes)


def cancel_training_run(session: Session, workspace_id: UUID, run_id: UUID) -> Run:
    run = require_run(session, workspace_id, run_id, for_update=True)
    if run.status in {"cancel_requested", "cancelled"}:
        return run
    if run.status in TERMINAL_RUN_STATUSES:
        raise conflict(f"训练任务处于 {run.status} 状态，无法取消")
    if run.status == "queued":
        run.status = "cancelled"
        run.finished_at = datetime.now(UTC)
        append_run_event(session, run, "job.cancelled")
        return run
    run.status = "cancel_requested"
    append_run_event(session, run, "job.cancel_requested")
    return run


def claim_worker_execution(
    session: Session,
    storage: Storage,
    workspace_id: UUID,
    run_id: UUID,
    claim: WorkerExecutionClaim,
) -> tuple[Run, dict[str, Any]]:
    run = require_run(session, workspace_id, run_id, for_update=True)
    if run.execution_token == claim.attempt_id and run.status in {
        "preparing",
        "running",
        "cancel_requested",
    }:
        if run.spec_uri is None:
            raise conflict("训练任务缺少不可变任务规格")
        run.heartbeat_at = datetime.now(UTC)
        return run, storage.get_json(run.spec_uri)
    if run.status != "queued":
        raise conflict(f"训练任务已由其他执行尝试领取（{run.status}）")
    if run.spec_uri is None:
        raise conflict("训练任务缺少不可变任务规格")
    try:
        job_spec = storage.get_json(run.spec_uri)
    except (OSError, ValueError) as error:
        raise conflict("无法读取训练任务规格") from error
    now = datetime.now(UTC)
    run.status = "preparing"
    run.execution_token = claim.attempt_id
    run.execution_attempt += 1
    run.claimed_at = now
    run.heartbeat_at = now
    append_run_event(
        session,
        run,
        "job.preparing",
        {
            "attempt_id": str(claim.attempt_id),
            "worker_id": claim.worker_id,
            "attempt": run.execution_attempt,
        },
    )
    return run, job_spec


def _require_execution_attempt(run: Run, attempt_id: UUID) -> None:
    if run.execution_token != attempt_id:
        raise conflict("执行尝试已失效或不属于当前任务")


def heartbeat_worker_execution(
    session: Session,
    workspace_id: UUID,
    run_id: UUID,
    heartbeat: WorkerExecutionHeartbeat,
) -> Run:
    run = require_run(session, workspace_id, run_id, for_update=True)
    _require_execution_attempt(run, heartbeat.attempt_id)
    if run.status not in {"preparing", "running", "cancel_requested"}:
        raise conflict(f"训练任务处于 {run.status} 状态，无法续期执行租约")
    run.heartbeat_at = datetime.now(UTC)
    session.flush()
    return run


def recover_stale_executions(
    session: Session,
    *,
    lease_timeout_seconds: int,
    max_attempts: int,
    now: datetime | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    recovered_at = now or datetime.now(UTC)
    cutoff = recovered_at - timedelta(seconds=lease_timeout_seconds)
    stale_lease = or_(
        Run.heartbeat_at < cutoff,
        and_(Run.heartbeat_at.is_(None), Run.claimed_at < cutoff),
    )
    statement = (
        select(Run, Project.workspace_id)
        .join(Project, Project.id == Run.project_id)
        .where(
            Run.status.in_({"preparing", "running", "cancel_requested"}),
            stale_lease,
        )
        .order_by(func.coalesce(Run.heartbeat_at, Run.claimed_at), Run.id)
        .limit(limit)
        .with_for_update(skip_locked=True)
    )
    recovered: list[dict[str, Any]] = []
    for run, workspace_id in session.execute(statement):
        previous_status = run.status
        previous_attempt_id = run.execution_token
        last_heartbeat_at = run.heartbeat_at or run.claimed_at
        event_payload = {
            "previous_status": previous_status,
            "previous_attempt_id": str(previous_attempt_id) if previous_attempt_id else None,
            "last_heartbeat_at": (
                last_heartbeat_at.isoformat() if last_heartbeat_at else None
            ),
            "lease_timeout_seconds": lease_timeout_seconds,
            "execution_attempt": run.execution_attempt,
        }

        if previous_status == "cancel_requested":
            action = "cancelled"
            run.status = "cancelled"
            run.finished_at = recovered_at
            append_run_event(
                session,
                run,
                "job.cancelled",
                {**event_payload, "reason": "execution_lease_expired"},
                occurred_at=recovered_at,
            )
        elif run.execution_attempt >= max_attempts:
            action = "failed"
            run.status = "failed"
            run.error_code = "execution_lease_exhausted"
            run.error_message = "训练执行器多次失联，已停止自动重试"
            run.finished_at = recovered_at
            append_run_event(
                session,
                run,
                "job.failed",
                {
                    **event_payload,
                    "error_code": run.error_code,
                    "error_message": run.error_message,
                },
                occurred_at=recovered_at,
            )
        else:
            action = "requeued"
            run.status = "queued"
            run.progress = 0
            run.started_at = None
            run.finished_at = None
            run.error_code = None
            run.error_message = None
            append_run_event(
                session,
                run,
                "job.lease_expired",
                {**event_payload, "action": "requeued"},
                occurred_at=recovered_at,
            )

        run.execution_token = None
        run.claimed_at = None
        run.heartbeat_at = None
        recovered.append(
            {
                "workspace_id": workspace_id,
                "run_id": run.id,
                "run_type": run.run_type,
                "action": action,
                "execution_attempt": run.execution_attempt,
            }
        )
    session.flush()
    return recovered


def apply_worker_event(
    session: Session,
    workspace_id: UUID,
    run_id: UUID,
    event: WorkerRunEventCreate,
) -> tuple[Run, bool]:
    run = require_run(session, workspace_id, run_id, for_update=True)
    _require_execution_attempt(run, event.attempt_id)
    existing = session.scalar(
        select(RunEvent).where(
            RunEvent.run_id == run.id,
            RunEvent.event_id == event.event_id,
        )
    )
    if existing is not None:
        return run, True
    if run.status in TERMINAL_RUN_STATUSES:
        raise conflict(f"训练任务已处于终态 {run.status}")

    now = event.occurred_at
    run.heartbeat_at = now
    if event.event_type == "job.started":
        if run.status not in {"queued", "preparing", "running"}:
            raise conflict(f"无法从 {run.status} 状态开始训练")
        run.status = "running"
        run.started_at = run.started_at or now
    elif event.event_type == "job.progressed":
        if run.status != "running":
            raise conflict(f"无法在 {run.status} 状态更新训练进度")
        if event.progress is None:
            raise unprocessable("进度事件必须包含 progress")
        if event.progress < run.progress:
            raise conflict("训练进度不能回退")
        run.progress = event.progress
    elif event.event_type == "job.failed":
        run.status = "failed"
        run.error_code = event.error_code or "executor_failed"
        run.error_message = event.error_message or "训练执行失败"
        run.finished_at = now
    elif event.event_type == "job.cancelled":
        run.status = "cancelled"
        run.finished_at = now

    event_payload = dict(event.payload)
    event_payload["attempt_id"] = str(event.attempt_id)
    if event.error_code:
        event_payload["error_code"] = event.error_code
    if event.error_message:
        event_payload["error_message"] = event.error_message
    append_run_event(
        session,
        run,
        event.event_type,
        event_payload,
        event_id=event.event_id,
        occurred_at=event.occurred_at,
    )
    return run, False


def _artifact_key(uri: str) -> str:
    if uri.startswith("local://"):
        return uri.removeprefix("local://")
    if uri.startswith("s3://"):
        _, _, remainder = uri.partition("s3://")
        _, separator, key = remainder.partition("/")
        if separator:
            return key
    return ""


def complete_training_run(
    session: Session,
    storage: Storage,
    workspace_id: UUID,
    run_id: UUID,
    completion: WorkerRunCompletion,
) -> tuple[Run, ModelVersion, bool]:
    run = require_run(session, workspace_id, run_id, for_update=True)
    _require_execution_attempt(run, completion.attempt_id)
    existing_version = session.scalar(
        select(ModelVersion).where(ModelVersion.run_id == run.id)
    )
    if existing_version is not None:
        return run, existing_version, True
    if run.status != "running":
        raise conflict(f"无法在 {run.status} 状态登记模型产物")
    if not run.artifact_prefix or not _artifact_key(completion.artifact_uri).startswith(
        f"{run.artifact_prefix}/"
    ):
        raise unprocessable("模型产物地址不属于当前训练任务")

    project = session.get(Project, run.project_id)
    if project is None:
        raise conflict("训练任务所属项目不存在")
    model = session.scalar(
        select(Model)
        .where(Model.project_id == project.id, Model.name == completion.model_name)
        .with_for_update()
    )
    if model is None:
        model = Model(
            project_id=project.id,
            name=completion.model_name,
            task_type=project.task_type,
        )
        session.add(model)
        session.flush()
    next_version = (
        session.scalar(
            select(func.max(ModelVersion.version_number)).where(
                ModelVersion.model_id == model.id
            )
        )
        or 0
    ) + 1
    model_version = ModelVersion(
        model_id=model.id,
        run_id=run.id,
        version_number=next_version,
        status="candidate",
        artifact_uri=completion.artifact_uri,
        metrics=completion.metrics,
    )
    session.add(model_version)
    session.flush()

    run.status = "succeeded"
    run.progress = 100
    run.started_at = run.started_at or completion.occurred_at
    run.finished_at = completion.occurred_at
    run.heartbeat_at = completion.occurred_at
    run.error_code = None
    run.error_message = None
    append_run_event(
        session,
        run,
        "job.succeeded",
        {
            "model_version_id": str(model_version.id),
            "artifact_uri": completion.artifact_uri,
            "attempt_id": str(completion.attempt_id),
        },
        event_id=completion.event_id,
        occurred_at=completion.occurred_at,
    )
    evaluate_model_version(
        session,
        storage,
        workspace_id,
        model_version,
        project.id,
        run.dataset_version_id,
    )
    return run, model_version, False


def list_model_versions(
    session: Session,
    workspace_id: UUID,
    project_id: UUID,
) -> list[ModelVersionResponse]:
    require_project(session, workspace_id, project_id)
    statement = (
        select(ModelVersion, Model)
        .join(Model, Model.id == ModelVersion.model_id)
        .where(Model.project_id == project_id)
        .order_by(ModelVersion.created_at.desc())
    )
    return [
        ModelVersionResponse(
            id=version.id,
            model_id=version.model_id,
            model_name=model.name,
            run_id=version.run_id,
            version_number=version.version_number,
            status=version.status,
            artifact_uri=version.artifact_uri,
            metrics=version.metrics,
            created_at=version.created_at,
        )
        for version, model in session.execute(statement)
    ]


def training_engines() -> list[TrainingEngineResponse]:
    return [
        TrainingEngineResponse(**descriptor.model_dump())
        for descriptor in list_engine_descriptors()
    ]
