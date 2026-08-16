from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Header, Response, status
from sqlalchemy.orm import Session

from sensemu_api import annotation_service, catalog_service, video_extraction_service
from sensemu_api.catalog_schemas import (
    AnnotationRegister,
    AnnotationTaskCreate,
    AnnotationTaskFromVideoExtractionCreate,
    AnnotationTaskResponse,
    AnnotationTaskStatusUpdate,
    AnnotationTaskYoloImport,
    AnnotationTaskYoloImportResponse,
    AnnotationTaskYoloImportUploadIntentCreate,
    AnnotationUploadIntentCreate,
    AssetRegister,
    AssetResponse,
    DatasetClassMapUpdate,
    DatasetCreate,
    DatasetItemUpdate,
    DatasetResponse,
    DatasetVersionQualityReport,
    DatasetVersionResponse,
    FreezeDatasetVersion,
    ProjectCreate,
    ProjectResponse,
    SourceAssetResponse,
    UploadIntentCreate,
    UploadIntentResponse,
    VideoExtractionJobCreate,
    VideoExtractionJobResponse,
    VideoExtractionRecoveryResponse,
    VideoExtractionWorkerClaim,
    VideoExtractionWorkerCompletion,
    VideoExtractionWorkerEvent,
    VideoExtractionWorkerHeartbeat,
    WorkspaceCreate,
    WorkspaceResponse,
)
from sensemu_api.config import get_settings
from sensemu_api.db.session import get_session
from sensemu_api.dependencies import CurrentUser, WorkspaceId
from sensemu_api.storage import Storage, get_storage
from sensemu_api.video_extraction_dispatch import VideoExtractionDispatcherDep
from sensemu_api.worker_auth import WorkerAuth

router = APIRouter(prefix="/api/v1", tags=["catalog"])
SessionDep = Annotated[Session, Depends(get_session)]
StorageDep = Annotated[Storage, Depends(get_storage)]
IdempotencyKey = Annotated[
    str,
    Header(alias="Idempotency-Key", min_length=8, max_length=120),
]


