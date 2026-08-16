import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from sensemu_worker.object_store import ObjectStore


class DatasetPreflightError(ValueError):
    pass


@dataclass(frozen=True)
class PreparedDataset:
    root: Path
    data_file: Path
    train_count: int
    validation_count: int


@dataclass(frozen=True)
class PreparedAcceptanceDataset:
    root: Path
    data_file: Path
    asset_count: int
    source_split: str


def _file_suffix(uri: str) -> str:
    suffix = Path(urlparse(uri).path).suffix.lower()
    return suffix if suffix in {".jpg", ".jpeg", ".png", ".webp", ".bmp"} else ".jpg"


def _class_names(class_map: Any) -> list[str]:
    if not isinstance(class_map, dict) or not class_map:
        raise DatasetPreflightError("数据版本缺少类别定义")
    try:
        ordered = sorted(((int(key), str(value)) for key, value in class_map.items()))
    except (TypeError, ValueError) as error:
        raise DatasetPreflightError("类别编号必须是连续整数") from error
    if [index for index, _ in ordered] != list(range(len(ordered))):
        raise DatasetPreflightError("类别编号必须从 0 开始且连续")
    return [name for _, name in ordered]


def prepare_detection_dataset(
    manifest: dict[str, Any],
    store: ObjectStore,
    workspace: Path,
) -> PreparedDataset:
    assets = manifest.get("assets")
    if not isinstance(assets, list) or not assets:
        raise DatasetPreflightError("数据版本中没有资产")
    names = _class_names(manifest.get("class_map"))
    dataset_root = workspace / "dataset"
    split_counts = {"train": 0, "valid": 0}

    for asset in assets:
        if not isinstance(asset, dict):
            raise DatasetPreflightError("数据 manifest 格式不正确")
        split = "valid" if asset.get("split") in {"valid", "val"} else asset.get("split")
        if split not in split_counts:
            continue
        asset_id = str(asset.get("asset_id", "")).strip()
        image_uri = str(asset.get("uri", ""))
        annotation_uri = asset.get("annotation_uri")
        if not asset_id or not image_uri:
            raise DatasetPreflightError("数据资产缺少标识或对象地址")
        if not annotation_uri:
            raise DatasetPreflightError(f"资产 {asset_id} 缺少 YOLO 标注")

        image_path = dataset_root / "images" / split / f"{asset_id}{_file_suffix(image_uri)}"
        label_path = dataset_root / "labels" / split / f"{asset_id}.txt"
        store.materialize(image_uri, image_path)
        store.materialize(str(annotation_uri), label_path)
        split_counts[split] += 1

    if split_counts["train"] == 0:
        raise DatasetPreflightError("数据版本缺少训练集")
    if split_counts["valid"] == 0:
        raise DatasetPreflightError("数据版本缺少独立验证集")

    data_file = dataset_root / "data.yaml"
    data_file.write_text(
        json.dumps(
            {
                "path": "/tmp/sensemu-workspace/dataset",
                "train": "images/train",
                "val": "images/valid",
                "names": names,
            },
            ensure_ascii=False,
        )
    )
    return PreparedDataset(
        root=dataset_root,
        data_file=data_file,
        train_count=split_counts["train"],
        validation_count=split_counts["valid"],
    )


def prepare_detection_acceptance_dataset(
    manifest: dict[str, Any],
    store: ObjectStore,
    workspace: Path,
) -> PreparedAcceptanceDataset:
    assets = manifest.get("assets")
    if not isinstance(assets, list) or not assets:
        raise DatasetPreflightError("验收数据版本中没有资产")
    names = _class_names(manifest.get("class_map"))
    available_splits = {
        "valid" if asset.get("split") == "val" else asset.get("split")
        for asset in assets
        if isinstance(asset, dict)
    }
    source_split = "test" if "test" in available_splits else "valid"
    dataset_root = workspace / "dataset"
    count = 0

    for asset in assets:
        if not isinstance(asset, dict):
            raise DatasetPreflightError("数据 manifest 格式不正确")
        split = "valid" if asset.get("split") == "val" else asset.get("split")
        if split != source_split:
            continue
        asset_id = str(asset.get("asset_id", "")).strip()
        image_uri = str(asset.get("uri", ""))
        annotation_uri = asset.get("annotation_uri")
        if not asset_id or not image_uri:
            raise DatasetPreflightError("验收数据资产缺少标识或对象地址")
        if not annotation_uri:
            raise DatasetPreflightError(f"验收资产 {asset_id} 缺少 YOLO 标注")
        image_path = dataset_root / "images" / "acceptance" / (
            f"{asset_id}{_file_suffix(image_uri)}"
        )
        label_path = dataset_root / "labels" / "acceptance" / f"{asset_id}.txt"
        store.materialize(image_uri, image_path)
        store.materialize(str(annotation_uri), label_path)
        count += 1

    if count == 0:
        raise DatasetPreflightError("验收数据版本必须包含测试集或验证集")
    data_file = dataset_root / "data.yaml"
    data_file.write_text(
        json.dumps(
            {
                "path": "/tmp/sensemu-workspace/dataset",
                # Ultralytics requires both keys even when acceptance only evaluates `val`.
                "train": "images/acceptance",
                "val": "images/acceptance",
                "names": names,
            },
            ensure_ascii=False,
        )
    )
    return PreparedAcceptanceDataset(
        root=dataset_root,
        data_file=data_file,
        asset_count=count,
        source_split=source_split,
    )
