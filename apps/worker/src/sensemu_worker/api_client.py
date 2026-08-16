from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import httpx

from sensemu_worker.config import WorkerSettings


class WorkerAPIError(RuntimeError):
    pass


class TransientWorkerAPIError(WorkerAPIError):
    pass


class WorkerAPIClient:
    def __init__(self, settings: WorkerSettings) -> None:
        self.base_url = settings.api_url
        self.worker_token = settings.worker_token

    def _request(
        self,
        method: str,
        path: str,
        workspace_id: str | None,
        *,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        try:
            headers = {
                "Accept": "application/json",
                "X-SenseMu-Worker-Token": self.worker_token,
            }
            if workspace_id is not None:
                headers["X-Workspace-ID"] = workspace_id
            response = httpx.request(
                method,
                f"{self.base_url}{path}",
                headers=headers,
                json=payload,
                timeout=20,
            )
        except httpx.HTTPError as error:
            raise TransientWorkerAPIError("无法连接 SenseMu API") from error
        if response.status_code >= 500:
            raise TransientWorkerAPIError(f"SenseMu API 暂时不可用 ({response.status_code})")
        if not response.is_success:
            detail = response.json().get("detail", response.text)
            raise WorkerAPIError(str(detail))
        return response.json()

    def claim_execution(
        self,
        workspace_id: str,
        run_id: str,
        attempt_id: str,
        worker_id: str,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            f"/api/v1/internal/training-runs/{run_id}/execution:claim",
            workspace_id,
            payload={"attempt_id": attempt_id, "worker_id": worker_id},
        )

    def get_run(self, workspace_id: str, run_id: str) -> dict[str, Any]:
        return self._request("GET", f"/api/v1/training-runs/{run_id}", workspace_id)

    def heartbeat_execution(
        self,
        workspace_id: str,
        run_id: str,
        attempt_id: str,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            f"/api/v1/internal/training-runs/{run_id}/execution:heartbeat",
            workspace_id,
            payload={"attempt_id": attempt_id},
        )

    def recover_stale_executions(self) -> dict[str, Any]:
        return self._request(
            "POST",
            "/api/v1/internal/training-runs/executions:recover-stale",
            None,
        )

    def recover_stale_video_extractions(self) -> dict[str, Any]:
        return self._request(
            "POST",
            "/api/v1/internal/video-extractions/executions:recover-stale",
            None,
        )

    def recover_stale_usage_reservations(self) -> dict[str, Any]:
        return self._request(
            "POST",
            "/api/v1/internal/inference/usage-reservations:recover-stale",
            None,
        )

    def claim_webhook_delivery(self, delivery_id: str) -> dict[str, Any]:
        return self._request(
            "POST",
            f"/api/v1/internal/webhook-deliveries/{delivery_id}:claim",
            None,
        )

    def complete_webhook_delivery(
        self,
        delivery_id: str,
        *,
        succeeded: bool,
        status_code: int | None = None,
        error: str | None = None,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            f"/api/v1/internal/webhook-deliveries/{delivery_id}:complete",
            None,
            payload={
                "succeeded": succeeded,
                "status_code": status_code,
                "error": error,
            },
        )

    def recover_webhook_deliveries(self) -> dict[str, Any]:
        return self._request("POST", "/api/v1/internal/webhook-deliveries:recover", None)

    def send_event(
        self,
        workspace_id: str,
        run_id: str,
        attempt_id: str,
        event_type: str,
        *,
        progress: int | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
        payload: dict[str, Any] | None = None,
        event_id: UUID | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "attempt_id": attempt_id,
            "event_id": str(event_id or uuid4()),
            "event_type": event_type,
            "occurred_at": datetime.now(UTC).isoformat(),
            "payload": payload or {},
        }
        if progress is not None:
            body["progress"] = progress
        if error_code:
            body["error_code"] = error_code
        if error_message:
            body["error_message"] = error_message
        return self._request(
            "POST",
            f"/api/v1/internal/training-runs/{run_id}/events",
            workspace_id,
            payload=body,
        )

    def complete(
        self,
        workspace_id: str,
        run_id: str,
        attempt_id: str,
        *,
        model_name: str,
        artifact_uri: str,
        metrics: dict[str, Any],
        event_id: UUID | None = None,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            f"/api/v1/internal/training-runs/{run_id}/complete",
            workspace_id,
            payload={
                "attempt_id": attempt_id,
                "event_id": str(event_id or uuid4()),
                "model_name": model_name,
                "artifact_uri": artifact_uri,
                "metrics": metrics,
                "occurred_at": datetime.now(UTC).isoformat(),
            },
        )

    def complete_acceptance(
        self,
        workspace_id: str,
        run_id: str,
        attempt_id: str,
        *,
        metrics: dict[str, Any],
        evaluated_asset_count: int,
        runtime_image: str,
        event_id: UUID | None = None,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            f"/api/v1/internal/acceptance-runs/{run_id}/complete",
            workspace_id,
            payload={
                "attempt_id": attempt_id,
                "event_id": str(event_id or uuid4()),
                "metrics": metrics,
                "evaluated_asset_count": evaluated_asset_count,
                "runtime_image": runtime_image,
                "occurred_at": datetime.now(UTC).isoformat(),
            },
        )

    def complete_batch_inference(
        self,
        workspace_id: str,
        run_id: str,
        attempt_id: str,
        *,
        output_uri: str,
        report_uri: str,
        processed_asset_count: int,
        prediction_count: int,
        runtime: dict[str, Any],
        event_id: UUID | None = None,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            f"/api/v1/internal/batch-inference-runs/{run_id}/complete",
            workspace_id,
            payload={
                "attempt_id": attempt_id,
                "event_id": str(event_id or uuid4()),
                "output_uri": output_uri,
                "report_uri": report_uri,
                "processed_asset_count": processed_asset_count,
                "prediction_count": prediction_count,
                "runtime": runtime,
                "occurred_at": datetime.now(UTC).isoformat(),
            },
        )

    def claim_video_extraction(
        self,
        workspace_id: str,
        job_id: str,
        attempt_id: str,
        worker_id: str,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            f"/api/v1/internal/video-extractions/{job_id}/execution:claim",
            workspace_id,
            payload={"attempt_id": attempt_id, "worker_id": worker_id},
        )

    def get_video_extraction(
        self,
        workspace_id: str,
        job_id: str,
    ) -> dict[str, Any]:
        return self._request("GET", f"/api/v1/video-extractions/{job_id}", workspace_id)

    def heartbeat_video_extraction(
        self,
        workspace_id: str,
        job_id: str,
        attempt_id: str,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            f"/api/v1/internal/video-extractions/{job_id}/execution:heartbeat",
            workspace_id,
            payload={"attempt_id": attempt_id},
        )

    def video_extraction_event(
        self,
        workspace_id: str,
        job_id: str,
        attempt_id: str,
        event_type: str,
        *,
        progress: int | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"attempt_id": attempt_id, "event_type": event_type}
        if progress is not None:
            payload["progress"] = progress
        if error_code is not None:
            payload["error_code"] = error_code
        if error_message is not None:
            payload["error_message"] = error_message
        return self._request(
            "POST",
            f"/api/v1/internal/video-extractions/{job_id}/events",
            workspace_id,
            payload=payload,
        )

    def complete_video_extraction(
        self,
        workspace_id: str,
        job_id: str,
        attempt_id: str,
        frames: list[dict[str, Any]],
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            f"/api/v1/internal/video-extractions/{job_id}/complete",
            workspace_id,
            payload={
                "attempt_id": attempt_id,
                "frames": frames,
                "occurred_at": datetime.now(UTC).isoformat(),
            },
        )
