import re
from collections import Counter, defaultdict
from datetime import UTC, datetime
from math import isfinite
from pathlib import PurePath
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from sensemu_api.catalog_schemas import (
    AnnotationRegister,
    AnnotationUploadIntentCreate,
    AssetRegister,
    DatasetClassMapUpdate,
    DatasetCreate,
    DatasetItemUpdate,
    DatasetResponse,
    FreezeDatasetVersion,
    ProjectCreate,
    UploadIntentCreate,
    UploadIntentResponse,
    WorkspaceCreate,
)
from sensemu_api.db.models import (
    AnnotationTask,
    Asset,
    Dataset,
    DatasetItem,
    DatasetVersion,
    Deployment,
    Model,
    ModelVersion,
    Project,
    Run,
    UserAccount,
    VideoExtractionJob,
    Workspace,
    WorkspaceMembership,
)
from sensemu_api.identity_service import add_workspace_owner, list_user_workspaces
from sensemu_api.storage import Storage


def conflict(message: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=message)


def not_found(resource: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{resource} not found")


def create_workspace(
    session: Session,
    payload: WorkspaceCreate,
    owner: UserAccount,
) -> tuple[Workspace, WorkspaceMembership]:
    existing = session.scalar(select(Workspace).where(Workspace.slug == payload.slug))
    if existing:
        raise conflict("Workspace slug already exists")
    workspace = Workspace(slug=payload.slug, name=payload.name)
    session.add(workspace)
    session.flush()
    membership = add_workspace_owner(session, workspace.id, owner.id)
    return workspace, membership


def list_workspaces(
    session: Session,
    user_id: UUID,
) -> list[tuple[Workspace, WorkspaceMembership]]:
    return list_user_workspaces(session, user_id)


def require_workspace(session: Session, workspace_id: UUID) -> Workspace:
    workspace = session.get(Workspace, workspace_id)
    if workspace is None:
        raise not_found("Workspace")
    return workspace


def create_project(
    session: Session,
    workspace_id: UUID,
    payload: ProjectCreate,
) -> Project:
    require_workspace(session, workspace_id)
    existing = session.scalar(
        select(Project).where(
            Project.workspace_id == workspace_id,
            Project.slug == payload.slug,
        )
    )
    if existing:
        raise conflict("Project slug already exists in this workspace")
    project = Project(workspace_id=workspace_id, **payload.model_dump())
    session.add(project)
    session.flush()
    return project


def list_projects(session: Session, workspace_id: UUID) -> list[Project]:
    require_workspace(session, workspace_id)
    statement = (
        select(Project)
        .where(Project.workspace_id == workspace_id, Project.archived_at.is_(None))
        .order_by(Project.created_at.desc())
    )
    return list(session.scalars(statement).all())


def require_project(session: Session, workspace_id: UUID, project_id: UUID) -> Project:
    project = session.scalar(
        select(Project).where(
            Project.id == project_id,
            Project.workspace_id == workspace_id,
        )
    )
    if project is None:
        raise not_found("Project")
    return project


def require_active_project(
    session: Session,
    workspace_id: UUID,
    project_id: UUID,
) -> Project:
    project = require_project(session, workspace_id, project_id)
    if project.archived_at is not None:
        raise conflict("项目已归档")
    if project.status == "paused":
        raise conflict("项目已暂停，请先继续项目")
    return project


def pause_project(session: Session, workspace_id: UUID, project_id: UUID) -> Project:
    project = require_project(session, workspace_id, project_id)
    if project.archived_at is not None:
        raise conflict("项目已归档")
    project.status = "paused"
    session.flush()
    return project


def resume_project(session: Session, workspace_id: UUID, project_id: UUID) -> Project:
    project = require_project(session, workspace_id, project_id)
    if project.archived_at is not None:
        raise conflict("项目已归档")
    project.status = "active"
    session.flush()
    return project


def archive_project(session: Session, workspace_id: UUID, project_id: UUID) -> Project:
    project = require_project(session, workspace_id, project_id)
    if project.archived_at is not None:
        raise conflict("项目已归档")

    active_run = session.scalar(
        select(Run.id)
        .where(
            Run.project_id == project_id,
            Run.status.in_({"queued", "preparing", "running", "cancel_requested"}),
        )
        .limit(1)
    )
    if active_run is not None:
        raise conflict("项目仍有运行中的训练或处理任务，完成或取消后才能归档")

    published_deployment = session.scalar(
        select(Deployment.id)
        .join(ModelVersion, Deployment.model_version_id == ModelVersion.id)
        .join(Model, ModelVersion.model_id == Model.id)
        .where(Model.project_id == project_id, Deployment.status == "published")
        .limit(1)
    )
    if published_deployment is not None:
        raise conflict("项目仍有运行中的在线服务，请先停用服务后再归档")

    project.status = "paused"
    project.archived_at = datetime.now(UTC)
    session.flush()
    return project


def create_dataset(
    session: Session,
    workspace_id: UUID,
    project_id: UUID,
    payload: DatasetCreate,
) -> Dataset:
    require_project(session, workspace_id, project_id)
    existing = session.scalar(
        select(Dataset).where(Dataset.project_id == project_id, Dataset.name == payload.name)
    )
    if existing:
        raise conflict("Dataset name already exists in this project")
    dataset = Dataset(project_id=project_id, **payload.model_dump())
    session.add(dataset)
    session.flush()
    return dataset


def list_datasets(
    session: Session,
    workspace_id: UUID,
    project_id: UUID,
) -> list[DatasetResponse]:
    require_project(session, workspace_id, project_id)
    statement = (
        select(
            Dataset,
            func.count(func.distinct(DatasetItem.asset_id)).label("asset_count"),
            func.count(func.distinct(DatasetVersion.id)).label("version_count"),
        )
        .outerjoin(
            DatasetItem,
            (DatasetItem.dataset_id == Dataset.id)
            & (DatasetItem.item_role == "training_asset"),
        )
        .outerjoin(DatasetVersion, DatasetVersion.dataset_id == Dataset.id)
        .where(Dataset.project_id == project_id)
        .group_by(Dataset.id)
        .order_by(Dataset.created_at.desc())
    )
    return [
        DatasetResponse.model_validate(dataset).model_copy(
            update={"asset_count": asset_count, "version_count": version_count}
        )
        for dataset, asset_count, version_count in session.execute(statement)
    ]


def require_dataset(session: Session, workspace_id: UUID, dataset_id: UUID) -> Dataset:
    dataset = session.scalar(
        select(Dataset)
        .join(Project, Project.id == Dataset.project_id)
        .where(Dataset.id == dataset_id, Project.workspace_id == workspace_id)
    )
    if dataset is None:
        raise not_found("Dataset")
    return dataset


def update_dataset_class_map(
    session: Session,
    workspace_id: UUID,
    dataset_id: UUID,
    payload: DatasetClassMapUpdate,
) -> Dataset:
    dataset = require_dataset(session, workspace_id, dataset_id)
    if dataset.class_map == payload.class_map:
        return dataset
    has_annotations = session.scalar(
        select(DatasetItem.id).where(
            DatasetItem.dataset_id == dataset_id,
            DatasetItem.item_role == "training_asset",
            DatasetItem.annotation_uri.is_not(None),
        ).limit(1)
    )
    has_tasks = session.scalar(
        select(AnnotationTask.id).where(AnnotationTask.dataset_id == dataset_id).limit(1)
    )
    if has_annotations or has_tasks:
        raise conflict("已有标注或标注任务，不能修改类别；请创建新的数据集继续标注")
    dataset.class_map = payload.class_map
    session.flush()
    return dataset


def delete_dataset(session: Session, workspace_id: UUID, dataset_id: UUID) -> None:
    dataset = require_dataset(session, workspace_id, dataset_id)

    if session.scalar(
        select(DatasetVersion.id).where(DatasetVersion.dataset_id == dataset_id).limit(1)
    ) is not None:
        raise conflict("已有冻结数据版本，不能删除数据集")
    if session.scalar(
        select(AnnotationTask.id).where(AnnotationTask.dataset_id == dataset_id).limit(1)
    ) is not None:
        raise conflict("已有标注任务，不能删除数据集")
    if session.scalar(
        select(VideoExtractionJob.id).where(VideoExtractionJob.dataset_id == dataset_id).limit(1)
    ) is not None:
        raise conflict("已有视频抽帧任务，不能删除数据集")

    # Assets are workspace-scoped and may be reused by another dataset. Keep object cleanup
    # outside this operation so a metadata deletion cannot remove shared source files.
    session.execute(delete(DatasetItem).where(DatasetItem.dataset_id == dataset_id))
    session.delete(dataset)
    session.flush()


def resolve_dataset_class_map(
    session: Session,
    dataset: Dataset,
    requested_class_map: dict[str, str],
) -> dict[str, str]:
    if dataset.class_map:
        if requested_class_map != dataset.class_map:
            raise conflict("类别定义必须与数据集当前类别一致")
        return dataset.class_map
    if requested_class_map:
        dataset.class_map = requested_class_map
        session.flush()
    return dataset.class_map


def safe_filename(filename: str) -> str:
    name = PurePath(filename).name
    normalized = re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip(".-")
    return normalized[:180] or "asset"


def create_upload_intent(
    session: Session,
    storage: Storage,
    workspace_id: UUID,
    dataset_id: UUID,
    payload: UploadIntentCreate,
) -> UploadIntentResponse:
    require_dataset(session, workspace_id, dataset_id)
    key = (
        f"workspaces/{workspace_id}/datasets/{dataset_id}/uploads/"
        f"{payload.checksum_sha256[:16]}-{safe_filename(payload.filename)}"
    )
    expires_in = 900
    return UploadIntentResponse(
        upload_url=storage.presign_put(
            key,
            payload.content_type,
            payload.checksum_sha256,
            expires_in,
        ),
        object_key=key,
        headers={
            "Content-Type": payload.content_type,
            "x-amz-meta-sha256": payload.checksum_sha256,
        },
        expires_in=expires_in,
    )


def register_asset(
    session: Session,
    storage: Storage,
    workspace_id: UUID,
    dataset_id: UUID,
    payload: AssetRegister,
) -> tuple[Asset, DatasetItem, bool]:
    require_dataset(session, workspace_id, dataset_id)
    expected_prefix = f"workspaces/{workspace_id}/datasets/{dataset_id}/uploads/"
    if not payload.object_key.startswith(expected_prefix):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="object_key does not belong to this workspace and dataset",
        )
    if not storage.verify_object(
        payload.object_key,
        payload.byte_size,
        payload.checksum_sha256,
    ):
        raise conflict("Uploaded object is missing or does not match its declared checksum")

    asset = session.scalar(
        select(Asset).where(
            Asset.workspace_id == workspace_id,
            Asset.checksum_sha256 == payload.checksum_sha256,
        )
    )
    reused = asset is not None
    if asset is None:
        asset = Asset(
            workspace_id=workspace_id,
            uri=storage.uri_for(payload.object_key),
            media_type=payload.media_type,
            checksum_sha256=payload.checksum_sha256,
            byte_size=payload.byte_size,
            width=payload.width,
            height=payload.height,
        )
        session.add(asset)
        session.flush()

    item = session.scalar(
        select(DatasetItem).where(
            DatasetItem.dataset_id == dataset_id,
            DatasetItem.asset_id == asset.id,
        )
    )
    if item is None:
        item = DatasetItem(
            dataset_id=dataset_id,
            asset_id=asset.id,
            item_role=("source_video" if asset.media_type.startswith("video/") else "training_asset"),
        )
        session.add(item)
        session.flush()
    elif asset.media_type.startswith("video/") and item.item_role != "source_video":
        item.item_role = "source_video"
        item.split = None
        item.annotation_uri = None
        session.flush()
    return asset, item, reused


