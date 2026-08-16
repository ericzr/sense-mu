from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from sensemu_api.batch_inference_schemas import (
    BatchInferenceResultResponse,
    BatchInferenceRunCreate,
    BatchInferenceRunResponse,
    WorkerBatchInferenceCompletion,
)
from sensemu_api.catalog_service import conflict, require_active_project, require_project
from sensemu_api.db.models import (
    BatchInferenceResult,
    Deployment,
    Model,
    ModelVersion,
    Project,
    Run,
)
from sensemu_api.storage import Storage
from sensemu_api.training_service import (
    append_run_event,
    require_dataset_version,
    require_run,
)

RUN_TYPE = "inference.batch"
ENGINE = "ultralytics"
EXECUTOR = "runtime"
SUPPORTED_TASK_TYPE = "object-detection"


def _contract_for(task_type: str) -> str:
    if task_type == SUPPORTED_TASK_TYPE:
        return "detections.v1"
    return "predictions.v1"


def _require_batch_deployment(
    session: Session,
    workspace_id: UUID,
    project_id: UUID,
    deployment_id: UUID,
) -> tuple[Deployment, ModelVersion, Model, Project]:
    record = session.execute(
        select(Deployment, ModelVersion, Model, Project)
        .join(ModelVersion, ModelVersion.id == Deployment.model_version_id)
        .join(Model, Model.id == ModelVersion.model_id)
        .join(Project, Project.id == Model.project_id)
        .where(
            Deployment.id == deployment_id,
            Deployment.workspace_id == workspace_id,
            Model.project_id == project_id,
        )
        .with_for_update()
    ).one_or_none()
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="未找到项目内的在线服务")
    deployment, model_version, model, project = record
    if deployment.status != "published":
        raise conflict("批量推理只能使用已发布的在线服务")
    if project.task_type != SUPPORTED_TASK_TYPE:
        raise conflict("首阶段批量推理只支持目标检测服务")
    return deployment, model_version, model, project


def _selected_assets(
    storage: Storage,
    manifest_uri: str,
    source_split: str,
) -> list[dict[str, Any]]:
    try:
        manifest = storage.get_json(manifest_uri)
    except (OSError, ValueError, KeyError) as error:
        raise conflict("无法读取批量推理数据版本的不可变清单") from error
    assets = manifest.get("assets")
    if not isinstance(assets, list):
        raise conflict("批量推理数据版本的不可变清单格式不正确")
    selected = [
        asset
        for asset in assets
        if isinstance(asset, dict)
        and (source_split == "all" or asset.get("split") == source_split)
    ]
    if not selected:
        label = "全部资产" if source_split == "all" else f"{source_split} 划分"
        raise conflict(f"数据版本不包含可用于批量推理的{label}")
    for asset in selected:
        if not isinstance(asset.get("asset_id"), str) or not isinstance(asset.get("uri"), str):
            raise conflict("批量推理数据版本包含不完整的资产引用")
        media_type = asset.get("media_type")
        if not isinstance(media_type, str) or not media_type.startswith("image/"):
            raise conflict("首阶段批量推理只支持图片资产")
    return selected


def _result_response(result: BatchInferenceResult) -> BatchInferenceResultResponse:
    return BatchInferenceResultResponse.model_validate(result)


def _response_for_run(session: Session, run: Run) -> BatchInferenceRunResponse:
    result = session.scalar(select(BatchInferenceResult).where(BatchInferenceResult.run_id == run.id))
    return BatchInferenceRunResponse.model_validate(run).model_copy(
        update={"result": _result_response(result) if result else None}
    )


