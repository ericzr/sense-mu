import json
import logging
import socket
import tempfile
from ipaddress import ip_address
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from uuid import UUID, uuid4

import httpx
from celery import shared_task

from sensemu_worker.api_client import (
    TransientWorkerAPIError,
    WorkerAPIClient,
    WorkerAPIError,
)
from sensemu_worker.config import WorkerSettings
from sensemu_worker.dataset import (
    DatasetPreflightError,
    prepare_detection_acceptance_dataset,
    prepare_detection_dataset,
)
from sensemu_worker.executor import (
    DockerUltralyticsExecutor,
    DockerUnavailableError,
    TrainingCancelledError,
    TrainingExecutionError,
)
from sensemu_worker.lease import ExecutionLeaseHeartbeat, ExecutionLeaseLostError
from sensemu_worker.object_store import create_object_store
from sensemu_worker.runtime import BatchRuntimeClient, BatchRuntimeError, BatchRuntimeUnavailable
from sensemu_worker.video_extraction import VideoExtractionError, extract_frames, file_sha256

logger = logging.getLogger(__name__)
TERMINAL_STATUSES = {"succeeded", "failed", "cancelled"}


def _require_public_webhook_target(target_url: str) -> None:
    parsed = urlparse(target_url)
    hostname = parsed.hostname
    if parsed.scheme != "https" or not hostname or parsed.username:
        raise ValueError("Webhook 地址必须为不含凭据的 HTTPS 地址")
    try:
        port = parsed.port
    except ValueError as error:
        raise ValueError("Webhook 地址端口无效") from error
    if port not in {None, 443}:
        raise ValueError("Webhook 地址只能使用默认 HTTPS 端口")
    normalized = hostname.rstrip(".").lower()
    if normalized == "localhost" or normalized.endswith(
        (".localhost", ".local", ".internal")
    ):
        raise ValueError("Webhook 地址不能指向本地或内部域名")
    try:
        addresses = {
            ip_address(sockaddr[0].split("%", 1)[0])
            for _, _, _, _, sockaddr in socket.getaddrinfo(
                normalized,
                443,
                type=socket.SOCK_STREAM,
            )
        }
    except (OSError, ValueError) as error:
        raise ValueError("Webhook 域名无法安全解析") from error
    if not addresses or any(not address.is_global for address in addresses):
        raise ValueError("Webhook 域名不能解析到本地、私有或保留网络")