def list_assets(session: Session, workspace_id: UUID, dataset_id: UUID) -> list[dict[str, Any]]:
    require_dataset(session, workspace_id, dataset_id)
    statement = (
        select(Asset, DatasetItem.split, DatasetItem.annotation_uri)
        .join(DatasetItem, DatasetItem.asset_id == Asset.id)
        .where(
            DatasetItem.dataset_id == dataset_id,
            DatasetItem.item_role == "training_asset",
        )
        .order_by(DatasetItem.added_at.desc())
    )
    return [
        {
            "id": asset.id,
            "workspace_id": asset.workspace_id,
            "uri": asset.uri,
            "media_type": asset.media_type,
            "checksum_sha256": asset.checksum_sha256,
            "byte_size": asset.byte_size,
            "width": asset.width,
            "height": asset.height,
            "created_at": asset.created_at,
            "split": split,
            "annotation_uri": annotation_uri,
            "reused": False,
        }
        for asset, split, annotation_uri in session.execute(statement)
    ]


def list_source_videos(session: Session, workspace_id: UUID, dataset_id: UUID) -> list[Asset]:
    require_dataset(session, workspace_id, dataset_id)
    return list(
        session.scalars(
            select(Asset)
            .join(DatasetItem, DatasetItem.asset_id == Asset.id)
            .where(
                DatasetItem.dataset_id == dataset_id,
                DatasetItem.item_role == "source_video",
            )
            .order_by(DatasetItem.added_at.desc())
        ).all()
    )


