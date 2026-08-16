from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from sensemu_api.catalog_schemas import (
    VideoExtractionJobCreate,
    VideoExtractionJobResponse,
    VideoExtractionWorkerClaim,
    VideoExtractionWorkerCompletion,
    VideoExtractionWorkerEvent,
    VideoExtractionWorkerHeartbeat,
)
from sensemu_api.catalog_service import conflict, require_dataset, require_dataset_item
from sensemu_api.db.models import (
    Asset,
    Dataset,
    DatasetItem,
    Project,
    VideoExtractionJob,
    VideoExtractionOutput,
)
from sensemu_api.storage import Storage

VIDEO_MEDIA_TYPES = {"video/mp4", "video/quicktime", "video/webm"}
TERMINAL_STATUSES = {"succeeded", "failed", "cancelled"}
ACTIVE_STATUSES = {"queued", "preparing", "running", "cancel_requested"}


def _response(job: VideoExtractionJob) -> VideoExtractionJobResponse:
    return VideoExtractionJobResponse.model_validate(job)


def _job(
    session: Session,
    workspace_id: UUID,
    job_id: UUID,
    *,
    for_update: bool = False,
) -> VideoExtractionJob:
    statement = (
        select(VideoExtractionJob)
        .join(Dataset, Dataset.id == VideoExtractionJob.dataset_id)
        .join(Project, Project.id == Dataset.project_id)
        .where(
            VideoExtractionJob.id == job_id,
            Project.workspace_id == workspace_id,
        )
    )
    if for_update:
        statement = statement.with_for_update()
    record = session.scalar(statement)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="未找到视频抽帧任务")
    return record


def create_job(
    session: Session,
    workspace_id: UUID,
    dataset_id: UUID,
    idempotency_key: str,
    payload: VideoExtractionJobCreate,
) -> tuple[VideoExtractionJobResponse, bool]:
    require_dataset(session, workspace_id, dataset_id)
    source_asset, _item = require_dataset_item(
        session,
        workspace_id,
        dataset_id,
        payload.source_asset_id,
    )
    if source_asset.media_type not in VIDEO_MEDIA_TYPES:
        raise conflict("只能从已导入的视频文件创建抽帧任务")

    existing = session.scalar(
        select(VideoExtractionJob).where(
            VideoExtractionJob.dataset_id == dataset_id,
            VideoExtractionJob.idempotency_key == idempotency_key,
        )
    )
    if existing is not None:
        if (
            existing.source_asset_id != source_asset.id
            or existing.frame_interval_ms != payload.frame_interval_ms
            or existing.deduplicate != payload.deduplicate
        ):
            raise conflict("该幂等键已用于另一个不同的抽帧请求")
        return _response(existing), True

    running = session.scalar(
        select(VideoExtractionJob).where(
            VideoExtractionJob.dataset_id == dataset_id,
            VideoExtractionJob.source_asset_id == source_asset.id,
            VideoExtractionJob.frame_interval_ms == payload.frame_interval_ms,
            VideoExtractionJob.deduplicate == payload.deduplicate,
            VideoExtractionJob.status.in_(ACTIVE_STATUSES),
        )
    )
    if running is not None:
        raise conflict("相同视频和参数的抽帧任务正在执行")

    job_id = uuid4()
    artifact_prefix = f"workspaces/{workspace_id}/datasets/{dataset_id}/video-extractions/{job_id}"
    job = VideoExtractionJob(
        id=job_id,
        dataset_id=dataset_id,
        source_asset_id=source_asset.id,
        idempotency_key=idempotency_key,
        frame_interval_ms=payload.frame_interval_ms,
        deduplicate=payload.deduplicate,
        artifact_prefix=artifact_prefix,
    )
    session.add(job)
    session.flush()
    return _response(job), False


def list_jobs(
    session: Session,
    workspace_id: UUID,
    dataset_id: UUID,
) -> list[VideoExtractionJobResponse]:
    require_dataset(session, workspace_id, dataset_id)
    jobs = session.scalars(
        select(VideoExtractionJob)
        .where(VideoExtractionJob.dataset_id == dataset_id)
        .order_by(VideoExtractionJob.created_at.desc())
    ).all()
    return [_response(job) for job in jobs]


def require_job(
    session: Session,
    workspace_id: UUID,
    job_id: UUID,
) -> VideoExtractionJobResponse:
    return _response(_job(session, workspace_id, job_id))


