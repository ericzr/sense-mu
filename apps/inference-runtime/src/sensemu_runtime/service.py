import base64
import binascii
import shutil
import tempfile
import threading
from collections import OrderedDict
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from time import perf_counter
from typing import Any, Protocol

from sensemu_runtime.storage import ObjectStore


class RuntimeInputError(ValueError):
    pass


class RuntimeExecutionError(RuntimeError):
    pass


class RuntimeBusyError(RuntimeError):
    pass


class Predictor(Protocol):
    def __call__(self, sources: list[str], **kwargs: Any) -> list[Any]: ...


PredictorFactory = Callable[[Path], Predictor]


@dataclass
class ModelHandle:
    predictor: Predictor
    inference_lock: threading.Lock = field(default_factory=threading.Lock)


def ultralytics_predictor_factory(model_path: Path) -> Predictor:
    try:
        from ultralytics import YOLO
    except ImportError as error:
        raise RuntimeExecutionError("运行时没有安装 Ultralytics") from error
    return YOLO(str(model_path))


def _input_suffix(uri: str) -> str:
    if uri.startswith("data:image/png;"):
        return ".png"
    if uri.startswith("data:image/webp;"):
        return ".webp"
    if uri.startswith("data:image/jpeg;"):
        return ".jpg"
    suffix = Path(uri.split("?", maxsplit=1)[0]).suffix.lower()
    return suffix if suffix in {".jpg", ".jpeg", ".png", ".webp"} else ".jpg"


def _materialize_input(
    store: ObjectStore,
    uri: str,
    destination: Path,
    max_bytes: int,
) -> None:
    if not uri.startswith("data:"):
        store.materialize(uri, destination, max_bytes)
        return
    header, separator, encoded = uri.partition(",")
    if not separator or header not in {
        "data:image/jpeg;base64",
        "data:image/png;base64",
        "data:image/webp;base64",
    }:
        raise RuntimeInputError("只允许 JPEG、PNG 或 WebP 的 Base64 图片")
    try:
        payload = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as error:
        raise RuntimeInputError("Base64 图片格式无效") from error
    if len(payload) > max_bytes:
        raise RuntimeInputError("图片超过运行时大小限制")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(payload)


class ModelCache:
    def __init__(
        self,
        store: ObjectStore,
        cache_root: Path,
        factory: PredictorFactory,
        max_models: int,
        max_model_bytes: int,
    ) -> None:
        self.store = store
        self.cache_root = cache_root.resolve()
        self.cache_root.mkdir(parents=True, exist_ok=True)
        self.factory = factory
        self.max_models = max(1, max_models)
        self.max_model_bytes = max_model_bytes
        self.models: OrderedDict[str, ModelHandle] = OrderedDict()
        self.lock = threading.RLock()

    def get(self, model_version_id: str, artifact_uri: str) -> ModelHandle:
        with self.lock:
            cached = self.models.get(model_version_id)
            if cached is not None:
                self.models.move_to_end(model_version_id)
                return cached
            model_path = self.cache_root / model_version_id / "model.pt"
            if not model_path.is_file():
                self.store.materialize(artifact_uri, model_path, self.max_model_bytes)
            try:
                predictor = self.factory(model_path)
            except Exception as error:
                if isinstance(error, RuntimeExecutionError):
                    raise
                raise RuntimeExecutionError("模型加载失败") from error
            handle = ModelHandle(predictor=predictor)
            self.models[model_version_id] = handle
            while len(self.models) > self.max_models:
                evicted_id, _ = self.models.popitem(last=False)
                shutil.rmtree(self.cache_root / evicted_id, ignore_errors=True)
            return handle

    def contains(self, model_version_id: str) -> bool:
        with self.lock:
            return model_version_id in self.models

    def summary(self) -> dict[str, Any]:
        with self.lock:
            return {
                "loaded_models": len(self.models),
                "max_cached_models": self.max_models,
                "model_version_ids": list(self.models.keys()),
            }