def require_dataset_item(
    session: Session,
    workspace_id: UUID,
    dataset_id: UUID,
    asset_id: UUID,
) -> tuple[Asset, DatasetItem]:
    require_dataset(session, workspace_id, dataset_id)
    row = session.execute(
        select(Asset, DatasetItem)
        .join(DatasetItem, DatasetItem.asset_id == Asset.id)
        .where(
            DatasetItem.dataset_id == dataset_id,
            DatasetItem.asset_id == asset_id,
            Asset.workspace_id == workspace_id,
        )
    ).one_or_none()
    if row is None:
        raise not_found("Dataset item")
    return row


def update_dataset_item(
    session: Session,
    workspace_id: UUID,
    dataset_id: UUID,
    asset_id: UUID,
    payload: DatasetItemUpdate,
) -> dict[str, Any]:
    asset, item = require_dataset_item(session, workspace_id, dataset_id, asset_id)
    item.split = payload.split
    session.flush()
    return asset_item_response(asset, item)


def create_annotation_upload_intent(
    session: Session,
    storage: Storage,
    workspace_id: UUID,
    dataset_id: UUID,
    asset_id: UUID,
    payload: AnnotationUploadIntentCreate,
) -> UploadIntentResponse:
    require_dataset_item(session, workspace_id, dataset_id, asset_id)
    if not payload.filename.lower().endswith(".txt"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="YOLO 标注文件必须使用 .txt 扩展名",
        )
    key = (
        f"workspaces/{workspace_id}/datasets/{dataset_id}/annotations/{asset_id}/"
        f"{payload.checksum_sha256[:16]}-{safe_filename(payload.filename)}"
    )
    expires_in = 900
    content_type = "text/plain"
    return UploadIntentResponse(
        upload_url=storage.presign_put(
            key,
            content_type,
            payload.checksum_sha256,
            expires_in,
        ),
        object_key=key,
        headers={
            "Content-Type": content_type,
            "x-amz-meta-sha256": payload.checksum_sha256,
        },
        expires_in=expires_in,
    )