def cancel_job(session: Session, workspace_id: UUID, job_id: UUID) -> VideoExtractionJobResponse:
    job = _job(session, workspace_id, job_id, for_update=True)
    if job.status in {"cancel_requested", "cancelled"}:
        return _response(job)
    if job.status in TERMINAL_STATUSES:
        raise conflict(f"抽帧任务处于 {job.status} 状态，无法取消")
    now = datetime.now(UTC)
    if job.status == "queued":
        job.status = "cancelled"
        job.finished_at = now
    else:
        job.status = "cancel_requested"
    session.flush()
    return _response(job)


def claim_job(
    session: Session,
    storage: Storage,
    workspace_id: UUID,
    job_id: UUID,
    payload: VideoExtractionWorkerClaim,
) -> tuple[VideoExtractionJobResponse, dict[str, object]]:
    job = _job(session, workspace_id, job_id, for_update=True)
    if job.execution_token == payload.attempt_id and job.status in {
        "preparing",
        "running",
        "cancel_requested",
    }:
        job.heartbeat_at = datetime.now(UTC)
        return _response(job), _job_spec(session, storage, workspace_id, job)
    if job.status != "queued":
        raise conflict(f"抽帧任务已由其他执行尝试领取（{job.status}）")

    now = datetime.now(UTC)
    job.status = "preparing"
    job.execution_token = payload.attempt_id
    job.execution_attempt += 1
    job.claimed_at = now
    job.heartbeat_at = now
    session.flush()
    return _response(job), _job_spec(session, storage, workspace_id, job)


def _job_spec(
    session: Session,
    _storage: Storage,
    workspace_id: UUID,
    job: VideoExtractionJob,
) -> dict[str, object]:
    source_asset, _item = require_dataset_item(
        session,
        workspace_id,
        job.dataset_id,
        job.source_asset_id,
    )
    if not job.artifact_prefix:
        raise conflict("抽帧任务缺少产物目录")
    return {
        "schema_version": "1.0",
        "job_id": str(job.id),
        "workspace_id": str(workspace_id),
        "dataset_id": str(job.dataset_id),
        "source": {
            "asset_id": str(source_asset.id),
            "uri": source_asset.uri,
            "media_type": source_asset.media_type,
        },
        "recipe": {
            "frame_interval_ms": job.frame_interval_ms,
            "deduplicate": job.deduplicate,
        },
        "artifact_prefix": job.artifact_prefix,
    }


def heartbeat_job(
    session: Session,
    workspace_id: UUID,
    job_id: UUID,
    payload: VideoExtractionWorkerHeartbeat,
) -> VideoExtractionJobResponse:
    job = _job(session, workspace_id, job_id, for_update=True)
    _require_attempt(job, payload.attempt_id)
    if job.status not in {"preparing", "running", "cancel_requested"}:
        raise conflict(f"抽帧任务处于 {job.status} 状态，无法续期")
    job.heartbeat_at = datetime.now(UTC)
    session.flush()
    return _response(job)


def recover_stale_jobs(
    session: Session,
    *,
    lease_timeout_seconds: int,
    max_attempts: int,
    now: datetime | None = None,
    limit: int = 100,
) -> list[dict[str, object]]:
    recovered_at = now or datetime.now(UTC)
    cutoff = recovered_at - timedelta(seconds=lease_timeout_seconds)
    stale_lease = or_(
        VideoExtractionJob.heartbeat_at < cutoff,
        and_(
            VideoExtractionJob.heartbeat_at.is_(None),
            VideoExtractionJob.claimed_at < cutoff,
        ),
    )
    statement = (
        select(VideoExtractionJob, Project.workspace_id)
        .join(Dataset, Dataset.id == VideoExtractionJob.dataset_id)
        .join(Project, Project.id == Dataset.project_id)
        .where(
            VideoExtractionJob.status.in_({"preparing", "running", "cancel_requested"}),
            stale_lease,
        )
        .order_by(func.coalesce(VideoExtractionJob.heartbeat_at, VideoExtractionJob.claimed_at), VideoExtractionJob.id)
        .limit(limit)
        .with_for_update(skip_locked=True)
    )
    recovered: list[dict[str, object]] = []
    for job, workspace_id in session.execute(statement):
        previous_status = job.status
        if previous_status == "cancel_requested":
            action = "cancelled"
            job.status = "cancelled"
            job.finished_at = recovered_at
        elif job.execution_attempt >= max_attempts:
            action = "failed"
            job.status = "failed"
            job.error_code = "execution_lease_exhausted"
            job.error_message = "视频抽帧执行器多次失联，已停止自动重试"
            job.finished_at = recovered_at
        else:
            action = "requeued"
            job.status = "queued"
            job.progress = 0
            job.started_at = None
            job.finished_at = None
            job.error_code = None
            job.error_message = None

        job.execution_token = None
        job.claimed_at = None
        job.heartbeat_at = None
        recovered.append(
            {
                "workspace_id": workspace_id,
                "job_id": job.id,
                "action": action,
                "execution_attempt": job.execution_attempt,
            }
        )
    session.flush()
    return recovered