@shared_task(bind=True, name="sensemu.video-extraction.execute", max_retries=3)
def execute_video_extraction(
    self,
    workspace_id: str,
    job_id: str,
    attempt_id: str,
) -> dict[str, Any]:
    settings = WorkerSettings.from_environment()
    api = WorkerAPIClient(settings)
    try:
        execution = api.claim_video_extraction(
            workspace_id,
            job_id,
            attempt_id,
            str(self.request.hostname or "sensemu-worker"),
        )
    except TransientWorkerAPIError as error:
        raise self.retry(exc=error, countdown=30) from error
    except WorkerAPIError as error:
        return {"job_id": job_id, "status": "not-claimed", "reason": str(error)}

    job = dict(execution["job"])
    if job["status"] in TERMINAL_STATUSES:
        return {"job_id": job_id, "status": job["status"]}
    if job["status"] == "cancel_requested":
        api.video_extraction_event(workspace_id, job_id, attempt_id, "job.cancelled")
        return {"job_id": job_id, "status": "cancelled"}

    spec = dict(execution["job_spec"])
    store = create_object_store(settings)
    lease = ExecutionLeaseHeartbeat(
        api,
        workspace_id,
        job_id,
        attempt_id,
        settings.lease_heartbeat_interval_seconds,
        heartbeat=api.heartbeat_video_extraction,
        resource_name="抽帧任务",
    )

    def cancel_requested() -> bool:
        lease.ensure_owned()
        try:
            return api.get_video_extraction(workspace_id, job_id)["status"] == "cancel_requested"
        except TransientWorkerAPIError:
            return False

    def cancel() -> dict[str, Any]:
        api.video_extraction_event(workspace_id, job_id, attempt_id, "job.cancelled")
        return {"job_id": job_id, "status": "cancelled"}

    try:
        lease.start()
        api.video_extraction_event(workspace_id, job_id, attempt_id, "job.started")
        source = dict(spec["source"])
        recipe = dict(spec["recipe"])
        artifact_prefix = str(spec["artifact_prefix"])
        with tempfile.TemporaryDirectory(prefix=f"sensemu-extract-{job_id[:8]}-") as temporary:
            workspace = Path(temporary)
            source_path = workspace / "source-video"
            store.materialize(str(source["uri"]), source_path)
            lease.ensure_owned()
            if cancel_requested():
                return cancel()
            frames, dimensions, _duration_ms = extract_frames(
                source_path,
                workspace / "frames",
                frame_interval_ms=int(recipe["frame_interval_ms"]),
                deduplicate=bool(recipe["deduplicate"]),
                on_progress=lambda progress: _report_video_extraction_progress(
                    api,
                    lease,
                    workspace_id,
                    job_id,
                    attempt_id,
                    progress,
                ),
            )
            lease.ensure_owned()
            if cancel_requested():
                return cancel()
            completed_frames: list[dict[str, Any]] = []
            total = len(frames)
            for position, frame in enumerate(frames):
                lease.ensure_owned()
                if position % 10 == 0 and cancel_requested():
                    return cancel()
                key = f"{artifact_prefix}/frames/{frame.name}"
                object_uri = store.upload(frame, key, "image/jpeg")
                completed_frames.append(
                    {
                        "object_uri": object_uri,
                        "media_type": "image/jpeg",
                        "checksum_sha256": file_sha256(frame),
                        "byte_size": frame.stat().st_size,
                        "width": dimensions[0],
                        "height": dimensions[1],
                        "frame_index": position,
                        "timestamp_ms": position * int(recipe["frame_interval_ms"]),
                    }
                )
                if position and position % 25 == 0:
                    _report_video_extraction_progress(
                        api,
                        lease,
                        workspace_id,
                        job_id,
                        attempt_id,
                        progress=min(95, 75 + round((position / total) * 20)),
                    )
        lease.ensure_owned()
        if cancel_requested():
            return cancel()
        result = api.complete_video_extraction(
            workspace_id,
            job_id,
            attempt_id,
            completed_frames,
        )
        return {"job_id": job_id, "status": result["status"], "frames_created": total}
    except TransientWorkerAPIError as error:
        raise self.retry(exc=error, countdown=30) from error
    except ExecutionLeaseLostError as error:
        logger.warning("Stopped stale video extraction %s: %s", job_id, error)
        return {"job_id": job_id, "status": "lease-lost"}
    except (VideoExtractionError, OSError, ValueError, KeyError) as error:
        try:
            if cancel_requested():
                return cancel()
            api.video_extraction_event(
                workspace_id,
                job_id,
                attempt_id,
                "job.failed",
                error_code="video_extraction_failed",
                error_message=str(error)[-4000:],
            )
        except WorkerAPIError:
            logger.exception("Unable to report failed video extraction %s", job_id)
        return {"job_id": job_id, "status": "failed", "reason": str(error)}
    except WorkerAPIError as error:
        logger.warning("Video extraction %s was not completed: %s", job_id, error)
        return {"job_id": job_id, "status": "not-completed", "reason": str(error)}
    finally:
        lease.stop()


def _report_video_extraction_progress(
    api: WorkerAPIClient,
    lease: ExecutionLeaseHeartbeat,
    workspace_id: str,
    job_id: str,
    attempt_id: str,
    progress: int,
) -> None:
    lease.ensure_owned()
    try:
        api.video_extraction_event(
            workspace_id,
            job_id,
            attempt_id,
            "job.progressed",
            progress=progress,
        )
    except TransientWorkerAPIError:
        logger.warning("Unable to report progress for video extraction %s", job_id)