def parse_yolo_detection_annotation(
    body: bytes,
    allowed_class_ids: set[int] | None = None,
) -> set[int]:
    return set(_parse_yolo_detection_annotation_classes(body, allowed_class_ids))


def _parse_yolo_detection_annotation_classes(
    body: bytes,
    allowed_class_ids: set[int] | None = None,
) -> list[int]:
    try:
        text = body.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise conflict("YOLO 标注必须是 UTF-8 文本") from error

    class_ids: list[int] = []
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        fields = line.split()
        if len(fields) != 5:
            raise conflict(f"YOLO 标注第 {line_number} 行必须包含 5 个字段")
        try:
            class_id = int(fields[0])
            coordinates = [float(value) for value in fields[1:]]
        except ValueError as error:
            raise conflict(f"YOLO 标注第 {line_number} 行包含无效数字") from error
        if class_id < 0:
            raise conflict(f"YOLO 标注第 {line_number} 行的类别编号不能为负数")
        if not all(isfinite(value) for value in coordinates):
            raise conflict(f"YOLO 标注第 {line_number} 行包含非有限坐标")
        x_center, y_center, width, height = coordinates
        if not (0 <= x_center <= 1 and 0 <= y_center <= 1):
            raise conflict(f"YOLO 标注第 {line_number} 行的中心坐标必须位于 0 到 1")
        if not (0 < width <= 1 and 0 < height <= 1):
            raise conflict(f"YOLO 标注第 {line_number} 行的宽高必须大于 0 且不超过 1")
        if allowed_class_ids is not None and class_id not in allowed_class_ids:
            raise conflict(f"YOLO 标注第 {line_number} 行引用了未定义类别 {class_id}")
        class_ids.append(class_id)
    return class_ids


