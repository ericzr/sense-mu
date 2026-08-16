"""Create an explicit, idempotent local-only project for product demonstrations."""

import json
import os
import struct
import zlib
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from uuid import uuid4

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from sensemu_api import catalog_service
from sensemu_api.catalog_schemas import FreezeDatasetVersion, ProjectCreate
from sensemu_api.config import get_settings
from sensemu_api.db.models import (
    Asset,
    Dataset,
    DatasetItem,
    DatasetVersion,
    Model,
    ModelVersion,
    Project,
    Run,
    RunEvent,
    Workspace,
)
from sensemu_api.storage import get_storage

DEMO_PROJECT_SLUG = "ppe-training-demo"
DEMO_PROJECT_NAME = "PPE 安全检测演示"
DEMO_DATASET_NAME = "工地安全穿戴演示集"
DEMO_MODEL_NAME = "PPE 安全穿戴演示模型"
DEMO_COMPARISON_RUN_KEY = "local-demo-training-v2"
DEMO_CLASS_MAP = {"0": "人员", "1": "安全帽", "2": "反光衣"}


def _png_chunk(kind: bytes, payload: bytes) -> bytes:
    return (
        struct.pack(">I", len(payload))
        + kind
        + payload
        + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)
    )


def demo_image(index: int, *, width: int = 640, height: int = 360) -> bytes:
    """Make a compact valid PNG with a simple synthetic construction-site scene."""
    raw = bytearray()
    person_x = 190 + (index % 5) * 52
    person_y = 130 + (index % 3) * 12
    for y in range(height):
        raw.append(0)
        for x in range(width):
            if y < 210:
                color = (202 - y // 9, 221 - y // 12, 228 - y // 14)
            else:
                color = (166, 158, 141)
            if 50 < x < 118 and 55 < y < 248:
                color = (111, 121, 126)
            if person_x - 18 < x < person_x + 18 and person_y - 23 < y < person_y + 39:
                color = (242, 170, 45) if y < person_y - 2 else (65, 75, 80)
            if person_x - 24 < x < person_x + 24 and person_y + 3 < y < person_y + 53:
                color = (228, 113, 44)
            if 420 < x < 580 and 86 < y < 103:
                color = (238, 178, 57)
            if 600 < x < 620 and 18 + (index % 6) * 7 < y < 23 + (index % 6) * 7:
                color = (34 + index * 7, 68 + index * 5, 90 + index * 3)
            raw.extend(color)
    header = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return header + _png_chunk(b"IHDR", ihdr) + _png_chunk(b"IDAT", zlib.compress(bytes(raw), 9)) + _png_chunk(b"IEND", b"")


def annotation_for(index: int) -> bytes:
    person_x = 0.35 + (index % 5) * 0.08
    return (
        f"0 {person_x:.3f} 0.560 0.120 0.360\n"
        f"1 {person_x:.3f} 0.360 0.080 0.090\n"
        f"2 {person_x:.3f} 0.590 0.140 0.180\n"
    ).encode()


def training_results_csv(
    *,
    precision: float = 0.91,
    recall: float = 0.87,
    map50: float = 0.89,
    map5095: float = 0.67,
) -> bytes:
    rows = [
        "epoch,train/box_loss,train/cls_loss,val/box_loss,metrics/precision(B),metrics/recall(B),metrics/mAP50(B),metrics/mAP50-95(B)"
    ]
    for epoch in range(12):
        progress = epoch / 11
        rows.append(
            ",".join(
                [
                    str(epoch),
                    f"{1.18 - progress * 0.52:.4f}",
                    f"{0.84 - progress * 0.39:.4f}",
                    f"{1.09 - progress * 0.44:.4f}",
                    f"{precision - 0.30 + progress * 0.30:.4f}",
                    f"{recall - 0.29 + progress * 0.29:.4f}",
                    f"{map50 - 0.37 + progress * 0.37:.4f}",
                    f"{map5095 - 0.31 + progress * 0.31:.4f}",
                ]
            )
        )
    return ("\n".join(rows) + "\n").encode()


def demo_workspace(session: Session) -> Workspace:
    workspace = session.scalar(select(Workspace).order_by(Workspace.created_at).limit(1))
    if workspace is None:
        raise RuntimeError("请先通过本地页面创建工作区，再写入演示数据")
    return workspace


def ensure_demo_project(session: Session, workspace: Workspace) -> Project:
    project = session.scalar(
        select(Project).where(
            Project.workspace_id == workspace.id,
            Project.slug == DEMO_PROJECT_SLUG,
        )
    )
    if project is None:
        project = catalog_service.create_project(
            session,
            workspace.id,
            ProjectCreate(
                slug=DEMO_PROJECT_SLUG,
                name=DEMO_PROJECT_NAME,
                task_type="object-detection",
                description="本地演示数据：用于查看数据、训练与报告界面，不代表真实训练或验收。",
            ),
        )
    return project


def ensure_demo_dataset(session: Session, storage, workspace: Workspace, project: Project) -> Dataset:
    dataset = session.scalar(
        select(Dataset).where(
            Dataset.project_id == project.id,
            Dataset.name == DEMO_DATASET_NAME,
        )
    )
    if dataset is None:
        dataset = Dataset(
            project_id=project.id,
            name=DEMO_DATASET_NAME,
            description="18 张合成工地画面，已预置人员、安全帽和反光衣标注，仅用于本地演示。",
            class_map=DEMO_CLASS_MAP,
        )
        session.add(dataset)
        session.flush()

    has_assets = session.scalar(
        select(DatasetItem.id)
        .where(DatasetItem.dataset_id == dataset.id, DatasetItem.item_role == "training_asset")
        .limit(1)
    )
    if has_assets is not None:
        return dataset

    for index in range(18):
        image = demo_image(index)
        checksum = sha256(image).hexdigest()
        asset_key = f"workspaces/{workspace.id}/datasets/{dataset.id}/demo-assets/ppe-{index + 1:02d}.png"
        annotation_key = f"workspaces/{workspace.id}/datasets/{dataset.id}/demo-annotations/ppe-{index + 1:02d}.txt"
        asset = session.scalar(
            select(Asset).where(
                Asset.workspace_id == workspace.id,
                Asset.checksum_sha256 == checksum,
            )
        )
        if asset is None:
            asset = Asset(
                workspace_id=workspace.id,
                uri=storage.put_bytes(asset_key, image, "image/png"),
                media_type="image/png",
                checksum_sha256=checksum,
                byte_size=len(image),
                width=640,
                height=360,
            )
            session.add(asset)
            session.flush()
        split = "train" if index < 12 else "valid" if index < 16 else "test"
        session.add(
            DatasetItem(
                dataset_id=dataset.id,
                asset_id=asset.id,
                split=split,
                annotation_uri=storage.put_bytes(annotation_key, annotation_for(index), "text/plain"),
            )
        )
    session.flush()
    return dataset


def ensure_demo_version(
    session: Session,
    storage,
    workspace: Workspace,
    dataset: Dataset,
) -> DatasetVersion:
    existing = session.scalar(
        select(DatasetVersion)
        .where(DatasetVersion.dataset_id == dataset.id)
        .order_by(DatasetVersion.version_number.desc())
        .limit(1)
    )
    if existing is not None:
        return existing
    return catalog_service.freeze_dataset(
        session,
        storage,
        workspace.id,
        dataset.id,
        FreezeDatasetVersion(class_map=DEMO_CLASS_MAP),
    )


def ensure_demo_training(session: Session, storage, workspace: Workspace, project: Project, version) -> Run:
    run = session.scalar(
        select(Run).where(
            Run.project_id == project.id,
            Run.idempotency_key == "local-demo-training-v1",
        )
    )
    if run is not None:
        return run

    now = datetime.now(UTC)
    run = Run(
        project_id=project.id,
        dataset_version_id=version.id,
        run_type="model.train",
        status="succeeded",
        engine="ultralytics",
        executor="local-demo",
        idempotency_key="local-demo-training-v1",
        recipe={"model": "YOLO11s · 演示", "epochs": 12, "image_size": 640, "batch_size": 8, "seed": 42},
        progress=100,
        started_at=now - timedelta(minutes=8),
        finished_at=now - timedelta(minutes=2),
        heartbeat_at=now - timedelta(minutes=2),
    )
    session.add(run)
    session.flush()
    prefix = f"workspaces/{workspace.id}/projects/{project.id}/runs/{run.id}"
    run.artifact_prefix = prefix
    storage.put_bytes(f"{prefix}/metrics/results.csv", training_results_csv(), "text/csv")
    model_uri = storage.put_bytes(
        f"{prefix}/model/best.pt",
        b"SenseMu local demo artifact only; not a deployable model.\n",
        "application/octet-stream",
    )
    model = session.scalar(select(Model).where(Model.project_id == project.id, Model.name == DEMO_MODEL_NAME))
    if model is None:
        model = Model(project_id=project.id, name=DEMO_MODEL_NAME, task_type="object-detection")
        session.add(model)
        session.flush()
    session.add(
        ModelVersion(
            model_id=model.id,
            run_id=run.id,
            version_number=1,
            status="candidate",
            artifact_uri=model_uri,
            metrics={
                "metrics/mAP50(B)": 0.89,
                "metrics/mAP50-95(B)": 0.67,
                "metrics/precision(B)": 0.91,
                "metrics/recall(B)": 0.87,
            },
        )
    )
    events = [
        ("job.queued", 0, now - timedelta(minutes=9)),
        ("job.preparing", 0, now - timedelta(minutes=8)),
        ("job.started", 0, now - timedelta(minutes=8)),
        ("job.progressed", 42, now - timedelta(minutes=6)),
        ("job.progressed", 84, now - timedelta(minutes=3)),
        ("job.succeeded", 100, now - timedelta(minutes=2)),
    ]
    for sequence, (event_type, progress, occurred_at) in enumerate(events, start=1):
        session.add(
            RunEvent(
                run_id=run.id,
                event_id=uuid4(),
                sequence=sequence,
                event_type=event_type,
                status="succeeded" if event_type == "job.succeeded" else "running",
                progress=progress,
                payload={"source": "local_demo"},
                occurred_at=occurred_at,
            )
        )
    session.flush()
    return run


def ensure_demo_comparison_training(
    session: Session,
    storage,
    workspace: Workspace,
    project: Project,
    version: DatasetVersion,
) -> Run:
    run = session.scalar(
        select(Run).where(
            Run.project_id == project.id,
            Run.idempotency_key == DEMO_COMPARISON_RUN_KEY,
        )
    )
    if run is not None:
        return run

    now = datetime.now(UTC)
    run = Run(
        project_id=project.id,
        dataset_version_id=version.id,
        run_type="model.train",
        status="succeeded",
        engine="ultralytics",
        executor="local-demo",
        idempotency_key=DEMO_COMPARISON_RUN_KEY,
        recipe={"model": "YOLO11n · 演示", "epochs": 10, "image_size": 640, "batch_size": 8, "seed": 7},
        progress=100,
        started_at=now - timedelta(minutes=22),
        finished_at=now - timedelta(minutes=14),
        heartbeat_at=now - timedelta(minutes=14),
    )
    session.add(run)
    session.flush()
    prefix = f"workspaces/{workspace.id}/projects/{project.id}/runs/{run.id}"
    run.artifact_prefix = prefix
    storage.put_bytes(
        f"{prefix}/metrics/results.csv",
        training_results_csv(precision=0.88, recall=0.84, map50=0.86, map5095=0.64),
        "text/csv",
    )
    model_uri = storage.put_bytes(
        f"{prefix}/model/best.pt",
        b"SenseMu local demo artifact only; not a deployable model.\n",
        "application/octet-stream",
    )
    model = session.scalar(select(Model).where(Model.project_id == project.id, Model.name == DEMO_MODEL_NAME))
    if model is None:
        raise RuntimeError("演示主模型缺失")
    session.add(
        ModelVersion(
            model_id=model.id,
            run_id=run.id,
            version_number=2,
            status="candidate",
            artifact_uri=model_uri,
            metrics={
                "metrics/mAP50(B)": 0.86,
                "metrics/mAP50-95(B)": 0.64,
                "metrics/precision(B)": 0.88,
                "metrics/recall(B)": 0.84,
            },
        )
    )
    events = [
        ("job.queued", 0, now - timedelta(minutes=23)),
        ("job.preparing", 0, now - timedelta(minutes=22)),
        ("job.started", 0, now - timedelta(minutes=22)),
        ("job.progressed", 51, now - timedelta(minutes=19)),
        ("job.succeeded", 100, now - timedelta(minutes=14)),
    ]
    for sequence, (event_type, progress, occurred_at) in enumerate(events, start=1):
        session.add(
            RunEvent(
                run_id=run.id,
                event_id=uuid4(),
                sequence=sequence,
                event_type=event_type,
                status="succeeded" if event_type == "job.succeeded" else "running",
                progress=progress,
                payload={"source": "local_demo"},
                occurred_at=occurred_at,
            )
        )
    session.flush()
    return run


def main() -> None:
    settings = get_settings()
    if settings.environment != "development" or settings.object_storage_endpoint != "local://":
        raise RuntimeError("演示数据只能写入 development + local:// 的本地环境")
    if not settings.database_url.startswith("sqlite"):
        raise RuntimeError("演示数据只能写入本地 SQLite 数据库")
    if os.environ.get("SENSEMU_DATABASE_URL") is None:
        raise RuntimeError("请通过 make seed-demo 执行，不直接连接默认数据库")

    storage = get_storage()
    engine = create_engine(settings.database_url)
    with Session(engine) as session:
        workspace = demo_workspace(session)
        project = ensure_demo_project(session, workspace)
        dataset = ensure_demo_dataset(session, storage, workspace, project)
        version = ensure_demo_version(session, storage, workspace, dataset)
        run = ensure_demo_training(session, storage, workspace, project, version)
        comparison_run = ensure_demo_comparison_training(session, storage, workspace, project, version)
        session.commit()
        print(
            json.dumps(
                {
                    "workspace_id": str(workspace.id),
                    "project_id": str(project.id),
                    "dataset_id": str(dataset.id),
                    "dataset_version_id": str(version.id),
                    "run_id": str(run.id),
                    "comparison_run_id": str(comparison_run.id),
                    "studio_url": f"http://localhost:3000/studio?project={project.id}",
                    "data_url": f"http://localhost:3000/studio/data?project={project.id}&dataset={dataset.id}",
                    "training_url": f"http://localhost:3000/studio/training/runs/{run.id}?project={project.id}",
                },
                ensure_ascii=False,
            )
        )


if __name__ == "__main__":
    main()
