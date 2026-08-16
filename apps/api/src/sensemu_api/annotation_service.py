import json
from hashlib import sha256
from io import BytesIO
from pathlib import PurePosixPath
from uuid import UUID
from zipfile import ZIP_DEFLATED, BadZipFile, ZipFile

from fastapi import HTTPException, status
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from sensemu_api import catalog_service
from sensemu_api.catalog_schemas import (
    AnnotationTaskCreate,
    AnnotationTaskFromVideoExtractionCreate,
    AnnotationTaskResponse,
    AnnotationTaskStatusUpdate,
    AnnotationTaskYoloImport,
    AnnotationTaskYoloImportResponse,
    AnnotationTaskYoloImportUploadIntentCreate,
    AssetResponse,
    UploadIntentResponse,
)
from sensemu_api.db.models import (
    AnnotationTask,
    AnnotationTaskItem,
    Asset,
    DatasetItem,
    Project,
    VideoExtractionJob,
    VideoExtractionOutput,
)
from sensemu_api.storage import Storage

TASK_PACKAGE_SCHEMA_VERSION = "1.0"
TASK_PACKAGE_MAX_BYTES = 512 * 1024 * 1024
TASK_PACKAGE_MAX_ENTRIES = 20_000


def _task_response(
    task: AnnotationTask,
    *,
    asset_count: int,
    completed_count: int,
) -> AnnotationTaskResponse:
    return AnnotationTaskResponse(
        id=task.id,
        dataset_id=task.dataset_id,
        name=task.name,
        method=task.method,
        asset_scope=task.asset_scope,
        status=task.status,
        assigned_to_user_id=task.assigned_to_user_id,
        source_video_extraction_job_id=task.source_video_extraction_job_id,
        class_map=task.class_map,
        asset_count=asset_count,
        completed_count=completed_count,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


def _task_counts(session: Session, task_id: UUID) -> tuple[int, int]:
    row = session.execute(
        select(
            func.count(AnnotationTaskItem.id),
            func.coalesce(
                func.sum(case((DatasetItem.annotation_uri.is_not(None), 1), else_=0)),
                0,
            ),
        )
        .select_from(AnnotationTaskItem)
        .join(
            DatasetItem,
            DatasetItem.asset_id == AnnotationTaskItem.asset_id,
        )
        .join(
            AnnotationTask,
            AnnotationTask.id == AnnotationTaskItem.task_id,
        )
        .where(
            AnnotationTaskItem.task_id == task_id,
            DatasetItem.dataset_id == AnnotationTask.dataset_id,
            DatasetItem.item_role == "training_asset",
        )
    ).one()
    return int(row[0] or 0), int(row[1] or 0)


def _require_task(
    session: Session,
    workspace_id: UUID,
    dataset_id: UUID,
    task_id: UUID,
) -> AnnotationTask:
    catalog_service.require_dataset(session, workspace_id, dataset_id)
    task = session.scalar(
        select(AnnotationTask).where(
            AnnotationTask.id == task_id,
            AnnotationTask.dataset_id == dataset_id,
        )
    )
    if task is None:
        raise catalog_service.not_found("Annotation task")
    return task


def create_task(
    session: Session,
    workspace_id: UUID,
    dataset_id: UUID,
    assigned_to_user_id: UUID,
    payload: AnnotationTaskCreate,
) -> AnnotationTaskResponse:
    dataset = catalog_service.require_dataset(session, workspace_id, dataset_id)
    class_map = catalog_service.resolve_dataset_class_map(
        session,
        dataset,
        payload.class_map,
    )
    project = session.get(Project, dataset.project_id)
    if project is not None and project.task_type == "object-detection" and not class_map:
        raise catalog_service.conflict("请先为数据集定义类别，再创建目标检测标注任务")
    if payload.method == "smart":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="智能预标注服务尚未接入，请先使用手动标注或导入 YOLO 标注",
        )

    statement = (
        select(Asset.id)
        .join(DatasetItem, DatasetItem.asset_id == Asset.id)
        .where(
            DatasetItem.dataset_id == dataset_id,
            DatasetItem.item_role == "training_asset",
        )
        .order_by(DatasetItem.added_at, Asset.id)
    )
    if payload.asset_scope == "unlabeled":
        statement = statement.where(DatasetItem.annotation_uri.is_(None))
    asset_ids = list(session.scalars(statement).all())
    if not asset_ids:
        detail = (
            "当前数据集没有未标注素材"
            if payload.asset_scope == "unlabeled"
            else "当前数据集没有可加入任务的素材"
        )
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)

    task = AnnotationTask(
        dataset_id=dataset_id,
        name=payload.name.strip(),
        method=payload.method,
        asset_scope=payload.asset_scope,
        status="annotating",
        assigned_to_user_id=assigned_to_user_id,
        source_video_extraction_job_id=None,
        class_map=class_map,
    )
    session.add(task)
    session.flush()
    session.add_all(
        AnnotationTaskItem(task_id=task.id, asset_id=asset_id, position=position)
        for position, asset_id in enumerate(asset_ids, start=1)
    )
    session.flush()
    asset_count, completed_count = _task_counts(session, task.id)
    return _task_response(
        task,
        asset_count=asset_count,
        completed_count=completed_count,
    )