@shared_task(
    name="sensemu.video-extraction.recover-stale",
    autoretry_for=(TransientWorkerAPIError,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 5},
)
def recover_stale_video_extraction_executions() -> dict[str, Any]:
    api = WorkerAPIClient(WorkerSettings.from_environment())
    return api.recover_stale_video_extractions()


def _send_failure(
    api: WorkerAPIClient,
    workspace_id: str,
    run_id: str,
    attempt_id: str,
    error_code: str,
    message: str,
) -> None:
    try:
        api.send_event(
            workspace_id,
            run_id,
            attempt_id,
            "job.failed",
            error_code=error_code,
            error_message=message[-4000:],
        )
    except WorkerAPIError:
        logger.exception("Unable to report failed training run %s", run_id)


@shared_task(
    name="sensemu.training.recover-stale",
    autoretry_for=(TransientWorkerAPIError,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 5},
)
def recover_stale_training_executions() -> dict[str, Any]:
    api = WorkerAPIClient(WorkerSettings.from_environment())
    return api.recover_stale_executions()


@shared_task(
    name="sensemu.inference.recover-stale-reservations",
    autoretry_for=(TransientWorkerAPIError,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 5},
)
def recover_stale_usage_reservations() -> dict[str, Any]:
    api = WorkerAPIClient(WorkerSettings.from_environment())
    return api.recover_stale_usage_reservations()


@shared_task(
    name="sensemu.webhooks.recover",
    autoretry_for=(TransientWorkerAPIError,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 5},
)
def recover_webhook_deliveries() -> dict[str, Any]:
    api = WorkerAPIClient(WorkerSettings.from_environment())
    recovered = api.recover_webhook_deliveries()
    for delivery_id in recovered.get("queued_delivery_ids", []):
        deliver_webhook.delay(str(delivery_id))
    return recovered


