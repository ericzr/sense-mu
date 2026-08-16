import json
from pathlib import Path

import pytest

from sensemu_worker.dataset import (
    DatasetPreflightError,
    prepare_detection_acceptance_dataset,
    prepare_detection_dataset,
)


class FakeStore:
    def __init__(self) -> None:
        self.objects = {
            "local://train.jpg": b"train-image",
            "local://train.txt": b"0 0.5 0.5 0.2 0.2\n",
            "local://valid.jpg": b"valid-image",
            "local://valid.txt": b"0 0.4 0.4 0.1 0.1\n",
        }

    def materialize(self, uri: str, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(self.objects[uri])


def manifest() -> dict:
    return {
        "class_map": {"0": "helmet"},
        "assets": [
            {
                "asset_id": "train-1",
                "uri": "local://train.jpg",
                "annotation_uri": "local://train.txt",
                "split": "train",
            },
            {
                "asset_id": "valid-1",
                "uri": "local://valid.jpg",
                "annotation_uri": "local://valid.txt",
                "split": "valid",
            },
        ],
    }


def test_prepare_detection_dataset_materializes_frozen_inputs(tmp_path: Path) -> None:
    prepared = prepare_detection_dataset(manifest(), FakeStore(), tmp_path)

    assert prepared.train_count == 1
    assert prepared.validation_count == 1
    assert (prepared.root / "images/train/train-1.jpg").read_bytes() == b"train-image"
    assert (prepared.root / "labels/valid/valid-1.txt").is_file()
    data = json.loads(prepared.data_file.read_text())
    assert data["names"] == ["helmet"]
    assert data["path"] == "/tmp/sensemu-workspace/dataset"


def test_prepare_detection_dataset_rejects_missing_annotations(tmp_path: Path) -> None:
    invalid = manifest()
    invalid["assets"][0]["annotation_uri"] = None

    with pytest.raises(DatasetPreflightError, match="缺少 YOLO 标注"):
        prepare_detection_dataset(invalid, FakeStore(), tmp_path)


def test_prepare_detection_dataset_requires_validation_split(tmp_path: Path) -> None:
    invalid = manifest()
    invalid["assets"] = invalid["assets"][:1]

    with pytest.raises(DatasetPreflightError, match="验证集"):
        prepare_detection_dataset(invalid, FakeStore(), tmp_path)


def test_prepare_acceptance_dataset_prefers_test_split(tmp_path: Path) -> None:
    acceptance_manifest = manifest()
    acceptance_manifest["assets"][0]["split"] = "test"

    prepared = prepare_detection_acceptance_dataset(
        acceptance_manifest,
        FakeStore(),
        tmp_path,
    )

    assert prepared.asset_count == 1
    assert prepared.source_split == "test"
    assert (prepared.root / "images/acceptance/train-1.jpg").is_file()
    data = json.loads(prepared.data_file.read_text())
    assert data["train"] == "images/acceptance"
    assert data["val"] == "images/acceptance"


def test_prepare_acceptance_dataset_requires_evaluation_split(tmp_path: Path) -> None:
    invalid = manifest()
    invalid["assets"] = invalid["assets"][:1]

    with pytest.raises(DatasetPreflightError, match="测试集或验证集"):
        prepare_detection_acceptance_dataset(invalid, FakeStore(), tmp_path)