def create_task_from_video_extraction(
    session: Session,
    workspace_id: UUID,
    dataset_id: UUID,
    job_id: UUID,
    assigned_to_user_id: UUID,
    payload: AnnotationTaskFromVideoExtractionCreate,
) -> AnnotationTaskResponse:
    dataset = catalog_service.require_dataset(session, workspace_id, dataset_id)
    job = session.scalar(
        select(VideoExtractionJob).where(
            VideoExtractionJob.id == job_id,
            VideoExtractionJob.dataset_id == dataset_id,
        )
    )
    if job is None:
        raise catalog_service.not_found("Video extraction job")
    if job.status != "succeeded":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="视频抽帧完成后才能创建标注任务",
        )

    existing = session.scalar(
        select(AnnotationTask).where(
            AnnotationTask.source_video_extraction_job_id == job.id,
        )
    )
    if existing is not None:
        asset_count, completed_count = _task_counts(session, existing.id)
        return _task_response(
            existing,
            asset_count=asset_count,
            completed_count=completed_count,
        )

    class_map = catalog_service.resolve_dataset_class_map(
        session,
        dataset,
        payload.class_map,
    )
    project = session.get(Project, dataset.project_id)
    if project is not None and project.task_type == "object-detection" and not class_map:
        raise catalog_service.conflict("请先为数据集定义类别，再创建目标检测标注任务")

    asset_ids = list(
        session.scalars(
            select(VideoExtractionOutput.asset_id)
            .join(
                DatasetItem,
                (DatasetItem.asset_id == VideoExtractionOutput.asset_id)
                & (DatasetItem.dataset_id == dataset_id),
            )
            .where(
                VideoExtractionOutput.job_id == job.id,
                DatasetItem.item_role == "training_asset",
            )
            .order_by(VideoExtractionOutput.frame_index)
        ).all()
    )
    if not asset_ids:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="该抽帧任务没有可用于标注的素材，请重新处理视频",
        )

    task = AnnotationTask(
        dataset_id=dataset_id,
        name=payload.name.strip(),
        method="manual",
        asset_scope="video_extraction",
        status="annotating",
        assigned_to_user_id=assigned_to_user_id,
        source_video_extraction_job_id=job.id,
        class_map=class_map,
    )
    session.add(task)
    session.flush()
    session.add_all(
        AnnotationTaskItem(task_id=task.id, asset_id=asset_id, position=position)
        for position, asset_id in enumerate(asset_ids, start=1)
    )
    session.flush()
    asset_count, completed_count = _task_counts(session, task.id)
    return _task_response(
        task,
        asset_count=asset_count,
        completed_count=completed_count,
    )


