import csv
import io
import json
import queue
import re
import tarfile
import threading
import time
from collections import deque
from collections.abc import Callable
from pathlib import Path
from typing import Any

import docker
from docker.errors import APIError, DockerException, ImageNotFound, NotFound
from docker.models.containers import Container
from docker.types import DeviceRequest

from sensemu_worker.config import WorkerSettings
from sensemu_worker.dataset import PreparedAcceptanceDataset, PreparedDataset


class DockerUnavailableError(RuntimeError):
    pass


class TrainingExecutionError(RuntimeError):
    pass


class TrainingCancelledError(RuntimeError):
    pass


def _normalize_architecture(value: str) -> str:
    aliases = {
        "aarch64": "arm64",
        "x86_64": "amd64",
    }
    return aliases.get(value.strip().lower(), value.strip().lower())


def architecture_mismatch(image_architecture: str, host_architecture: str) -> bool:
    """Return whether two known Docker architectures cannot run natively together."""

    image = _normalize_architecture(image_architecture)
    host = _normalize_architecture(host_architecture)
    return bool(image and host and image != host)


def build_yolo_command(recipe: dict[str, Any], *, use_gpu: bool) -> list[str]:
    return [
        "yolo",
        "detect",
        "train",
        f"model={recipe['model']}",
        "data=/tmp/sensemu-workspace/dataset/data.yaml",
        f"epochs={int(recipe['epochs'])}",
        f"imgsz={int(recipe['image_size'])}",
        f"batch={int(recipe['batch_size'])}",
        f"seed={int(recipe['seed'])}",
        f"device={'0' if use_gpu else 'cpu'}",
        "project=/tmp/sensemu-workspace/output",
        "name=train",
        "exist_ok=True",
        "plots=True",
        "verbose=True",
    ]


def build_yolo_evaluation_command(recipe: dict[str, Any], *, use_gpu: bool) -> list[str]:
    script = (
        "import json; from pathlib import Path; from ultralytics import YOLO; "
        "result=YOLO('/tmp/sensemu-workspace/model.pt').val("
        "data='/tmp/sensemu-workspace/dataset/data.yaml', split='val', "
        f"imgsz={int(recipe['image_size'])}, batch={int(recipe['batch_size'])}, "
        f"device={'0' if use_gpu else repr('cpu')}, plots=False, verbose=True); "
        "metrics={str(key): float(value) for key, value in result.results_dict.items()}; "
        "Path('/tmp/sensemu-workspace/output').mkdir(parents=True, exist_ok=True); "
        "Path('/tmp/sensemu-workspace/output/metrics.json').write_text(json.dumps(metrics))"
    )
    return ["python", "-c", script]


def build_yolo_class_metrics_command(recipe: dict[str, Any], *, use_gpu: bool) -> list[str]:
    script = "\n".join(
        [
            "import json, math",
            "from pathlib import Path",
            "from ultralytics import YOLO",
            "result = YOLO('/tmp/sensemu-workspace/model.pt').val(",
            "    data='/tmp/sensemu-workspace/dataset/data.yaml', split='val',",
            f"    imgsz={int(recipe['image_size'])}, batch={int(recipe['batch_size'])},",
            f"    device={'0' if use_gpu else repr('cpu')}, plots=False, verbose=False,",
            ")",
            "box = result.box",
            "names = getattr(result, 'names', {}) or {}",
            "indices = list(getattr(box, 'ap_class_index', []))",
            "def number(name, position):",
            "    values = getattr(box, name, [])",
            "    try: value = float(values[position])",
            "    except (IndexError, TypeError, ValueError): return None",
            "    return value if math.isfinite(value) else None",
            "def label(index):",
            "    if isinstance(names, dict): return str(names.get(index, index))",
            "    try: return str(names[index])",
            "    except (IndexError, TypeError): return str(index)",
            "classes = [{",
            "    'id': int(index), 'name': label(int(index)),",
            "    'precision': number('p', position), 'recall': number('r', position),",
            "    'map50': number('ap50', position), 'map50_95': number('ap', position),",
            "} for position, index in enumerate(indices)]",
            "output = Path('/tmp/sensemu-workspace/output')",
            "output.mkdir(parents=True, exist_ok=True)",
            "(output / 'class_metrics.json').write_text(json.dumps({'schema_version': 1, 'classes': classes}, ensure_ascii=False))",
        ]
    )
    return ["python", "-c", script]