@shared_task(
    name="sensemu.webhooks.deliver",
    autoretry_for=(TransientWorkerAPIError,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 5},
)
def deliver_webhook(delivery_id: str) -> dict[str, Any]:
    api = WorkerAPIClient(WorkerSettings.from_environment())
    try:
        delivery = api.claim_webhook_delivery(delivery_id)
    except WorkerAPIError as error:
        return {"delivery_id": delivery_id, "status": "not-claimed", "reason": str(error)}
    encoded = json.dumps(
        delivery["payload"],
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    try:
        _require_public_webhook_target(delivery["target_url"])
        response = httpx.post(
            delivery["target_url"],
            content=encoded,
            headers={
                "Content-Type": "application/json",
                "X-SenseMu-Event-ID": str(delivery["payload"]["event_id"]),
                "X-SenseMu-Webhook-Signature": f"sha256={delivery['signature']}",
            },
            timeout=10,
            follow_redirects=False,
        )
    except (httpx.HTTPError, ValueError) as error:
        return api.complete_webhook_delivery(
            delivery_id,
            succeeded=False,
            error=f"网络请求失败：{error}",
        )
    return api.complete_webhook_delivery(
        delivery_id,
        succeeded=200 <= response.status_code < 300,
        status_code=response.status_code,
        error=None if response.is_success else f"Webhook 返回 HTTP {response.status_code}",
    )


@shared_task(bind=True, name="sensemu.training.execute", max_retries=12)
def execute_training(
    self,
    workspace_id: str,
    run_id: str,
    attempt_id: str,
    completion: dict[str, Any] | None = None,
) -> dict[str, Any]:
    settings = WorkerSettings.from_environment()
    api = WorkerAPIClient(settings)
    try:
        execution = api.claim_execution(
            workspace_id,
            run_id,
            attempt_id,
            str(self.request.hostname or "sensemu-worker"),
        )
    except TransientWorkerAPIError as error:
        raise self.retry(exc=error, countdown=30) from error
    except WorkerAPIError as error:
        return {"run_id": run_id, "status": "not-claimed", "reason": str(error)}

    status = str(execution["status"])
    if status in TERMINAL_STATUSES:
        return {"run_id": run_id, "status": status}
    if completion is not None:
        try:
            api.complete(
                workspace_id,
                run_id,
                attempt_id,
                model_name=str(completion["model_name"]),
                artifact_uri=str(completion["artifact_uri"]),
                metrics=dict(completion.get("metrics", {})),
                event_id=UUID(str(completion["event_id"])),
            )
        except TransientWorkerAPIError as error:
            raise self.retry(
                exc=error,
                countdown=30,
                kwargs={
                    "workspace_id": workspace_id,
                    "run_id": run_id,
                    "attempt_id": attempt_id,
                    "completion": completion,
                },
            ) from error
        return {"run_id": run_id, "status": "succeeded"}
    if status == "cancel_requested":
        api.send_event(workspace_id, run_id, attempt_id, "job.cancelled")
        return {"run_id": run_id, "status": "cancelled"}
    if status == "running":
        return {"run_id": run_id, "status": "already-running"}
    if status not in {"queued", "preparing"}:
        raise WorkerAPIError(f"不支持执行状态 {status}")

    job_spec = dict(execution["job_spec"])
    store = create_object_store(settings)
    runtime = job_spec.get("runtime") or {}
    executor = DockerUltralyticsExecutor(settings, image=str(runtime.get("image") or settings.docker_image))
    lease = ExecutionLeaseHeartbeat(
        api,
        workspace_id,
        run_id,
        attempt_id,
        settings.lease_heartbeat_interval_seconds,
    )
    try:
        lease.start()
        manifest_uri = str(job_spec["dataset_version"]["manifest_uri"])
        manifest = store.read_json(manifest_uri)
        with tempfile.TemporaryDirectory(prefix=f"sensemu-{run_id[:8]}-") as temporary:
            workspace = Path(temporary)
            prepared = prepare_detection_dataset(manifest, store, workspace)
            lease.ensure_owned()
            resolved_image = executor.ensure_available()
            lease.ensure_owned()
            api.send_event(
                workspace_id,
                run_id,
                attempt_id,
                "job.started",
                payload={
                    "engine": job_spec["engine"],
                    "executor": job_spec["executor"],
                    "train_assets": prepared.train_count,
                    "validation_assets": prepared.validation_count,
                    "runtime_image": resolved_image,
                },
            )

            def on_progress(progress: int) -> None:
                lease.ensure_owned()
                try:
                    api.send_event(
                        workspace_id,
                        run_id,
                        attempt_id,
                        "job.progressed",
                        progress=progress,
                    )
                except TransientWorkerAPIError:
                    logger.warning("Unable to report progress for training run %s", run_id)

            def should_cancel() -> bool:
                lease.ensure_owned()
                try:
                    return api.get_run(workspace_id, run_id)["status"] == "cancel_requested"
                except TransientWorkerAPIError:
                    return False

            artifact_directory = workspace / "artifacts"
            model_path, metrics, results_path, visualization_paths, class_metrics_path = executor.run(
                run_id,
                prepared,
                dict(job_spec["recipe"]),
                artifact_directory,
                on_progress=on_progress,
                should_cancel=should_cancel,
            )
            artifact_prefix = str(job_spec["artifact_prefix"])
            artifact_uri = store.upload(model_path, f"{artifact_prefix}/model/best.pt")
            if results_path is not None:
                store.upload(results_path, f"{artifact_prefix}/metrics/results.csv")
            for visualization_path in visualization_paths:
                store.upload(
                    visualization_path,
                    f"{artifact_prefix}/metrics/{visualization_path.name}",
                    "image/png",
                )
            if class_metrics_path is not None:
                store.upload(
                    class_metrics_path,
                    f"{artifact_prefix}/metrics/{class_metrics_path.name}",
                    "application/json",
                )

        lease.ensure_owned()
        completion_payload = {
            "event_id": str(uuid4()),
            "model_name": str(job_spec.get("project", {}).get("name") or "训练模型"),
            "artifact_uri": artifact_uri,
            "metrics": metrics,
        }
        try:
            api.complete(
                workspace_id,
                run_id,
                attempt_id,
                model_name=str(completion_payload["model_name"]),
                artifact_uri=artifact_uri,
                metrics=metrics,
                event_id=UUID(str(completion_payload["event_id"])),
            )
        except TransientWorkerAPIError as error:
            raise self.retry(
                exc=error,
                countdown=30,
                kwargs={
                    "workspace_id": workspace_id,
                    "run_id": run_id,
                    "attempt_id": attempt_id,
                    "completion": completion_payload,
                },
            ) from error
        return {"run_id": run_id, "status": "succeeded", "artifact_uri": artifact_uri}
    except DatasetPreflightError as error:
        try:
            if api.get_run(workspace_id, run_id)["status"] == "cancel_requested":
                api.send_event(workspace_id, run_id, attempt_id, "job.cancelled")
                return {"run_id": run_id, "status": "cancelled"}
        except TransientWorkerAPIError:
            pass
        _send_failure(
            api,
            workspace_id,
            run_id,
            attempt_id,
            "dataset_preflight_failed",
            str(error),
        )
        return {"run_id": run_id, "status": "failed", "reason": str(error)}
    except DockerUnavailableError as error:
        raise self.retry(exc=error, countdown=30) from error
    except ExecutionLeaseLostError as error:
        return {"run_id": run_id, "status": "lease-lost", "reason": str(error)}
    except TrainingCancelledError:
        api.send_event(workspace_id, run_id, attempt_id, "job.cancelled")
        return {"run_id": run_id, "status": "cancelled"}
    except TrainingExecutionError as error:
        _send_failure(api, workspace_id, run_id, attempt_id, "training_failed", str(error))
        return {"run_id": run_id, "status": "failed", "reason": str(error)}
    except (OSError, ValueError, KeyError) as error:
        _send_failure(api, workspace_id, run_id, attempt_id, "worker_failed", str(error))
        return {"run_id": run_id, "status": "failed", "reason": str(error)}
    finally:
        lease.stop()


@shared_task(bind=True, name="sensemu.batch-inference.execute", max_retries=3)
def execute_batch_inference(
    self,
    workspace_id: str,
    run_id: str,
    attempt_id: str,
    completion: dict[str, Any] | None = None,
) -> dict[str, Any]:
    settings = WorkerSettings.from_environment()
    api = WorkerAPIClient(settings)
    try:
        execution = api.claim_execution(
            workspace_id,
            run_id,
            attempt_id,
            str(self.request.hostname or "sensemu-worker"),
        )
    except TransientWorkerAPIError as error:
        raise self.retry(exc=error, countdown=30) from error
    except WorkerAPIError as error:
        return {"run_id": run_id, "status": "not-claimed", "reason": str(error)}

    execution_status = str(execution["status"])
    if execution_status in TERMINAL_STATUSES:
        return {"run_id": run_id, "status": execution_status}
    if completion is not None:
        try:
            api.complete_batch_inference(
                workspace_id,
                run_id,
                attempt_id,
                output_uri=str(completion["output_uri"]),
                report_uri=str(completion["report_uri"]),
                processed_asset_count=int(completion["processed_asset_count"]),
                prediction_count=int(completion["prediction_count"]),
                runtime=dict(completion.get("runtime", {})),
                event_id=UUID(str(completion["event_id"])),
            )
        except TransientWorkerAPIError as error:
            raise self.retry(
                exc=error,
                countdown=30,
                kwargs={
                    "workspace_id": workspace_id,
                    "run_id": run_id,
                    "attempt_id": attempt_id,
                    "completion": completion,
                },
            ) from error
        return {"run_id": run_id, "status": "succeeded"}
    if execution_status == "cancel_requested":
        api.send_event(workspace_id, run_id, attempt_id, "job.cancelled")
        return {"run_id": run_id, "status": "cancelled"}
    if execution_status == "running":
        return {"run_id": run_id, "status": "already-running"}
    if execution_status not in {"queued", "preparing"}:
        raise WorkerAPIError(f"不支持执行状态 {execution_status}")

    job_spec = dict(execution["job_spec"])
    store = create_object_store(settings)
    lease = ExecutionLeaseHeartbeat(
        api,
        workspace_id,
        run_id,
        attempt_id,
        settings.lease_heartbeat_interval_seconds,
    )
    try:
        lease.start()
        manifest = store.read_json(str(job_spec["dataset_version"]["manifest_uri"]))
        assets = manifest.get("assets")
        recipe = dict(job_spec["recipe"])
        source_split = str(recipe["source_split"])
        if not isinstance(assets, list):
            raise TypeError("批量推理清单格式不正确")
        selected_assets = [
            asset
            for asset in assets
            if isinstance(asset, dict)
            and (source_split == "all" or asset.get("split") == source_split)
        ]
        if not selected_assets:
            raise ValueError("批量推理清单没有可处理的资产")

        deployment = dict(job_spec["deployment"])
        model_payload = {
            "version_id": deployment["model_version_id"],
            "artifact_uri": deployment["artifact_uri"],
            "task_type": deployment["task_type"],
        }
        runtime = BatchRuntimeClient(settings)
        prediction_count = 0
        processed_count = 0
        elapsed_ms = 0.0
        with tempfile.TemporaryDirectory(prefix=f"sensemu-batch-{run_id[:8]}-") as temporary:
            output_path = Path(temporary) / "predictions.ndjson"
            report_path = Path(temporary) / "report.json"
            api.send_event(
                workspace_id,
                run_id,
                attempt_id,
                "job.started",
                payload={
                    "engine": "ultralytics",
                    "executor": "runtime",
                    "selected_asset_count": len(selected_assets),
                    "source_split": source_split,
                },
            )
            with output_path.open("w", encoding="utf-8") as output:
                for offset in range(0, len(selected_assets), 4):
                    lease.ensure_owned()
                    try:
                        if api.get_run(workspace_id, run_id)["status"] == "cancel_requested":
                            api.send_event(workspace_id, run_id, attempt_id, "job.cancelled")
                            return {"run_id": run_id, "status": "cancelled"}
                    except TransientWorkerAPIError:
                        pass
                    group = selected_assets[offset : offset + 4]
                    inputs = [str(asset["uri"]) for asset in group]
                    response = runtime.predict(
                        request_id=f"{run_id}-{offset // 4:06d}",
                        model=model_payload,
                        contract=str(deployment["contract"]),
                        inputs=inputs,
                        parameters=dict(recipe["parameters"]),
                    )
                    predictions = response.get("predictions")
                    if not isinstance(predictions, list) or len(predictions) != len(group):
                        raise BatchRuntimeError("运行时返回结果数量与批量输入不一致")
                    elapsed_ms += float((response.get("runtime") or {}).get("inference_ms") or 0)
                    for asset, prediction in zip(group, predictions, strict=True):
                        detections = prediction.get("detections") if isinstance(prediction, dict) else []
                        if isinstance(detections, list):
                            prediction_count += len(detections)
                        output.write(
                            json.dumps(
                                {"asset_id": asset["asset_id"], "prediction": prediction},
                                ensure_ascii=False,
                                separators=(",", ":"),
                            )
                            + "\n"
                        )
                    processed_count += len(group)
                    api.send_event(
                        workspace_id,
                        run_id,
                        attempt_id,
                        "job.progressed",
                        progress=min(99, round(processed_count / len(selected_assets) * 100)),
                        payload={"processed_asset_count": processed_count},
                    )
            runtime_summary = {
                "engine": "ultralytics",
                "inference_ms": round(elapsed_ms, 3),
            }
            report_path.write_text(
                json.dumps(
                    {
                        "schema_version": "1.0",
                        "run_id": run_id,
                        "deployment_id": deployment["id"],
                        "dataset_version_id": job_spec["dataset_version"]["id"],
                        "source_split": source_split,
                        "processed_asset_count": processed_count,
                        "prediction_count": prediction_count,
                        "runtime": runtime_summary,
                        "output_format": "ndjson",
                    },
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
            )
            artifact_prefix = str(job_spec["artifact_prefix"])
            output_uri = store.upload(output_path, f"{artifact_prefix}/predictions.ndjson")
            report_uri = store.upload(report_path, f"{artifact_prefix}/report.json")

        lease.ensure_owned()
        completion_payload = {
            "event_id": str(uuid4()),
            "output_uri": output_uri,
            "report_uri": report_uri,
            "processed_asset_count": processed_count,
            "prediction_count": prediction_count,
            "runtime": runtime_summary,
        }
        try:
            api.complete_batch_inference(
                workspace_id,
                run_id,
                attempt_id,
                output_uri=output_uri,
                report_uri=report_uri,
                processed_asset_count=processed_count,
                prediction_count=prediction_count,
                runtime=runtime_summary,
                event_id=UUID(completion_payload["event_id"]),
            )
        except TransientWorkerAPIError as error:
            raise self.retry(
                exc=error,
                countdown=30,
                kwargs={
                    "workspace_id": workspace_id,
                    "run_id": run_id,
                    "attempt_id": attempt_id,
                    "completion": completion_payload,
                },
            ) from error
        return {"run_id": run_id, "status": "succeeded", "output_uri": output_uri}
    except BatchRuntimeUnavailable as error:
        _send_failure(api, workspace_id, run_id, attempt_id, "runtime_unavailable", str(error))
        return {"run_id": run_id, "status": "failed", "reason": str(error)}
    except (BatchRuntimeError, OSError, TypeError, ValueError, KeyError) as error:
        _send_failure(api, workspace_id, run_id, attempt_id, "batch_inference_failed", str(error))
        return {"run_id": run_id, "status": "failed", "reason": str(error)}
    except ExecutionLeaseLostError as error:
        return {"run_id": run_id, "status": "lease-lost", "reason": str(error)}
    finally:
        lease.stop()


@shared_task(bind=True, name="sensemu.evaluation.execute", max_retries=12)
def execute_acceptance_evaluation(
    self,
    workspace_id: str,
    run_id: str,
    attempt_id: str,
    completion: dict[str, Any] | None = None,
) -> dict[str, Any]:
    settings = WorkerSettings.from_environment()
    api = WorkerAPIClient(settings)
    try:
        execution = api.claim_execution(
            workspace_id,
            run_id,
            attempt_id,
            str(self.request.hostname or "sensemu-worker"),
        )
    except TransientWorkerAPIError as error:
        raise self.retry(exc=error, countdown=30) from error
    except WorkerAPIError as error:
        return {"run_id": run_id, "status": "not-claimed", "reason": str(error)}

    status = str(execution["status"])
    if status in TERMINAL_STATUSES:
        return {"run_id": run_id, "status": status}
    if completion is not None:
        try:
            api.complete_acceptance(
                workspace_id,
                run_id,
                attempt_id,
                metrics=dict(completion["metrics"]),
                evaluated_asset_count=int(completion["evaluated_asset_count"]),
                runtime_image=str(completion["runtime_image"]),
                event_id=UUID(str(completion["event_id"])),
            )
        except TransientWorkerAPIError as error:
            raise self.retry(
                exc=error,
                countdown=30,
                kwargs={
                    "workspace_id": workspace_id,
                    "run_id": run_id,
                    "attempt_id": attempt_id,
                    "completion": completion,
                },
            ) from error
        return {"run_id": run_id, "status": "succeeded"}
    if status == "cancel_requested":
        api.send_event(workspace_id, run_id, attempt_id, "job.cancelled")
        return {"run_id": run_id, "status": "cancelled"}
    if status == "running":
        return {"run_id": run_id, "status": "already-running"}
    if status not in {"queued", "preparing"}:
        raise WorkerAPIError(f"不支持执行状态 {status}")

    job_spec = dict(execution["job_spec"])
    store = create_object_store(settings)
    runtime = job_spec.get("runtime") or {}
    executor = DockerUltralyticsExecutor(
        settings,
        image=str(runtime.get("image") or settings.docker_image),
    )
    lease = ExecutionLeaseHeartbeat(
        api,
        workspace_id,
        run_id,
        attempt_id,
        settings.lease_heartbeat_interval_seconds,
    )
    try:
        lease.start()
        manifest_uri = str(job_spec["dataset_version"]["manifest_uri"])
        model_uri = str(job_spec["model_version"]["artifact_uri"])
        manifest = store.read_json(manifest_uri)
        with tempfile.TemporaryDirectory(prefix=f"sensemu-eval-{run_id[:8]}-") as temporary:
            workspace = Path(temporary)
            prepared = prepare_detection_acceptance_dataset(manifest, store, workspace)
            model_path = workspace / "model.pt"
            store.materialize(model_uri, model_path)
            lease.ensure_owned()
            resolved_image = executor.ensure_available()
            lease.ensure_owned()
            api.send_event(
                workspace_id,
                run_id,
                attempt_id,
                "job.started",
                payload={
                    "engine": job_spec["engine"],
                    "executor": job_spec["executor"],
                    "evaluated_assets": prepared.asset_count,
                    "source_split": prepared.source_split,
                    "runtime_image": resolved_image,
                },
            )

            def should_cancel() -> bool:
                lease.ensure_owned()
                try:
                    return api.get_run(workspace_id, run_id)["status"] == "cancel_requested"
                except TransientWorkerAPIError:
                    return False

            artifact_directory = workspace / "artifacts"
            metrics, metrics_path = executor.run_evaluation(
                run_id,
                prepared,
                model_path,
                dict(job_spec["recipe"]),
                artifact_directory,
                should_cancel=should_cancel,
            )
            lease.ensure_owned()
            store.upload(
                metrics_path,
                f"{job_spec['artifact_prefix']}/metrics.json",
            )

        lease.ensure_owned()
        completion_payload = {
            "event_id": str(uuid4()),
            "metrics": metrics,
            "evaluated_asset_count": prepared.asset_count,
            "runtime_image": resolved_image,
        }
        try:
            api.complete_acceptance(
                workspace_id,
                run_id,
                attempt_id,
                metrics=metrics,
                evaluated_asset_count=prepared.asset_count,
                runtime_image=resolved_image,
                event_id=UUID(completion_payload["event_id"]),
            )
        except TransientWorkerAPIError as error:
            raise self.retry(
                exc=error,
                countdown=30,
                kwargs={
                    "workspace_id": workspace_id,
                    "run_id": run_id,
                    "attempt_id": attempt_id,
                    "completion": completion_payload,
                },
            ) from error
        return {"run_id": run_id, "status": "succeeded"}
    except DatasetPreflightError as error:
        _send_failure(
            api,
            workspace_id,
            run_id,
            attempt_id,
            "acceptance_dataset_preflight_failed",
            str(error),
        )
        return {"run_id": run_id, "status": "failed", "reason": str(error)}
    except DockerUnavailableError as error:
        raise self.retry(exc=error, countdown=30) from error
    except ExecutionLeaseLostError as error:
        return {"run_id": run_id, "status": "lease-lost", "reason": str(error)}
    except TrainingCancelledError:
        api.send_event(workspace_id, run_id, attempt_id, "job.cancelled")
        return {"run_id": run_id, "status": "cancelled"}
    except TrainingExecutionError as error:
        _send_failure(
            api,
            workspace_id,
            run_id,
            attempt_id,
            "acceptance_evaluation_failed",
            str(error),
        )
        return {"run_id": run_id, "status": "failed", "reason": str(error)}
    except (OSError, ValueError, KeyError) as error:
        _send_failure(api, workspace_id, run_id, attempt_id, "worker_failed", str(error))
        return {"run_id": run_id, "status": "failed", "reason": str(error)}
    finally:
        lease.stop()