def list_tasks(
    session: Session,
    workspace_id: UUID,
    dataset_id: UUID,
) -> list[AnnotationTaskResponse]:
    catalog_service.require_dataset(session, workspace_id, dataset_id)
    tasks = list(
        session.scalars(
            select(AnnotationTask)
            .where(AnnotationTask.dataset_id == dataset_id)
            .order_by(AnnotationTask.created_at.desc())
        ).all()
    )
    return [
        _task_response(task, asset_count=counts[0], completed_count=counts[1])
        for task in tasks
        for counts in [_task_counts(session, task.id)]
    ]


def get_task(
    session: Session,
    workspace_id: UUID,
    dataset_id: UUID,
    task_id: UUID,
) -> AnnotationTaskResponse:
    task = _require_task(session, workspace_id, dataset_id, task_id)
    asset_count, completed_count = _task_counts(session, task.id)
    return _task_response(
        task,
        asset_count=asset_count,
        completed_count=completed_count,
    )


def update_task_status(
    session: Session,
    workspace_id: UUID,
    dataset_id: UUID,
    task_id: UUID,
    payload: AnnotationTaskStatusUpdate,
) -> AnnotationTaskResponse:
    task = _require_task(session, workspace_id, dataset_id, task_id)
    asset_count, completed_count = _task_counts(session, task.id)
    if payload.status == "done" and completed_count != asset_count:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="任务中仍有未标注素材，不能标记为已完成",
        )
    task.status = payload.status
    session.flush()
    return _task_response(
        task,
        asset_count=asset_count,
        completed_count=completed_count,
    )


def _task_asset_rows(session: Session, task: AnnotationTask) -> list[tuple[Asset, DatasetItem]]:
    return list(
        session.execute(
            select(Asset, DatasetItem)
            .join(AnnotationTaskItem, AnnotationTaskItem.asset_id == Asset.id)
            .join(
                DatasetItem,
                (DatasetItem.asset_id == Asset.id) & (DatasetItem.dataset_id == task.dataset_id),
            )
            .where(
                AnnotationTaskItem.task_id == task.id,
                DatasetItem.item_role == "training_asset",
            )
            .order_by(AnnotationTaskItem.position)
        ).all()
    )


def _require_task_class_map(task: AnnotationTask) -> dict[str, str]:
    class_map = task.class_map
    if not class_map:
        raise catalog_service.conflict("请先为标注任务定义类别，再导出或导入 YOLO 任务包")
    if not isinstance(class_map, dict) or any(
        not isinstance(key, str) or not isinstance(value, str) for key, value in class_map.items()
    ):
        raise catalog_service.conflict("标注任务的类别定义格式不正确")
    try:
        class_ids = sorted(int(key) for key in class_map)
    except ValueError as error:
        raise catalog_service.conflict("标注任务的类别编号格式不正确") from error
    if class_ids != list(range(len(class_ids))):
        raise catalog_service.conflict("标注任务的类别编号必须从 0 连续排列")
    return class_map


def _image_extension(media_type: str) -> str:
    extensions = {
        "image/jpeg": "jpg",
        "image/png": "png",
        "image/webp": "webp",
    }
    extension = extensions.get(media_type)
    if extension is None:
        raise catalog_service.conflict("标注任务只能导出图片素材")
    return extension


def _package_manifest(
    task: AnnotationTask,
    rows: list[tuple[Asset, DatasetItem]],
    class_map: dict[str, str],
) -> tuple[dict[str, object], dict[str, tuple[Asset, DatasetItem]]]:
    assets: list[dict[str, object]] = []
    rows_by_asset_id: dict[str, tuple[Asset, DatasetItem]] = {}
    for asset, item in rows:
        asset_id = str(asset.id)
        image_path = f"images/{asset_id}.{_image_extension(asset.media_type)}"
        label_path = f"labels/{asset_id}.txt"
        assets.append(
            {
                "asset_id": asset_id,
                "image_path": image_path,
                "label_path": label_path,
                "image_sha256": asset.checksum_sha256,
                "image_byte_size": asset.byte_size,
                "media_type": asset.media_type,
                "width": asset.width,
                "height": asset.height,
            }
        )
        rows_by_asset_id[asset_id] = (asset, item)
    return (
        {
            "schema_version": TASK_PACKAGE_SCHEMA_VERSION,
            "format": "yolo-detection",
            "task": {
                "id": str(task.id),
                "dataset_id": str(task.dataset_id),
                "name": task.name,
            },
            "class_map": class_map,
            "assets": assets,
        },
        rows_by_asset_id,
    )