def progress_from_log(line: str, epochs: int) -> int | None:
    for current, total in re.findall(r"(?<![\d.])(\d{1,4})/(\d{1,4})(?![\d.])", line):
        if int(total) == epochs and 0 < int(current) <= epochs:
            return min(99, int(int(current) / epochs * 100))
    return None


def read_metrics(path: Path) -> dict[str, float]:
    if not path.is_file():
        return {}
    with path.open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    if not rows:
        return {}
    metrics: dict[str, float] = {}
    for key, value in rows[-1].items():
        if value is None:
            continue
        try:
            metrics[key.strip()] = float(value.strip())
        except ValueError:
            continue
    return metrics


TRAINING_VISUALIZATION_FILENAMES = (
    "confusion_matrix.png",
    "confusion_matrix_normalized.png",
)
TRAINING_CLASS_METRICS_FILENAME = "class_metrics.json"


def read_json_metrics(path: Path) -> dict[str, float]:
    if not path.is_file():
        return {}
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict):
        return {}
    metrics: dict[str, float] = {}
    for key, value in payload.items():
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            metrics[str(key)] = float(value)
    return metrics


class DockerUltralyticsExecutor:
    def __init__(self, settings: WorkerSettings, image: str | None = None) -> None:
        self.image = image or settings.docker_image
        self.use_gpu = settings.docker_gpus.lower() not in {"", "none", "false", "0"}
        self.execution_timeout_seconds = max(1, settings.docker_execution_timeout_seconds)
        self.allow_cross_architecture = settings.docker_allow_cross_architecture
        self.client: docker.DockerClient | None = None
        self.resolved_image: str | None = None

    def ensure_available(self) -> str:
        try:
            self.client = docker.from_env()
            self.client.ping()
            try:
                image = self.client.images.get(self.image)
            except ImageNotFound:
                image = self.client.images.pull(self.image)
            image_architecture = str(image.attrs.get("Architecture") or "")
            host_architecture = str(self.client.info().get("Architecture") or "")
            if (
                architecture_mismatch(image_architecture, host_architecture)
                and not self.allow_cross_architecture
            ):
                raise TrainingExecutionError(
                    "Docker 训练镜像架构不匹配："
                    f"镜像为 {image_architecture}，Worker 为 {host_architecture}。"
                    "请切换到原生镜像，或仅在已验证的本地环境设置 "
                    "SENSEMU_DOCKER_ALLOW_CROSS_ARCHITECTURE=true。"
                )
            digests = image.attrs.get("RepoDigests") or []
            self.resolved_image = str(digests[0] if digests else image.id)
            return self.resolved_image
        except DockerException as error:
            raise DockerUnavailableError("Docker 执行器不可用") from error

    @staticmethod
    def _dataset_archive(prepared: PreparedDataset) -> bytes:
        payload = io.BytesIO()
        with tarfile.open(fileobj=payload, mode="w") as archive:
            archive.add(prepared.root, arcname="sensemu-workspace/dataset")
        return payload.getvalue()

    @staticmethod
    def _file_archive(source: Path, arcname: str) -> bytes:
        payload = io.BytesIO()
        with tarfile.open(fileobj=payload, mode="w") as archive:
            archive.add(source, arcname=arcname)
        return payload.getvalue()

    @staticmethod
    def _copy_from_container(container: Container, source: str, destination: Path) -> bool:
        try:
            stream, _ = container.get_archive(source)
        except NotFound:
            return False
        payload = io.BytesIO(b"".join(stream))
        with tarfile.open(fileobj=payload, mode="r") as archive:
            member = next((item for item in archive.getmembers() if item.isfile()), None)
            if member is None:
                return False
            extracted = archive.extractfile(member)
            if extracted is None:
                return False
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(extracted.read())
        return True

    def run(
        self,
        run_id: str,
        prepared: PreparedDataset,
        recipe: dict[str, Any],
        artifact_directory: Path,
        *,
        on_progress: Callable[[int], None],
        should_cancel: Callable[[], bool],
    ) -> tuple[Path, dict[str, float], Path | None, list[Path], Path | None]:
        if self.client is None:
            raise DockerUnavailableError("Docker 执行器尚未初始化")
        container_name = f"sensemu-{run_id[:12]}"
        device_requests = [DeviceRequest(count=-1, capabilities=[["gpu"]])] if self.use_gpu else None
        container: Container | None = None
        log_lines: queue.Queue[str] = queue.Queue()
        log_tail: deque[str] = deque(maxlen=120)

        try:
            try:
                stale = self.client.containers.get(container_name)
                stale.remove(force=True)
            except NotFound:
                pass
            container = self.client.containers.create(
                self.image,
                build_yolo_command(recipe, use_gpu=self.use_gpu),
                name=container_name,
                working_dir="/tmp/sensemu-workspace",
                labels={"sensemu.run_id": run_id, "sensemu.executor": "ultralytics"},
                device_requests=device_requests,
                network_disabled=False,
            )
            container.put_archive("/tmp", self._dataset_archive(prepared))
            container.start()

            def collect_logs() -> None:
                assert container is not None
                try:
                    for chunk in container.logs(stream=True, follow=True):
                        for line in chunk.decode(errors="replace").replace("\r", "\n").splitlines():
                            if line.strip():
                                log_lines.put(line.strip())
                except DockerException as error:
                    log_lines.put(f"Docker log stream failed: {error}")

            log_thread = threading.Thread(target=collect_logs, daemon=True)
            log_thread.start()
            epochs = int(recipe["epochs"])
            reported_progress = 0
            last_cancel_check = 0.0
            deadline = time.monotonic() + self.execution_timeout_seconds

            while True:
                while True:
                    try:
                        line = log_lines.get_nowait()
                    except queue.Empty:
                        break
                    log_tail.append(line)
                    progress = progress_from_log(line, epochs)
                    if progress is not None and progress > reported_progress:
                        reported_progress = progress
                        on_progress(progress)

                now = time.monotonic()
                if now - last_cancel_check >= 3:
                    last_cancel_check = now
                    if should_cancel():
                        container.stop(timeout=10)
                        raise TrainingCancelledError("训练任务已取消")
                container.reload()
                if container.status in {"exited", "dead"}:
                    break
                if now >= deadline:
                    container.stop(timeout=10)
                    raise TrainingExecutionError(
                        f"训练执行超过 {self.execution_timeout_seconds} 秒，已主动停止"
                    )
                time.sleep(0.5)

            log_thread.join(timeout=2)
            exit_code = int(container.attrs.get("State", {}).get("ExitCode") or 0)
            if exit_code != 0:
                message = "\n".join(log_tail)[-4000:]
                raise TrainingExecutionError(message or f"训练容器退出码 {exit_code}")

            artifact_directory.mkdir(parents=True, exist_ok=True)
            model_path = artifact_directory / "best.pt"
            copied = self._copy_from_container(
                container,
                "/tmp/sensemu-workspace/output/train/weights/best.pt",
                model_path,
            )
            if not copied:
                raise TrainingExecutionError("训练完成但未产生 best.pt")
            results_path = artifact_directory / "results.csv"
            has_results = self._copy_from_container(
                container,
                "/tmp/sensemu-workspace/output/train/results.csv",
                results_path,
            )
            visualization_paths: list[Path] = []
            for filename in TRAINING_VISUALIZATION_FILENAMES:
                visualization_path = artifact_directory / filename
                if self._copy_from_container(
                    container,
                    f"/tmp/sensemu-workspace/output/train/{filename}",
                    visualization_path,
                ):
                    visualization_paths.append(visualization_path)
            class_metrics_path = self._run_training_class_metrics(
                run_id,
                prepared,
                model_path,
                recipe,
                artifact_directory,
                should_cancel=should_cancel,
            )
            return (
                model_path,
                read_metrics(results_path),
                results_path if has_results else None,
                visualization_paths,
                class_metrics_path,
            )
        except APIError as error:
            raise TrainingExecutionError(f"Docker 执行失败：{error}") from error
        finally:
            if container is not None:
                try:
                    container.remove(force=True)
                except DockerException:
                    pass

    def _run_training_class_metrics(
        self,
        run_id: str,
        prepared: PreparedDataset,
        model_path: Path,
        recipe: dict[str, Any],
        artifact_directory: Path,
        *,
        should_cancel: Callable[[], bool],
    ) -> Path | None:
        """Run optional per-class validation after training succeeds."""

        if self.client is None:
            return None
        container_name = f"sensemu-classmetrics-{run_id[:12]}"
        device_requests = (
            [DeviceRequest(count=-1, capabilities=[["gpu"]])] if self.use_gpu else None
        )
        container: Container | None = None
        try:
            try:
                stale = self.client.containers.get(container_name)
                stale.remove(force=True)
            except NotFound:
                pass
            container = self.client.containers.create(
                self.image,
                build_yolo_class_metrics_command(recipe, use_gpu=self.use_gpu),
                name=container_name,
                working_dir="/tmp/sensemu-workspace",
                labels={"sensemu.run_id": run_id, "sensemu.executor": "ultralytics"},
                device_requests=device_requests,
                network_disabled=True,
            )
            container.put_archive("/tmp", self._dataset_archive(prepared))
            container.put_archive(
                "/tmp",
                self._file_archive(model_path, "sensemu-workspace/model.pt"),
            )
            container.start()
            deadline = time.monotonic() + self.execution_timeout_seconds
            while True:
                if should_cancel():
                    container.stop(timeout=10)
                    raise TrainingCancelledError("训练任务已取消")
                container.reload()
                if container.status in {"exited", "dead"}:
                    break
                if time.monotonic() >= deadline:
                    container.stop(timeout=10)
                    return None
                time.sleep(0.5)
            if int(container.attrs.get("State", {}).get("ExitCode") or 0) != 0:
                return None
            artifact_directory.mkdir(parents=True, exist_ok=True)
            class_metrics_path = artifact_directory / TRAINING_CLASS_METRICS_FILENAME
            copied = self._copy_from_container(
                container,
                f"/tmp/sensemu-workspace/output/{TRAINING_CLASS_METRICS_FILENAME}",
                class_metrics_path,
            )
            return class_metrics_path if copied else None
        except TrainingCancelledError:
            raise
        except DockerException:
            return None
        finally:
            if container is not None:
                try:
                    container.remove(force=True)
                except DockerException:
                    pass

    def run_evaluation(
        self,
        run_id: str,
        prepared: PreparedAcceptanceDataset,
        model_path: Path,
        recipe: dict[str, Any],
        artifact_directory: Path,
        *,
        should_cancel: Callable[[], bool],
    ) -> tuple[dict[str, float], Path]:
        if self.client is None:
            raise DockerUnavailableError("Docker 执行器尚未初始化")
        container_name = f"sensemu-eval-{run_id[:12]}"
        device_requests = (
            [DeviceRequest(count=-1, capabilities=[["gpu"]])] if self.use_gpu else None
        )
        container: Container | None = None
        try:
            try:
                stale = self.client.containers.get(container_name)
                stale.remove(force=True)
            except NotFound:
                pass
            container = self.client.containers.create(
                self.image,
                build_yolo_evaluation_command(recipe, use_gpu=self.use_gpu),
                name=container_name,
                working_dir="/tmp/sensemu-workspace",
                labels={"sensemu.run_id": run_id, "sensemu.executor": "ultralytics"},
                device_requests=device_requests,
                network_disabled=True,
            )
            container.put_archive("/tmp", self._dataset_archive(prepared))
            container.put_archive(
                "/tmp",
                self._file_archive(model_path, "sensemu-workspace/model.pt"),
            )
            container.start()
            deadline = time.monotonic() + self.execution_timeout_seconds
            while True:
                if should_cancel():
                    container.stop(timeout=10)
                    raise TrainingCancelledError("验收评测任务已取消")
                container.reload()
                if container.status in {"exited", "dead"}:
                    break
                if time.monotonic() >= deadline:
                    container.stop(timeout=10)
                    raise TrainingExecutionError(
                        f"验收评测超过 {self.execution_timeout_seconds} 秒，已主动停止"
                    )
                time.sleep(0.5)
            exit_code = int(container.attrs.get("State", {}).get("ExitCode") or 0)
            if exit_code != 0:
                logs = container.logs(tail=120).decode(errors="replace")[-4000:]
                raise TrainingExecutionError(logs or f"验收容器退出码 {exit_code}")
            artifact_directory.mkdir(parents=True, exist_ok=True)
            metrics_path = artifact_directory / "metrics.json"
            copied = self._copy_from_container(
                container,
                "/tmp/sensemu-workspace/output/metrics.json",
                metrics_path,
            )
            if not copied:
                raise TrainingExecutionError("验收评测完成但未产生指标文件")
            metrics = read_json_metrics(metrics_path)
            if not metrics:
                raise TrainingExecutionError("验收评测未产生可比较指标")
            return metrics, metrics_path
        except APIError as error:
            raise TrainingExecutionError(f"Docker 验收执行失败：{error}") from error
        finally:
            if container is not None:
                try:
                    container.remove(force=True)
                except DockerException:
                    pass