def build_dataset_quality_report(
    storage: Storage,
    assets: list[dict[str, Any]],
    class_map: dict[str, str],
) -> dict[str, Any]:
    split_counts = {"train": 0, "valid": 0, "test": 0}
    annotated_asset_count = 0
    class_annotation_counts: Counter[int] = Counter()
    class_asset_ids: dict[int, set[str]] = defaultdict(set)
    known_dimensions: list[tuple[int, int]] = []
    allowed_class_ids = {int(class_id) for class_id in class_map}

    for asset in assets:
        split = asset.get("split")
        if split in split_counts:
            split_counts[split] += 1

        width = asset.get("width")
        height = asset.get("height")
        if isinstance(width, int) and width > 0 and isinstance(height, int) and height > 0:
            known_dimensions.append((width, height))

        annotation_uri = asset.get("annotation_uri")
        if not isinstance(annotation_uri, str) or not annotation_uri:
            continue
        annotated_asset_count += 1
        if not class_map:
            continue
        class_ids = _parse_yolo_detection_annotation_classes(
            storage.get_bytes(annotation_uri),
            allowed_class_ids,
        )
        asset_id = str(asset.get("asset_id", ""))
        class_annotation_counts.update(class_ids)
        for class_id in set(class_ids):
            class_asset_ids[class_id].add(asset_id)

    asset_count = len(assets)
    class_distribution = [
        {
            "class_id": class_id,
            "class_name": class_map[str(class_id)],
            "annotation_count": class_annotation_counts[class_id],
            "asset_count": len(class_asset_ids[class_id]),
        }
        for class_id in sorted(allowed_class_ids)
    ]
    advisories: list[str] = []
    if split_counts["test"] == 0:
        advisories.append("未包含测试集；训练验证可用，但独立验收应使用单独冻结的数据版本。")
    if len(known_dimensions) != asset_count:
        advisories.append("部分资产缺少尺寸元数据；导入后补齐可改善数据分析。")
    empty_classes = [
        item["class_name"]
        for item in class_distribution
        if item["annotation_count"] == 0
    ]
    if empty_classes:
        advisories.append(f"以下类别没有已登记的标注实例：{'、'.join(empty_classes)}。")
    total_annotations = sum(item["annotation_count"] for item in class_distribution)
    if len(class_distribution) > 1 and total_annotations:
        dominant = max(item["annotation_count"] for item in class_distribution)
        if dominant / total_annotations >= 0.9:
            advisories.append("类别标注高度集中；训练前应确认这符合真实业务分布。")

    widths = [width for width, _height in known_dimensions]
    heights = [height for _width, height in known_dimensions]
    return {
        "schema_version": "1.0",
        "asset_count": asset_count,
        "split_counts": split_counts,
        "annotated_asset_count": annotated_asset_count,
        "unannotated_asset_count": asset_count - annotated_asset_count,
        "annotation_coverage_percent": round(
            (annotated_asset_count / asset_count * 100) if asset_count else 0,
            1,
        ),
        "class_distribution": class_distribution,
        "image_dimensions": {
            "known_asset_count": len(known_dimensions),
            "unknown_asset_count": asset_count - len(known_dimensions),
            "min_width": min(widths) if widths else None,
            "max_width": max(widths) if widths else None,
            "min_height": min(heights) if heights else None,
            "max_height": max(heights) if heights else None,
        },
        "advisories": advisories,
    }