def _data_yaml(class_map: dict[str, str]) -> str:
    names = "\n".join(
        f"  {class_id}: {json.dumps(class_map[class_id], ensure_ascii=False)}"
        for class_id in sorted(class_map, key=int)
    )
    return f"path: .\ntrain: images\nval: images\nnames:\n{names}\n"


def export_yolo_task_package(
    session: Session,
    storage: Storage,
    workspace_id: UUID,
    dataset_id: UUID,
    task_id: UUID,
) -> tuple[bytes, str]:
    task = _require_task(session, workspace_id, dataset_id, task_id)
    class_map = _require_task_class_map(task)
    rows = _task_asset_rows(session, task)
    if not rows:
        raise catalog_service.conflict("标注任务没有可导出的素材")
    if sum(asset.byte_size for asset, _item in rows) > TASK_PACKAGE_MAX_BYTES:
        raise catalog_service.conflict("任务包超过 512 MB，请拆分标注任务后再导出")
    manifest, _rows_by_asset_id = _package_manifest(task, rows, class_map)
    package = BytesIO()
    try:
        with ZipFile(package, "w", compression=ZIP_DEFLATED, compresslevel=6) as archive:
            archive.writestr(
                "sensemu-task.json",
                json.dumps(manifest, ensure_ascii=False, separators=(",", ":")),
            )
            archive.writestr("data.yaml", _data_yaml(class_map))
            archive.writestr(
                "README.txt",
                "使用外部工具标注 images 中的图片，并保留 sensemu-task.json 与图片原始内容。\n"
                "完成后将 labels 中同名 .txt 标注与原图片一起压缩，再导入此任务。\n",
            )
            for asset, item in rows:
                image_path = f"images/{asset.id}.{_image_extension(asset.media_type)}"
                try:
                    image_body = storage.get_bytes(asset.uri)
                except (OSError, ValueError) as error:
                    raise catalog_service.conflict(f"无法读取素材 {asset.id}") from error
                if sha256(image_body).hexdigest() != asset.checksum_sha256:
                    raise catalog_service.conflict(f"素材 {asset.id} 的内容与登记哈希不一致")
                archive.writestr(image_path, image_body)
                label_body = b""
                if item.annotation_uri:
                    try:
                        label_body = storage.get_bytes(item.annotation_uri)
                    except (OSError, ValueError) as error:
                        raise catalog_service.conflict(
                            f"无法读取素材 {asset.id} 的已有标注"
                        ) from error
                archive.writestr(f"labels/{asset.id}.txt", label_body)
    except OSError as error:
        raise catalog_service.conflict("无法生成 YOLO 标注任务包") from error
    return package.getvalue(), f"annotation-task-{task.id}.zip"


def create_yolo_import_upload_intent(
    session: Session,
    storage: Storage,
    workspace_id: UUID,
    dataset_id: UUID,
    task_id: UUID,
    payload: AnnotationTaskYoloImportUploadIntentCreate,
) -> UploadIntentResponse:
    task = _require_task(session, workspace_id, dataset_id, task_id)
    if task.status == "done":
        raise catalog_service.conflict("已完成的任务不能再导入标注")
    _require_task_class_map(task)
    if not payload.filename.lower().endswith(".zip"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="YOLO 标注任务包必须使用 .zip 扩展名",
        )
    key = (
        f"workspaces/{workspace_id}/datasets/{dataset_id}/annotation-task-imports/{task_id}/"
        f"uploads/{payload.checksum_sha256[:16]}-{catalog_service.safe_filename(payload.filename)}"
    )
    expires_in = 900
    content_type = "application/zip"
    return UploadIntentResponse(
        upload_url=storage.presign_put(key, content_type, payload.checksum_sha256, expires_in),
        object_key=key,
        headers={
            "Content-Type": content_type,
            "x-amz-meta-sha256": payload.checksum_sha256,
        },
        expires_in=expires_in,
    )


