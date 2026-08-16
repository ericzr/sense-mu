from pathlib import Path

from sensemu_worker.executor import (
    architecture_mismatch,
    build_yolo_class_metrics_command,
    build_yolo_command,
    build_yolo_evaluation_command,
    progress_from_log,
    read_json_metrics,
    read_metrics,
)


def recipe() -> dict:
    return {
        "model": "yolo26s.pt",
        "epochs": 100,
        "image_size": 640,
        "batch_size": 16,
        "seed": 42,
    }


def test_build_yolo_command_uses_only_validated_recipe_values() -> None:
    command = build_yolo_command(recipe(), use_gpu=False)

    assert command[:3] == ["yolo", "detect", "train"]
    assert "model=yolo26s.pt" in command
    assert "device=cpu" in command
    assert "project=/tmp/sensemu-workspace/output" in command


def test_architecture_mismatch_requires_an_explicit_local_opt_in() -> None:
    assert architecture_mismatch("amd64", "arm64") is True
    assert architecture_mismatch("x86_64", "aarch64") is True
    assert architecture_mismatch("amd64", "amd64") is False
    assert architecture_mismatch("", "arm64") is False


def test_progress_is_derived_from_epoch_log_not_invented() -> None:
    assert progress_from_log("      40/100      3.2G", 100) == 40
    assert progress_from_log("Downloading 40/120 MB", 100) is None
    assert progress_from_log("100/100 complete", 100) == 99


def test_read_metrics_uses_last_real_results_row(tmp_path: Path) -> None:
    results = tmp_path / "results.csv"
    results.write_text(
        "epoch,metrics/mAP50(B),metrics/precision(B)\n"
        "1,0.40,0.50\n"
        "2,0.82,0.91\n"
    )

    assert read_metrics(results) == {
        "epoch": 2.0,
        "metrics/mAP50(B)": 0.82,
        "metrics/precision(B)": 0.91,
    }


def test_build_evaluation_command_uses_frozen_local_inputs() -> None:
    command = build_yolo_evaluation_command(recipe(), use_gpu=False)

    assert command[:2] == ["python", "-c"]
    assert "model.pt" in command[2]
    assert "data.yaml" in command[2]
    assert "imgsz=640" in command[2]
    assert "device='cpu'" in command[2]


def test_build_class_metrics_command_writes_only_real_validation_values() -> None:
    command = build_yolo_class_metrics_command(recipe(), use_gpu=False)

    assert command[:2] == ["python", "-c"]
    assert "model.pt" in command[2]
    assert "data.yaml" in command[2]
    assert "ap50" in command[2]
    assert "class_metrics.json" in command[2]
    assert "device='cpu'" in command[2]
    compile(command[2], "class-metrics-command", "exec")


def test_read_json_metrics_keeps_only_numeric_results(tmp_path: Path) -> None:
    metrics_file = tmp_path / "metrics.json"
    metrics_file.write_text(
        '{"metrics/mAP50(B)": 0.84, "metrics/recall(B)": 0.77, "note": "real"}'
    )

    assert read_json_metrics(metrics_file) == {
        "metrics/mAP50(B)": 0.84,
        "metrics/recall(B)": 0.77,
    }