def create_batch_inference_run(
    session: Session,
    storage: Storage,
    workspace_id: UUID,
    project_id: UUID,
    idempotency_key: str,
    payload: BatchInferenceRunCreate,
) -> tuple[BatchInferenceRunResponse, bool]:
    require_active_project(session, workspace_id, project_id)
    version = require_dataset_version(
        session, workspace_id, project_id, payload.dataset_version_id
    )
    deployment, model_version, _model, project = _require_batch_deployment(
        session, workspace_id, project_id, payload.deployment_id
    )
    selected_assets = _selected_assets(storage, version.manifest_uri, payload.source_split)
    recipe = {
        "deployment_id": str(deployment.id),
        "source_split": payload.source_split,
        "parameters": payload.parameters.model_dump(mode="json"),
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
            or existing.dataset_version_id != version.id
            or existing.recipe != recipe
        ):
            raise conflict("该幂等键已用于另一个不同的批量推理请求")
        return _response_for_run(session, existing), True

    active_runs = session.scalars(
        select(Run).where(
            Run.project_id == project_id,
            Run.run_type == RUN_TYPE,
            Run.dataset_version_id == version.id,
            Run.status.in_({"queued", "preparing", "running", "cancel_requested"}),
        )
    ).all()
    if any(run.recipe == recipe for run in active_runs):
        raise conflict("相同服务、数据版本与参数的批量推理任务正在执行")

    run_id = uuid4()
    artifact_prefix = (
        f"workspaces/{workspace_id}/projects/{project_id}/batch-inference-runs/{run_id}"
    )
    job_spec = {
        "schema_version": "1.0",
        "run_id": str(run_id),
        "workspace_id": str(workspace_id),
        "project_id": str(project_id),
        "project": {"name": project.name, "task_type": project.task_type},
        "deployment": {
            "id": str(deployment.id),
            "model_version_id": str(model_version.id),
            "artifact_uri": model_version.artifact_uri,
            "task_type": project.task_type,
            "contract": _contract_for(project.task_type),
        },
        "dataset_version": {
            "id": str(version.id),
            "manifest_uri": version.manifest_uri,
            "asset_count": version.asset_count,
            "selected_asset_count": len(selected_assets),
        },
        "engine": ENGINE,
        "executor": EXECUTOR,
        "recipe": recipe,
        "artifact_prefix": artifact_prefix,
        "created_at": datetime.now(UTC).isoformat(),
    }
    spec_uri = storage.put_json(f"{artifact_prefix}/job-spec.json", job_spec)
    run = Run(
        id=run_id,
        project_id=project_id,
        dataset_version_id=version.id,
        run_type=RUN_TYPE,
        status="queued",
        engine=ENGINE,
        executor=EXECUTOR,
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
            "deployment_id": str(deployment.id),
            "dataset_version_id": str(version.id),
            "selected_asset_count": len(selected_assets),
        },
    )
    return _response_for_run(session, run), False


def list_batch_inference_runs(
    session: Session,
    workspace_id: UUID,
    project_id: UUID,
) -> list[BatchInferenceRunResponse]:
    require_project(session, workspace_id, project_id)
    runs = session.scalars(
        select(Run)
        .where(Run.project_id == project_id, Run.run_type == RUN_TYPE)
        .order_by(Run.created_at.desc())
    ).all()
    return [_response_for_run(session, run) for run in runs]


def complete_batch_inference_run(
    session: Session,
    workspace_id: UUID,
    run_id: UUID,
    completion: WorkerBatchInferenceCompletion,
) -> tuple[BatchInferenceRunResponse, bool]:
    run = require_run(session, workspace_id, run_id, for_update=True)
    if run.run_type != RUN_TYPE:
        raise conflict("该任务不是批量推理")
    if run.execution_token != completion.attempt_id:
        raise conflict("执行尝试已失效或不属于当前任务")
    existing = session.scalar(select(BatchInferenceResult).where(BatchInferenceResult.run_id == run.id))
    if existing is not None:
        return _response_for_run(session, run), True
    if run.status != "running":
        raise conflict(f"无法在 {run.status} 状态登记批量推理结果")
    if not run.artifact_prefix:
        raise conflict("批量推理任务缺少产物目录")
    prefix = f"{run.artifact_prefix}/"
    for uri in (completion.output_uri, completion.report_uri):
        key = uri.removeprefix("local://") if uri.startswith("local://") else uri.split("/", 3)[-1]
        if not key.startswith(prefix):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="批量推理产物地址不属于当前任务",
            )
    deployment_id = UUID(str(run.recipe["deployment_id"]))
    summary = {
        "source_split": run.recipe["source_split"],
        "parameters": run.recipe["parameters"],
        "processed_asset_count": completion.processed_asset_count,
        "prediction_count": completion.prediction_count,
        "runtime": completion.runtime,
        "format": "ndjson",
    }
    result = BatchInferenceResult(
        run_id=run.id,
        deployment_id=deployment_id,
        output_uri=completion.output_uri,
        report_uri=completion.report_uri,
        summary=summary,
        completed_at=completion.occurred_at,
    )
    session.add(result)
    run.status = "succeeded"
    run.progress = 100
    run.started_at = run.started_at or completion.occurred_at
    run.finished_at = completion.occurred_at
    run.heartbeat_at = completion.occurred_at
    run.error_code = None
    run.error_message = None
    session.flush()
    append_run_event(
        session,
        run,
        "job.succeeded",
        {
            "result_id": str(result.id),
            "output_uri": result.output_uri,
            "report_uri": result.report_uri,
            "processed_asset_count": completion.processed_asset_count,
            "prediction_count": completion.prediction_count,
            "attempt_id": str(completion.attempt_id),
        },
        event_id=completion.event_id,
        occurred_at=completion.occurred_at,
    )
    return _response_for_run(session, run), False


def get_batch_inference_output(
    session: Session,
    storage: Storage,
    workspace_id: UUID,
    run_id: UUID,
) -> bytes:
    run = require_run(session, workspace_id, run_id)
    if run.run_type != RUN_TYPE:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="未找到批量推理任务")
    result = session.scalar(select(BatchInferenceResult).where(BatchInferenceResult.run_id == run.id))
    if result is None:
        raise conflict("批量推理结果尚未生成")
    try:
        return storage.get_bytes(result.output_uri)
    except (OSError, ValueError, KeyError) as error:
        raise conflict("无法读取批量推理结果产物") from error