def _validate_archive_names(archive: ZipFile) -> set[str]:
    infos = archive.infolist()
    if len(infos) > TASK_PACKAGE_MAX_ENTRIES:
        raise catalog_service.conflict("任务包包含过多文件")
    names: set[str] = set()
    total_uncompressed = 0
    for info in infos:
        path = PurePosixPath(info.filename)
        if path.is_absolute() or ".." in path.parts:
            raise catalog_service.conflict("任务包包含无效文件路径")
        if info.flag_bits & 0x1:
            raise catalog_service.conflict("任务包不能包含加密文件")
        if not info.is_dir():
            if info.filename in names:
                raise catalog_service.conflict("任务包包含重复文件")
            names.add(info.filename)
            total_uncompressed += info.file_size
    if total_uncompressed > TASK_PACKAGE_MAX_BYTES * 2:
        raise catalog_service.conflict("任务包解压后的内容超过限制")
    return names


def _read_task_manifest(archive: ZipFile, names: set[str]) -> dict[str, object]:
    if "sensemu-task.json" not in names:
        raise catalog_service.conflict("任务包缺少 sensemu-task.json")
    try:
        manifest = json.loads(archive.read("sensemu-task.json").decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, KeyError) as error:
        raise catalog_service.conflict("任务包清单格式不正确") from error
    if not isinstance(manifest, dict):
        raise catalog_service.conflict("任务包清单格式不正确")
    return manifest