@router.post(
    "/workspaces",
    response_model=WorkspaceResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_workspace(
    payload: WorkspaceCreate,
    current_user: CurrentUser,
    session: SessionDep,
) -> WorkspaceResponse:
    workspace, membership = catalog_service.create_workspace(
        session, payload, current_user
    )
    return WorkspaceResponse.model_validate(workspace).model_copy(
        update={"role": membership.role}
    )


@router.get("/workspaces", response_model=list[WorkspaceResponse])
def list_workspaces(
    current_user: CurrentUser,
    session: SessionDep,
) -> list[WorkspaceResponse]:
    return [
        WorkspaceResponse.model_validate(workspace).model_copy(
            update={"role": membership.role}
        )
        for workspace, membership in catalog_service.list_workspaces(
            session, current_user.id
        )
    ]


@router.post(
    "/projects",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_project(
    payload: ProjectCreate,
    workspace_id: WorkspaceId,
    session: SessionDep,
) -> ProjectResponse:
    project = catalog_service.create_project(session, workspace_id, payload)
    return ProjectResponse.model_validate(project)


@router.get("/projects", response_model=list[ProjectResponse])
def list_projects(workspace_id: WorkspaceId, session: SessionDep) -> list[ProjectResponse]:
    return [
        ProjectResponse.model_validate(project)
        for project in catalog_service.list_projects(session, workspace_id)
    ]


@router.post("/projects/{project_id}:pause", response_model=ProjectResponse)
def pause_project(
    project_id: UUID,
    workspace_id: WorkspaceId,
    session: SessionDep,
) -> ProjectResponse:
    return ProjectResponse.model_validate(
        catalog_service.pause_project(session, workspace_id, project_id)
    )


@router.post("/projects/{project_id}:resume", response_model=ProjectResponse)
def resume_project(
    project_id: UUID,
    workspace_id: WorkspaceId,
    session: SessionDep,
) -> ProjectResponse:
    return ProjectResponse.model_validate(
        catalog_service.resume_project(session, workspace_id, project_id)
    )


@router.post("/projects/{project_id}:archive", response_model=ProjectResponse)
def archive_project(
    project_id: UUID,
    workspace_id: WorkspaceId,
    session: SessionDep,
) -> ProjectResponse:
    return ProjectResponse.model_validate(
        catalog_service.archive_project(session, workspace_id, project_id)
    )


@router.post(
    "/projects/{project_id}/datasets",
    response_model=DatasetResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_dataset(
    project_id: UUID,
    payload: DatasetCreate,
    workspace_id: WorkspaceId,
    session: SessionDep,
) -> DatasetResponse:
    dataset = catalog_service.create_dataset(session, workspace_id, project_id, payload)
    return DatasetResponse.model_validate(dataset)


@router.get(
    "/projects/{project_id}/datasets",
    response_model=list[DatasetResponse],
)
def list_datasets(
    project_id: UUID,
    workspace_id: WorkspaceId,
    session: SessionDep,
) -> list[DatasetResponse]:
    return catalog_service.list_datasets(session, workspace_id, project_id)


@router.patch("/datasets/{dataset_id}/classes", response_model=DatasetResponse)
def update_dataset_class_map(
    dataset_id: UUID,
    payload: DatasetClassMapUpdate,
    workspace_id: WorkspaceId,
    session: SessionDep,
) -> DatasetResponse:
    return DatasetResponse.model_validate(
        catalog_service.update_dataset_class_map(
            session,
            workspace_id,
            dataset_id,
            payload,
        )
    )


@router.delete("/datasets/{dataset_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_dataset(
    dataset_id: UUID,
    workspace_id: WorkspaceId,
    session: SessionDep,
) -> Response:
    catalog_service.delete_dataset(session, workspace_id, dataset_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/datasets/{dataset_id}/uploads",
    response_model=UploadIntentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_upload_intent(
    dataset_id: UUID,
    payload: UploadIntentCreate,
    workspace_id: WorkspaceId,
    session: SessionDep,
    storage: StorageDep,
) -> UploadIntentResponse:
    return catalog_service.create_upload_intent(
        session,
        storage,
        workspace_id,
        dataset_id,
        payload,
    )


@router.post(
    "/datasets/{dataset_id}/assets",
    response_model=AssetResponse,
    status_code=status.HTTP_201_CREATED,
)
def register_asset(
    dataset_id: UUID,
    payload: AssetRegister,
    workspace_id: WorkspaceId,
    session: SessionDep,
    storage: StorageDep,
) -> AssetResponse:
    asset, item, reused = catalog_service.register_asset(
        session,
        storage,
        workspace_id,
        dataset_id,
        payload,
    )
    return AssetResponse.model_validate(asset).model_copy(
        update={
            "split": item.split,
            "annotation_uri": item.annotation_uri,
            "reused": reused,
        }
    )


@router.get("/datasets/{dataset_id}/assets", response_model=list[AssetResponse])
def list_assets(
    dataset_id: UUID,
    workspace_id: WorkspaceId,
    session: SessionDep,
) -> list[AssetResponse]:
    return [
        AssetResponse.model_validate(asset)
        for asset in catalog_service.list_assets(session, workspace_id, dataset_id)
    ]


@router.get(
    "/datasets/{dataset_id}/source-videos",
    response_model=list[SourceAssetResponse],
)
def list_source_videos(
    dataset_id: UUID,
    workspace_id: WorkspaceId,
    session: SessionDep,
) -> list[SourceAssetResponse]:
    return [
        SourceAssetResponse.model_validate(asset)
        for asset in catalog_service.list_source_videos(session, workspace_id, dataset_id)
    ]


@router.get("/datasets/{dataset_id}/assets/{asset_id}/content")
def get_asset_content(
    dataset_id: UUID,
    asset_id: UUID,
    workspace_id: WorkspaceId,
    session: SessionDep,
    storage: StorageDep,
) -> Response:
    asset, _item = catalog_service.require_dataset_item(
        session,
        workspace_id,
        dataset_id,
        asset_id,
    )
    return Response(
        content=storage.get_bytes(asset.uri),
        media_type=asset.media_type,
        headers={"Cache-Control": "private, max-age=300"},
    )


@router.patch(
    "/datasets/{dataset_id}/items/{asset_id}",
    response_model=AssetResponse,
)
def update_dataset_item(
    dataset_id: UUID,
    asset_id: UUID,
    payload: DatasetItemUpdate,
    workspace_id: WorkspaceId,
    session: SessionDep,
) -> AssetResponse:
    return AssetResponse.model_validate(
        catalog_service.update_dataset_item(
            session,
            workspace_id,
            dataset_id,
            asset_id,
            payload,
        )
    )


@router.post(
    "/datasets/{dataset_id}/items/{asset_id}/annotation-uploads",
    response_model=UploadIntentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_annotation_upload_intent(
    dataset_id: UUID,
    asset_id: UUID,
    payload: AnnotationUploadIntentCreate,
    workspace_id: WorkspaceId,
    session: SessionDep,
    storage: StorageDep,
) -> UploadIntentResponse:
    return catalog_service.create_annotation_upload_intent(
        session,
        storage,
        workspace_id,
        dataset_id,
        asset_id,
        payload,
    )


@router.post(
    "/datasets/{dataset_id}/items/{asset_id}/annotation",
    response_model=AssetResponse,
)
def register_annotation(
    dataset_id: UUID,
    asset_id: UUID,
    payload: AnnotationRegister,
    workspace_id: WorkspaceId,
    session: SessionDep,
    storage: StorageDep,
) -> AssetResponse:
    return AssetResponse.model_validate(
        catalog_service.register_annotation(
            session,
            storage,
            workspace_id,
            dataset_id,
            asset_id,
            payload,
        )
    )


@router.get("/datasets/{dataset_id}/items/{asset_id}/annotation")
def get_annotation_content(
    dataset_id: UUID,
    asset_id: UUID,
    workspace_id: WorkspaceId,
    session: SessionDep,
    storage: StorageDep,
) -> Response:
    _asset, item = catalog_service.require_dataset_item(
        session,
        workspace_id,
        dataset_id,
        asset_id,
    )
    if not item.annotation_uri:
        return Response(content=b"", media_type="text/plain")
    return Response(
        content=storage.get_bytes(item.annotation_uri),
        media_type="text/plain",
        headers={"Cache-Control": "private, max-age=60"},
    )


@router.post(
    "/datasets/{dataset_id}/video-extractions",
    response_model=VideoExtractionJobResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_video_extraction_job(
    dataset_id: UUID,
    payload: VideoExtractionJobCreate,
    idempotency_key: IdempotencyKey,
    workspace_id: WorkspaceId,
    session: SessionDep,
    background_tasks: BackgroundTasks,
    dispatcher: VideoExtractionDispatcherDep,
) -> VideoExtractionJobResponse:
    job, _reused = video_extraction_service.create_job(
        session,
        workspace_id,
        dataset_id,
        idempotency_key,
        payload,
    )
    if job.status == "queued":
        background_tasks.add_task(dispatcher.submit, workspace_id, job.id)
    return job


@router.get(
    "/datasets/{dataset_id}/video-extractions",
    response_model=list[VideoExtractionJobResponse],
)
def list_video_extraction_jobs(
    dataset_id: UUID,
    workspace_id: WorkspaceId,
    session: SessionDep,
) -> list[VideoExtractionJobResponse]:
    return video_extraction_service.list_jobs(session, workspace_id, dataset_id)


@router.put(
    "/datasets/{dataset_id}/video-extractions/{job_id}/annotation-task",
    response_model=AnnotationTaskResponse,
)
def create_annotation_task_from_video_extraction(
    dataset_id: UUID,
    job_id: UUID,
    payload: AnnotationTaskFromVideoExtractionCreate,
    current_user: CurrentUser,
    workspace_id: WorkspaceId,
    session: SessionDep,
) -> AnnotationTaskResponse:
    return annotation_service.create_task_from_video_extraction(
        session,
        workspace_id,
        dataset_id,
        job_id,
        current_user.id,
        payload,
    )


@router.get("/video-extractions/{job_id}", response_model=VideoExtractionJobResponse)
def get_video_extraction_job(
    job_id: UUID,
    workspace_id: WorkspaceId,
    session: SessionDep,
) -> VideoExtractionJobResponse:
    return video_extraction_service.require_job(session, workspace_id, job_id)


@router.post("/video-extractions/{job_id}:cancel", response_model=VideoExtractionJobResponse)
def cancel_video_extraction_job(
    job_id: UUID,
    workspace_id: WorkspaceId,
    session: SessionDep,
) -> VideoExtractionJobResponse:
    return video_extraction_service.cancel_job(session, workspace_id, job_id)


@router.post(
    "/internal/video-extractions/{job_id}/execution:claim",
    response_model=dict,
    include_in_schema=False,
)
def claim_video_extraction_job(
    job_id: UUID,
    payload: VideoExtractionWorkerClaim,
    workspace_id: WorkspaceId,
    session: SessionDep,
    storage: StorageDep,
    _worker_auth: WorkerAuth,
) -> dict:
    job, job_spec = video_extraction_service.claim_job(
        session,
        storage,
        workspace_id,
        job_id,
        payload,
    )
    return {"job": job.model_dump(mode="json"), "job_spec": job_spec}


@router.post(
    "/internal/video-extractions/{job_id}/execution:heartbeat",
    response_model=VideoExtractionJobResponse,
    include_in_schema=False,
)
def heartbeat_video_extraction_job(
    job_id: UUID,
    payload: VideoExtractionWorkerHeartbeat,
    workspace_id: WorkspaceId,
    session: SessionDep,
    _worker_auth: WorkerAuth,
) -> VideoExtractionJobResponse:
    return video_extraction_service.heartbeat_job(session, workspace_id, job_id, payload)


@router.post(
    "/internal/video-extractions/executions:recover-stale",
    response_model=VideoExtractionRecoveryResponse,
    include_in_schema=False,
)
def recover_stale_video_extraction_executions(
    session: SessionDep,
    background_tasks: BackgroundTasks,
    dispatcher: VideoExtractionDispatcherDep,
    _worker_auth: WorkerAuth,
) -> VideoExtractionRecoveryResponse:
    settings = get_settings()
    recovered = video_extraction_service.recover_stale_jobs(
        session,
        lease_timeout_seconds=settings.video_extraction_execution_lease_timeout_seconds,
        max_attempts=settings.video_extraction_execution_max_attempts,
    )
    for item in recovered:
        if item["action"] == "requeued":
            background_tasks.add_task(dispatcher.submit, item["workspace_id"], item["job_id"])
    return VideoExtractionRecoveryResponse.model_validate({"recovered": recovered})


@router.post(
    "/internal/video-extractions/{job_id}/events",
    response_model=VideoExtractionJobResponse,
    include_in_schema=False,
)
def receive_video_extraction_event(
    job_id: UUID,
    payload: VideoExtractionWorkerEvent,
    workspace_id: WorkspaceId,
    session: SessionDep,
    _worker_auth: WorkerAuth,
) -> VideoExtractionJobResponse:
    return video_extraction_service.worker_event(session, workspace_id, job_id, payload)


@router.post(
    "/internal/video-extractions/{job_id}/complete",
    response_model=VideoExtractionJobResponse,
    include_in_schema=False,
)
def complete_video_extraction_job(
    job_id: UUID,
    payload: VideoExtractionWorkerCompletion,
    workspace_id: WorkspaceId,
    session: SessionDep,
    storage: StorageDep,
    _worker_auth: WorkerAuth,
) -> VideoExtractionJobResponse:
    return video_extraction_service.complete_job(session, storage, workspace_id, job_id, payload)


@router.post(
    "/datasets/{dataset_id}/annotation-tasks",
    response_model=AnnotationTaskResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_annotation_task(
    dataset_id: UUID,
    payload: AnnotationTaskCreate,
    current_user: CurrentUser,
    workspace_id: WorkspaceId,
    session: SessionDep,
) -> AnnotationTaskResponse:
    return annotation_service.create_task(
        session,
        workspace_id,
        dataset_id,
        current_user.id,
        payload,
    )


@router.get(
    "/datasets/{dataset_id}/annotation-tasks",
    response_model=list[AnnotationTaskResponse],
)
def list_annotation_tasks(
    dataset_id: UUID,
    workspace_id: WorkspaceId,
    session: SessionDep,
) -> list[AnnotationTaskResponse]:
    return annotation_service.list_tasks(session, workspace_id, dataset_id)


@router.get(
    "/datasets/{dataset_id}/annotation-tasks/{task_id}",
    response_model=AnnotationTaskResponse,
)
def get_annotation_task(
    dataset_id: UUID,
    task_id: UUID,
    workspace_id: WorkspaceId,
    session: SessionDep,
) -> AnnotationTaskResponse:
    return annotation_service.get_task(session, workspace_id, dataset_id, task_id)


@router.get("/datasets/{dataset_id}/annotation-tasks/{task_id}/yolo-package")
def export_annotation_task_yolo_package(
    dataset_id: UUID,
    task_id: UUID,
    workspace_id: WorkspaceId,
    session: SessionDep,
    storage: StorageDep,
) -> Response:
    package, filename = annotation_service.export_yolo_task_package(
        session,
        storage,
        workspace_id,
        dataset_id,
        task_id,
    )
    return Response(
        content=package,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "private, no-store",
        },
    )


@router.post(
    "/datasets/{dataset_id}/annotation-tasks/{task_id}/yolo-import-uploads",
    response_model=UploadIntentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_annotation_task_yolo_import_upload_intent(
    dataset_id: UUID,
    task_id: UUID,
    payload: AnnotationTaskYoloImportUploadIntentCreate,
    workspace_id: WorkspaceId,
    session: SessionDep,
    storage: StorageDep,
) -> UploadIntentResponse:
    return annotation_service.create_yolo_import_upload_intent(
        session,
        storage,
        workspace_id,
        dataset_id,
        task_id,
        payload,
    )


@router.post(
    "/datasets/{dataset_id}/annotation-tasks/{task_id}/yolo-import",
    response_model=AnnotationTaskYoloImportResponse,
)
def import_annotation_task_yolo_package(
    dataset_id: UUID,
    task_id: UUID,
    payload: AnnotationTaskYoloImport,
    workspace_id: WorkspaceId,
    session: SessionDep,
    storage: StorageDep,
) -> AnnotationTaskYoloImportResponse:
    return annotation_service.import_yolo_task_package(
        session,
        storage,
        workspace_id,
        dataset_id,
        task_id,
        payload,
    )


@router.get(
    "/datasets/{dataset_id}/annotation-tasks/{task_id}/assets",
    response_model=list[AssetResponse],
)
def list_annotation_task_assets(
    dataset_id: UUID,
    task_id: UUID,
    workspace_id: WorkspaceId,
    session: SessionDep,
) -> list[AssetResponse]:
    return annotation_service.list_task_assets(
        session,
        workspace_id,
        dataset_id,
        task_id,
    )


@router.patch(
    "/datasets/{dataset_id}/annotation-tasks/{task_id}",
    response_model=AnnotationTaskResponse,
)
def update_annotation_task_status(
    dataset_id: UUID,
    task_id: UUID,
    payload: AnnotationTaskStatusUpdate,
    workspace_id: WorkspaceId,
    session: SessionDep,
) -> AnnotationTaskResponse:
    return annotation_service.update_task_status(
        session,
        workspace_id,
        dataset_id,
        task_id,
        payload,
    )


@router.post(
    "/datasets/{dataset_id}/versions:freeze",
    response_model=DatasetVersionResponse,
    status_code=status.HTTP_201_CREATED,
)
def freeze_dataset(
    dataset_id: UUID,
    payload: FreezeDatasetVersion,
    workspace_id: WorkspaceId,
    session: SessionDep,
    storage: StorageDep,
) -> DatasetVersionResponse:
    version = catalog_service.freeze_dataset(
        session,
        storage,
        workspace_id,
        dataset_id,
        payload,
    )
    return DatasetVersionResponse.model_validate(version)


@router.get(
    "/datasets/{dataset_id}/versions",
    response_model=list[DatasetVersionResponse],
)
def list_versions(
    dataset_id: UUID,
    workspace_id: WorkspaceId,
    session: SessionDep,
) -> list[DatasetVersionResponse]:
    return [
        DatasetVersionResponse.model_validate(version)
        for version in catalog_service.list_versions(session, workspace_id, dataset_id)
    ]


@router.get(
    "/dataset-versions/{version_id}/quality-report",
    response_model=DatasetVersionQualityReport,
)
def get_dataset_version_quality_report(
    version_id: UUID,
    workspace_id: WorkspaceId,
    session: SessionDep,
    storage: StorageDep,
) -> DatasetVersionQualityReport:
    return DatasetVersionQualityReport.model_validate(
        catalog_service.get_dataset_version_quality_report(
            session,
            storage,
            workspace_id,
            version_id,
        )
    )