def register_annotation(
    session: Session,
    storage: Storage,
    workspace_id: UUID,
    dataset_id: UUID,
    asset_id: UUID,
    payload: AnnotationRegister,
) -> dict[str, Any]:
    asset, item = require_dataset_item(session, workspace_id, dataset_id, asset_id)
    expected_prefix = (
        f"workspaces/{workspace_id}/datasets/{dataset_id}/annotations/{asset_id}/"
    )
    if not payload.object_key.startswith(expected_prefix):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="object_key does not belong to this dataset item",
        )
    if not storage.verify_object(
        payload.object_key,
        payload.byte_size,
        payload.checksum_sha256,
    ):
        raise conflict("Uploaded annotation is missing or does not match its checksum")
    annotation_uri = storage.uri_for(payload.object_key)
    parse_yolo_detection_annotation(storage.get_bytes(annotation_uri))
    item.annotation_uri = annotation_uri
    session.flush()
    return asset_item_response(asset, item)


def asset_item_response(asset: Asset, item: DatasetItem) -> dict[str, Any]:
    return {
        "id": asset.id,
        "workspace_id": asset.workspace_id,
        "uri": asset.uri,
        "media_type": asset.media_type,
        "checksum_sha256": asset.checksum_sha256,
        "byte_size": asset.byte_size,
        "width": asset.width,
        "height": asset.height,
        "created_at": asset.created_at,
        "split": item.split,
        "annotation_uri": item.annotation_uri,
        "reused": False,
    }


def freeze_dataset(
    session: Session,
    storage: Storage,
    workspace_id: UUID,
    dataset_id: UUID,
    payload: FreezeDatasetVersion,
) -> DatasetVersion:
    dataset = require_dataset(session, workspace_id, dataset_id)
    class_map = resolve_dataset_class_map(session, dataset, payload.class_map)
    pending_task = session.scalar(
        select(AnnotationTask)
        .where(
            AnnotationTask.dataset_id == dataset_id,
            AnnotationTask.status != "done",
        )
        .order_by(AnnotationTask.created_at.asc())
        .limit(1)
    )
    if pending_task is not None:
        task_name = pending_task.name
        task_status = pending_task.status
        status_label = {"annotating": "标注中", "review": "待检查"}.get(
            task_status,
            "未完成",
        )
        raise conflict(f"标注任务「{task_name}」仍处于{status_label}，完成检查后才能冻结数据版本")
    rows = list(
        session.execute(
            select(DatasetItem, Asset)
            .join(Asset, Asset.id == DatasetItem.asset_id)
            .where(
                DatasetItem.dataset_id == dataset_id,
                DatasetItem.item_role == "training_asset",
            )
            .order_by(Asset.checksum_sha256)
        )
    )
    if not rows:
        raise conflict("Dataset must contain at least one asset before freezing")

    project = session.get(Project, dataset.project_id)
    if project is None:
        raise not_found("Project")
    if project.task_type == "object-detection":
        validate_detection_dataset(storage, rows, class_map)

    current_version = session.scalar(
        select(func.max(DatasetVersion.version_number)).where(
            DatasetVersion.dataset_id == dataset_id
        )
    )
    version_number = (current_version or 0) + 1
    assets: list[dict[str, Any]] = []
    for item, asset in rows:
        assets.append(
            {
                "asset_id": str(asset.id),
                "uri": asset.uri,
                "media_type": asset.media_type,
                "checksum_sha256": asset.checksum_sha256,
                "byte_size": asset.byte_size,
                "width": asset.width,
                "height": asset.height,
                "split": item.split,
                "annotation_uri": item.annotation_uri,
            }
        )

    manifest = {
        "schema_version": "1.0",
        "workspace_id": str(workspace_id),
        "project_id": str(dataset.project_id),
        "dataset_id": str(dataset_id),
        "version": version_number,
        "created_at": datetime.now(UTC).isoformat(),
        "class_map": class_map,
        "assets": assets,
        "quality_report": build_dataset_quality_report(storage, assets, class_map),
    }
    manifest_key = (
        f"workspaces/{workspace_id}/datasets/{dataset_id}/"
        f"versions/v{version_number}/manifest.json"
    )
    manifest_uri = storage.put_json(manifest_key, manifest)
    version = DatasetVersion(
        dataset_id=dataset_id,
        version_number=version_number,
        status="frozen",
        manifest_uri=manifest_uri,
        asset_count=len(assets),
        class_map=class_map,
        frozen_at=datetime.now(UTC),
    )
    session.add(version)
    session.flush()
    return version