def import_yolo_task_package(
    session: Session,
    storage: Storage,
    workspace_id: UUID,
    dataset_id: UUID,
    task_id: UUID,
    payload: AnnotationTaskYoloImport,
) -> AnnotationTaskYoloImportResponse:
    task = _require_task(session, workspace_id, dataset_id, task_id)
    if task.status == "done":
        raise catalog_service.conflict("已完成的任务不能再导入标注")
    class_map = _require_task_class_map(task)
    expected_prefix = f"workspaces/{workspace_id}/datasets/{dataset_id}/annotation-task-imports/{task.id}/uploads/"
    if not payload.object_key.startswith(expected_prefix):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="object_key does not belong to this annotation task",
        )
    if not storage.verify_object(payload.object_key, payload.byte_size, payload.checksum_sha256):
        raise catalog_service.conflict("上传的标注任务包不存在或与校验和不一致")
    try:
        package_body = storage.get_bytes(storage.uri_for(payload.object_key))
    except (OSError, ValueError) as error:
        raise catalog_service.conflict("无法读取上传的标注任务包") from error

    rows = _task_asset_rows(session, task)
    expected_manifest, rows_by_asset_id = _package_manifest(task, rows, class_map)
    expected_assets = expected_manifest["assets"]
    assert isinstance(expected_assets, list)
    allowed_class_ids = {int(class_id) for class_id in class_map}
    imported_labels: list[tuple[Asset, DatasetItem, bytes]] = []
    try:
        with ZipFile(BytesIO(package_body)) as archive:
            names = _validate_archive_names(archive)
            manifest = _read_task_manifest(archive, names)
            if manifest.get("schema_version") != TASK_PACKAGE_SCHEMA_VERSION:
                raise catalog_service.conflict("任务包版本不受支持")
            if manifest.get("format") != "yolo-detection":
                raise catalog_service.conflict("任务包不是目标检测 YOLO 格式")
            package_task = manifest.get("task")
            if not isinstance(package_task, dict) or package_task.get("id") != str(task.id):
                raise catalog_service.conflict("任务包不属于当前标注任务")
            if package_task.get("dataset_id") != str(dataset_id):
                raise catalog_service.conflict("任务包不属于当前数据集")
            if manifest.get("class_map") != class_map:
                raise catalog_service.conflict("任务包的类别定义与当前任务不一致")
            package_assets = manifest.get("assets")
            if not isinstance(package_assets, list) or len(package_assets) != len(expected_assets):
                raise catalog_service.conflict("任务包中的素材清单与当前任务不一致")

            package_assets_by_id: dict[str, dict[str, object]] = {}
            for package_asset in package_assets:
                if not isinstance(package_asset, dict):
                    raise catalog_service.conflict("任务包中的素材清单格式不正确")
                asset_id = package_asset.get("asset_id")
                if not isinstance(asset_id, str) or asset_id in package_assets_by_id:
                    raise catalog_service.conflict("任务包中的素材编号不正确")
                package_assets_by_id[asset_id] = package_asset
            if set(package_assets_by_id) != set(rows_by_asset_id):
                raise catalog_service.conflict("任务包中的图片不属于当前标注任务")

            for expected_asset in expected_assets:
                assert isinstance(expected_asset, dict)
                asset_id = expected_asset["asset_id"]
                assert isinstance(asset_id, str)
                package_asset = package_assets_by_id[asset_id]
                image_path = expected_asset["image_path"]
                label_path = expected_asset["label_path"]
                if (
                    package_asset.get("image_path") != image_path
                    or package_asset.get("label_path") != label_path
                    or package_asset.get("image_sha256") != expected_asset["image_sha256"]
                    or package_asset.get("image_byte_size") != expected_asset["image_byte_size"]
                    or package_asset.get("media_type") != expected_asset["media_type"]
                ):
                    raise catalog_service.conflict("任务包中的图片清单已被修改")
                if not isinstance(image_path, str) or image_path not in names:
                    raise catalog_service.conflict("任务包缺少原始图片")
                image_body = archive.read(image_path)
                expected_hash = expected_asset["image_sha256"]
                expected_size = expected_asset["image_byte_size"]
                if (
                    sha256(image_body).hexdigest() != expected_hash
                    or len(image_body) != expected_size
                ):
                    raise catalog_service.conflict("任务包中的图片与原始素材不一致")
                if not isinstance(label_path, str) or label_path not in names:
                    raise catalog_service.conflict("任务包缺少对应的 YOLO 标注文件")
                label_body = archive.read(label_path)
                catalog_service.parse_yolo_detection_annotation(label_body, allowed_class_ids)
                asset, item = rows_by_asset_id[asset_id]
                imported_labels.append((asset, item, label_body))
    except BadZipFile as error:
        raise catalog_service.conflict("上传文件不是有效的 ZIP 任务包") from error

    for asset, item, label_body in imported_labels:
        label_hash = sha256(label_body).hexdigest()
        key = (
            f"workspaces/{workspace_id}/datasets/{dataset_id}/annotations/tasks/{task.id}/"
            f"{asset.id}/{label_hash[:16]}.txt"
        )
        item.annotation_uri = storage.put_bytes(key, label_body, "text/plain")
    session.flush()
    asset_count, completed_count = _task_counts(session, task.id)
    return AnnotationTaskYoloImportResponse(
        task=_task_response(task, asset_count=asset_count, completed_count=completed_count),
        imported_asset_count=len(imported_labels),
    )


def list_task_assets(
    session: Session,
    workspace_id: UUID,
    dataset_id: UUID,
    task_id: UUID,
) -> list[AssetResponse]:
    task = _require_task(session, workspace_id, dataset_id, task_id)
    rows = _task_asset_rows(session, task)
    return [
        AssetResponse.model_validate(catalog_service.asset_item_response(asset, item))
        for asset, item in rows
    ]