def worker_event(
    session: Session,
    workspace_id: UUID,
    job_id: UUID,
    payload: VideoExtractionWorkerEvent,
) -> VideoExtractionJobResponse:
    job = _job(session, workspace_id, job_id, for_update=True)
    _require_attempt(job, payload.attempt_id)
    now = datetime.now(UTC)
    if payload.event_type == "job.started":
        if job.status not in {"preparing", "running"}:
            raise conflict(f"无法在 {job.status} 状态启动抽帧任务")
        job.status = "running"
        job.started_at = job.started_at or now
    elif payload.event_type == "job.progressed":
        if job.status not in {"preparing", "running"}:
            raise conflict(f"无法在 {job.status} 状态更新抽帧进度")
        job.status = "running"
        job.started_at = job.started_at or now
        job.progress = max(job.progress, payload.progress or 0)
    elif payload.event_type == "job.cancelled":
        job.status = "cancelled"
        job.finished_at = now
    else:
        job.status = "failed"
        job.finished_at = now
        job.error_code = payload.error_code or "extraction_failed"
        job.error_message = payload.error_message or "视频抽帧失败"
    job.heartbeat_at = now
    session.flush()
    return _response(job)


def complete_job(
    session: Session,
    storage: Storage,
    workspace_id: UUID,
    job_id: UUID,
    payload: VideoExtractionWorkerCompletion,
) -> VideoExtractionJobResponse:
    job = _job(session, workspace_id, job_id, for_update=True)
    _require_attempt(job, payload.attempt_id)
    if job.status == "succeeded":
        return _response(job)
    if job.status != "running":
        raise conflict(f"无法在 {job.status} 状态登记抽帧结果")
    if not job.artifact_prefix:
        raise conflict("抽帧任务缺少产物目录")

    prefix = f"{job.artifact_prefix}/frames/"
    seen_checksums: set[str] = set()
    for frame in payload.frames:
        key = _key_for_uri(frame.object_uri)
        if not key.startswith(prefix):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="抽帧产物地址不属于当前任务",
            )
        if frame.checksum_sha256 in seen_checksums:
            continue
        seen_checksums.add(frame.checksum_sha256)
        if not storage.verify_object(key, frame.byte_size, frame.checksum_sha256):
            raise conflict("抽帧产物缺失或校验失败")
        asset = session.scalar(
            select(Asset).where(
                Asset.workspace_id == workspace_id,
                Asset.checksum_sha256 == frame.checksum_sha256,
            )
        )
        if asset is None:
            asset = Asset(
                workspace_id=workspace_id,
                uri=frame.object_uri,
                media_type=frame.media_type,
                checksum_sha256=frame.checksum_sha256,
                byte_size=frame.byte_size,
                width=frame.width,
                height=frame.height,
            )
            session.add(asset)
            session.flush()
        item = session.scalar(
            select(DatasetItem).where(
                DatasetItem.dataset_id == job.dataset_id,
                DatasetItem.asset_id == asset.id,
            )
        )
        if item is None:
            session.add(
                DatasetItem(
                    dataset_id=job.dataset_id,
                    asset_id=asset.id,
                    item_role="training_asset",
                )
            )
        session.add(
            VideoExtractionOutput(
                job_id=job.id,
                asset_id=asset.id,
                frame_index=frame.frame_index,
                timestamp_ms=frame.timestamp_ms,
            )
        )

    now = payload.occurred_at
    job.status = "succeeded"
    job.progress = 100
    job.frames_created = len(seen_checksums)
    job.started_at = job.started_at or now
    job.finished_at = now
    job.heartbeat_at = now
    job.error_code = None
    job.error_message = None
    session.flush()
    return _response(job)


def _require_attempt(job: VideoExtractionJob, attempt_id: UUID) -> None:
    if job.execution_token != attempt_id:
        raise conflict("执行尝试已失效或不属于当前任务")


def _key_for_uri(uri: str) -> str:
    if uri.startswith("local://"):
        return uri.removeprefix("local://")
    if uri.startswith("s3://"):
        parts = uri.split("/", 3)
        return parts[3] if len(parts) == 4 else ""
    return ""