def validate_detection_dataset(
    storage: Storage,
    rows: list[Any],
    class_map: dict[str, str],
) -> None:
    if not class_map:
        raise conflict("目标检测数据版本至少需要定义一个类别")
    splits = {item.split for item, _asset in rows if item.split}
    if "train" not in splits or "valid" not in splits:
        raise conflict("目标检测数据版本必须同时包含训练集和验证集")
    allowed_class_ids = {int(key) for key in class_map}
    for item, asset in rows:
        if item.split not in {"train", "valid", "test"}:
            raise conflict(f"资产 {asset.id} 尚未划分数据用途")
        if not item.annotation_uri:
            raise conflict(f"资产 {asset.id} 尚未导入 YOLO 标注")
        try:
            body = storage.get_bytes(item.annotation_uri)
        except (OSError, ValueError) as error:
            raise conflict(f"资产 {asset.id} 的标注文件无法读取") from error
        parse_yolo_detection_annotation(body, allowed_class_ids)


def list_versions(
    session: Session,
    workspace_id: UUID,
    dataset_id: UUID,
) -> list[DatasetVersion]:
    require_dataset(session, workspace_id, dataset_id)
    statement = (
        select(DatasetVersion)
        .where(DatasetVersion.dataset_id == dataset_id)
        .order_by(DatasetVersion.version_number.desc())
    )
    return list(session.scalars(statement).all())


def get_dataset_version_quality_report(
    session: Session,
    storage: Storage,
    workspace_id: UUID,
    version_id: UUID,
) -> dict[str, Any]:
    version = session.scalar(
        select(DatasetVersion)
        .join(Dataset, Dataset.id == DatasetVersion.dataset_id)
        .join(Project, Project.id == Dataset.project_id)
        .where(DatasetVersion.id == version_id, Project.workspace_id == workspace_id)
    )
    if version is None:
        raise not_found("Dataset version")
    try:
        manifest = storage.get_json(version.manifest_uri)
    except (OSError, ValueError, KeyError) as error:
        raise conflict("无法读取数据版本的不可变清单") from error
    quality_report = manifest.get("quality_report")
    if not isinstance(quality_report, dict):
        assets = manifest.get("assets")
        class_map = manifest.get("class_map")
        if not isinstance(assets, list) or not isinstance(class_map, dict):
            raise conflict("数据版本的不可变清单格式不正确")
        quality_report = build_dataset_quality_report(storage, assets, class_map)
    return {"dataset_version_id": version.id, **quality_report}