class PredictionService:
    def __init__(
        self,
        store: ObjectStore,
        cache: ModelCache,
        *,
        device: str,
        max_input_bytes: int,
        max_concurrent_requests: int = 1,
        queue_timeout_seconds: float = 2.0,
    ) -> None:
        self.store = store
        self.cache = cache
        self.device = device
        self.max_input_bytes = max_input_bytes
        self.max_concurrent_requests = max(1, max_concurrent_requests)
        self.queue_timeout_seconds = max(0.0, queue_timeout_seconds)
        self._capacity = threading.BoundedSemaphore(self.max_concurrent_requests)
        self._capacity_lock = threading.Lock()
        self._active_requests = 0
        self._waiting_requests = 0

    @contextmanager
    def _capacity_slot(self) -> Iterator[None]:
        with self._capacity_lock:
            self._waiting_requests += 1
        acquired = self._capacity.acquire(timeout=self.queue_timeout_seconds)
        with self._capacity_lock:
            self._waiting_requests -= 1
            if acquired:
                self._active_requests += 1
        if not acquired:
            raise RuntimeBusyError("运行时容量已满，请稍后重试")
        try:
            yield
        finally:
            with self._capacity_lock:
                self._active_requests -= 1
            self._capacity.release()

    def capacity_summary(self) -> dict[str, int]:
        with self._capacity_lock:
            active_requests = self._active_requests
            waiting_requests = self._waiting_requests
        return {
            "active_requests": active_requests,
            "waiting_requests": waiting_requests,
            "max_concurrent_requests": self.max_concurrent_requests,
            "available_slots": max(0, self.max_concurrent_requests - active_requests),
        }

    def prewarm(
        self,
        *,
        model_version_id: str,
        artifact_uri: str,
        task_type: str,
    ) -> bool:
        if task_type != "object-detection":
            raise RuntimeInputError("当前运行时只支持目标检测模型")
        with self._capacity_slot():
            cache_hit = self.cache.contains(model_version_id)
            try:
                self.cache.get(model_version_id, artifact_uri)
            except (FileNotFoundError, ValueError) as error:
                raise RuntimeInputError(str(error)) from error
            return cache_hit

    def predict(
        self,
        *,
        model_version_id: str,
        artifact_uri: str,
        task_type: str,
        inputs: list[str],
        confidence: float,
        iou: float,
        max_detections: int,
        image_size: int,
    ) -> tuple[list[dict[str, Any]], float]:
        if task_type != "object-detection":
            raise RuntimeInputError("当前运行时只支持目标检测模型")
        with self._capacity_slot():
            try:
                model = self.cache.get(model_version_id, artifact_uri)
            except (FileNotFoundError, ValueError) as error:
                raise RuntimeInputError(str(error)) from error

            with tempfile.TemporaryDirectory(prefix="sensemu-inference-") as directory:
                request_root = Path(directory)
                paths: list[Path] = []
                try:
                    for index, uri in enumerate(inputs):
                        destination = request_root / f"input-{index}{_input_suffix(uri)}"
                        _materialize_input(
                            self.store,
                            uri,
                            destination,
                            self.max_input_bytes,
                        )
                        paths.append(destination)
                except (FileNotFoundError, ValueError) as error:
                    raise RuntimeInputError(str(error)) from error

                started_at = perf_counter()
                try:
                    with model.inference_lock:
                        results = model.predictor(
                            [str(path) for path in paths],
                            conf=confidence,
                            iou=iou,
                            max_det=max_detections,
                            imgsz=image_size,
                            device=self.device,
                            verbose=False,
                        )
                except Exception as error:
                    raise RuntimeExecutionError("模型推理失败") from error
                elapsed_ms = (perf_counter() - started_at) * 1000

        if len(results) != len(inputs):
            raise RuntimeExecutionError("运行时返回的结果数量与输入不一致")
        return [
            self._serialize_detection_result(index, uri, result)
            for index, (uri, result) in enumerate(zip(inputs, results, strict=True))
        ], elapsed_ms

    @staticmethod
    def _serialize_detection_result(index: int, uri: str, result: Any) -> dict[str, Any]:
        boxes = getattr(result, "boxes", None)
        names = getattr(result, "names", {})
        shape = getattr(result, "orig_shape", (0, 0))
        if boxes is None:
            detections: list[dict[str, Any]] = []
        else:
            coordinates = boxes.xyxy.tolist()
            confidences = boxes.conf.tolist()
            classes = boxes.cls.tolist()
            detections = [
                {
                    "class_id": int(class_id),
                    "class_name": str(names.get(int(class_id), int(class_id))),
                    "confidence": float(confidence),
                    "box": {
                        "x1": float(box[0]),
                        "y1": float(box[1]),
                        "x2": float(box[2]),
                        "y2": float(box[3]),
                    },
                }
                for box, confidence, class_id in zip(
                    coordinates, confidences, classes, strict=True
                )
            ]
        return {
            "input": f"inline-image-{index + 1}" if uri.startswith("data:") else uri,
            "width": int(shape[1]) if len(shape) > 1 else 0,
            "height": int(shape[0]) if shape else 0,
            "detections": detections,
        }
