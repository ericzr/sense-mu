import asyncio
from datetime import UTC, datetime
from hashlib import sha256
from typing import Annotated, Any, Literal
from uuid import uuid4

import httpx
import uvicorn
from fastapi import FastAPI, Header, HTTPException, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from sensemu_gateway.config import get_settings

InferenceInput = Annotated[str, Field(min_length=1, max_length=12_000_000)]
PPE_VIOLATION_WEBHOOK_TEMPLATE = "ppe-violation-webhook.v1"
PPE_EVENT_REQUIREMENTS = {
    "missing_hardhat": "hardhat",
    "missing_safety_vest": "safety_vest",
}


class EventContext(BaseModel):
    source_id: str = Field(
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,149}$",
    )
    source_type: Literal["camera", "batch", "upload"] = "camera"


class PredictionRequest(BaseModel):
    inputs: list[InferenceInput] = Field(min_length=1, max_length=4)
    parameters: dict[str, Any] = Field(default_factory=dict)
    event_context: EventContext | None = None


class RuntimeSummary(BaseModel):
    configured: bool
    protocol_version: str = "inference.v1"
    supported_contracts: list[str]


def _upstream_error(
    code: str,
    message: str,
    status_code: int,
    *,
    headers: dict[str, str] | None = None,
) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"code": code, "message": message},
        headers=headers,
    )


def _event_idempotency_key(
    request_id: str,
    workflow_id: str,
    event_type: str,
    input_index: int,
) -> str:
    suffix = sha256(
        f"{workflow_id}:{event_type}:{input_index}".encode()
    ).hexdigest()[:16]
    return f"{request_id}.{suffix}"


def _ppe_event_payloads(
    *,
    workflow_bindings: list[dict[str, Any]],
    inputs: list[str],
    event_context: EventContext | None,
    runtime_outputs: Any,
    request_id: str,
    occurred_at: datetime,
) -> list[tuple[str, dict[str, Any]]]:
    """Translate detection outputs using the single, published PPE template.

    The template reports frame-level class absence only. It intentionally does not
    claim person-to-equipment association and never copies an input reference into
    the event body.
    """
    if not isinstance(runtime_outputs, dict):
        return []
    predictions = runtime_outputs.get("predictions")
    if not isinstance(predictions, list):
        return []

    events: list[tuple[str, dict[str, Any]]] = []
    for input_index, prediction in enumerate(predictions):
        if input_index >= len(inputs) or not isinstance(prediction, dict):
            continue
        detections = prediction.get("detections")
        if not isinstance(detections, list):
            continue
        class_counts: dict[str, int] = {}
        for detection in detections:
            if not isinstance(detection, dict):
                continue
            class_name = detection.get("class_name")
            if not isinstance(class_name, str):
                continue
            normalized_class_name = class_name.strip().lower()
            if normalized_class_name:
                class_counts[normalized_class_name] = (
                    class_counts.get(normalized_class_name, 0) + 1
                )
        person_count = class_counts.get("person", 0)
        if person_count == 0:
            continue

        source_id = (
            event_context.source_id
            if event_context is not None
            else sha256(inputs[input_index].encode()).hexdigest()[:32]
        )
        source_type = event_context.source_type if event_context is not None else "upload"
        frame: dict[str, int] = {"detection_count": len(detections)}
        for dimension in ("width", "height"):
            value = prediction.get(dimension)
            if isinstance(value, int) and value > 0:
                frame[dimension] = value

        for binding in workflow_bindings:
            if binding.get("template_key") != PPE_VIOLATION_WEBHOOK_TEMPLATE:
                continue
            workflow_id = binding.get("workflow_id")
            event_types = binding.get("event_types")
            if not isinstance(workflow_id, str) or not isinstance(event_types, list):
                continue
            for event_type, required_class in PPE_EVENT_REQUIREMENTS.items():
                if event_type not in event_types:
                    continue
                required_class_count = class_counts.get(required_class, 0)
                if required_class_count:
                    continue
                events.append(
                    (
                        workflow_id,
                        {
                            "request_id": request_id,
                            "idempotency_key": _event_idempotency_key(
                                request_id,
                                workflow_id,
                                event_type,
                                input_index,
                            ),
                            "deduplication_key": f"{source_id}.{input_index}",
                            "event_type": event_type,
                            "payload": {
                                "source": {
                                    "id": source_id,
                                    "type": source_type,
                                    "input_index": input_index,
                                },
                                "condition": {
                                    "kind": "frame-class-absence.v1",
                                    "required_class": required_class,
                                    "person_count": person_count,
                                    "required_class_count": required_class_count,
                                },
                                "frame": frame,
                            },
                            "occurred_at": occurred_at.isoformat(),
                        },
                    )
                )
    return events


async def _dispatch_vision_events(
    client: httpx.AsyncClient,
    *,
    control_plane_url: str,
    control_headers: dict[str, str],
    timeout_seconds: float,
    events: list[tuple[str, dict[str, Any]]],
) -> None:
    for workflow_id, payload in events:
        try:
            dispatch_response = await client.post(
                (
                    f"{control_plane_url.rstrip('/')}/api/v1/internal/"
                    f"workflow-specs/{workflow_id}/vision-events"
                ),
                headers=control_headers,
                json=payload,
                timeout=timeout_seconds,
            )
        except httpx.TimeoutException as error:
            raise _upstream_error(
                "EVENT_DISPATCH_TIMEOUT",
                "推理已完成，但业务事件提交超时",
                status.HTTP_502_BAD_GATEWAY,
            ) from error
        except httpx.HTTPError as error:
            raise _upstream_error(
                "EVENT_DISPATCH_UNAVAILABLE",
                "推理已完成，但暂时无法连接业务事件服务",
                status.HTTP_502_BAD_GATEWAY,
            ) from error
        if not dispatch_response.is_success:
            raise _upstream_error(
                "EVENT_DISPATCH_FAILED",
                "推理已完成，但业务事件未能确认",
                status.HTTP_502_BAD_GATEWAY,
            )


def create_app(outbound_transport: httpx.AsyncBaseTransport | None = None) -> FastAPI:
    settings = get_settings()
    application = FastAPI(
        title="SenseMu Inference Gateway",
        version="0.1.0",
        description="Stable inference boundary for hosted and marketplace models.",
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.web_origin],
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "X-API-Key", "X-Request-ID"],
        expose_headers=["X-Request-ID", "Retry-After"],
    )

    control_headers = {"X-SenseMu-Gateway-Token": settings.control_plane_token}

    async def resolve_deployment(
        client: httpx.AsyncClient,
        workspace_slug: str,
        endpoint_slug: str,
        api_key: str,
    ) -> dict[str, Any]:
        try:
            resolution = await client.post(
                (
                    f"{settings.control_plane_url.rstrip('/')}/api/v1/internal/"
                    f"inference/workspaces/{workspace_slug}/endpoints/"
                    f"{endpoint_slug}:resolve"
                ),
                headers={**control_headers, "X-API-Key": api_key},
                timeout=settings.control_plane_timeout_seconds,
            )
        except httpx.TimeoutException as error:
            raise _upstream_error(
                "CONTROL_PLANE_TIMEOUT",
                "推理端点解析超时",
                status.HTTP_504_GATEWAY_TIMEOUT,
            ) from error
        except httpx.HTTPError as error:
            raise _upstream_error(
                "CONTROL_PLANE_UNAVAILABLE",
                "暂时无法连接推理控制面",
                status.HTTP_502_BAD_GATEWAY,
            ) from error
        if resolution.status_code == status.HTTP_401_UNAUTHORIZED:
            raise _upstream_error(
                "INVALID_API_KEY",
                "API 密钥无效",
                status.HTTP_401_UNAUTHORIZED,
            )
        if resolution.status_code == status.HTTP_404_NOT_FOUND:
            raise _upstream_error(
                "ENDPOINT_NOT_FOUND",
                "推理端点不存在或已停用",
                status.HTTP_404_NOT_FOUND,
            )
        if not resolution.is_success:
            raise _upstream_error(
                "CONTROL_PLANE_UNAVAILABLE",
                "暂时无法解析推理端点",
                status.HTTP_502_BAD_GATEWAY,
            )
        return resolution.json()

    async def authorize_deployment(
        client: httpx.AsyncClient,
        workspace_slug: str,
        endpoint_slug: str,
        api_key: str,
        request_id: str,
        billable_units: int,
    ) -> dict[str, Any]:
        try:
            authorization = await client.post(
                (
                    f"{settings.control_plane_url.rstrip('/')}/api/v1/internal/"
                    f"inference/workspaces/{workspace_slug}/endpoints/"
                    f"{endpoint_slug}:authorize"
                ),
                headers={**control_headers, "X-API-Key": api_key},
                json={
                    "request_id": request_id,
                    "billable_units": billable_units,
                    "unit": "image",
                },
                timeout=settings.control_plane_timeout_seconds,
            )
        except httpx.TimeoutException as error:
            raise _upstream_error(
                "CONTROL_PLANE_TIMEOUT",
                "推理调用授权超时",
                status.HTTP_504_GATEWAY_TIMEOUT,
            ) from error
        except httpx.HTTPError as error:
            raise _upstream_error(
                "CONTROL_PLANE_UNAVAILABLE",
                "暂时无法连接推理控制面",
                status.HTTP_502_BAD_GATEWAY,
            ) from error
        if authorization.status_code == status.HTTP_401_UNAUTHORIZED:
            raise _upstream_error(
                "INVALID_API_KEY",
                "API 密钥无效",
                status.HTTP_401_UNAUTHORIZED,
            )
        if authorization.status_code == status.HTTP_402_PAYMENT_REQUIRED:
            raise _upstream_error(
                "QUOTA_EXHAUSTED",
                "调用额度不足，请续订后重试",
                status.HTTP_402_PAYMENT_REQUIRED,
            )
        if authorization.status_code == status.HTTP_403_FORBIDDEN:
            raise _upstream_error(
                "SUBSCRIPTION_EXPIRED",
                "调用授权已到期",
                status.HTTP_403_FORBIDDEN,
            )
        if authorization.status_code == status.HTTP_404_NOT_FOUND:
            raise _upstream_error(
                "ENDPOINT_NOT_FOUND",
                "推理端点不存在或已停用",
                status.HTTP_404_NOT_FOUND,
            )
        if not authorization.is_success:
            raise _upstream_error(
                "CONTROL_PLANE_UNAVAILABLE",
                "暂时无法确认推理调用授权",
                status.HTTP_502_BAD_GATEWAY,
            )
        return authorization.json()

    async def release_reservation(
        client: httpx.AsyncClient,
        reservation_id: str | None,
        request_id: str,
    ) -> None:
        if reservation_id is None:
            return
        try:
            await client.post(
                (
                    f"{settings.control_plane_url.rstrip('/')}/api/v1/internal/"
                    f"inference/usage-reservations/{reservation_id}:release"
                ),
                headers=control_headers,
                json={"request_id": request_id},
                timeout=settings.metering_timeout_seconds,
            )
        except httpx.HTTPError:
            return

    def require_runtime() -> str:
        if not settings.runtime_url:
            raise _upstream_error(
                "RUNTIME_NOT_CONFIGURED",
                "推理运行时尚未配置",
                status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return settings.runtime_url.rstrip("/")

    async def call_runtime(
        client: httpx.AsyncClient,
        path: str,
        request_id: str,
        payload: dict[str, Any],
    ) -> httpx.Response:
        runtime_url = require_runtime()
        try:
            runtime_response = await client.post(
                f"{runtime_url}{path}",
                json=payload,
                headers={
                    "X-Request-ID": request_id,
                    "X-SenseMu-Runtime-Token": settings.runtime_token,
                },
                timeout=settings.runtime_timeout_seconds,
            )
        except httpx.TimeoutException as error:
            raise _upstream_error(
                "RUNTIME_TIMEOUT",
                "推理运行时响应超时",
                status.HTTP_504_GATEWAY_TIMEOUT,
            ) from error
        except httpx.HTTPError as error:
            raise _upstream_error(
                "RUNTIME_UNAVAILABLE",
                "暂时无法连接推理运行时",
                status.HTTP_502_BAD_GATEWAY,
            ) from error
        if runtime_response.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
            detail = runtime_response.json().get("detail", {})
            retry_after = runtime_response.headers.get("Retry-After", "1")
            raise _upstream_error(
                "RUNTIME_BUSY",
                str(detail.get("message", "运行时容量已满，请稍后重试")),
                status.HTTP_429_TOO_MANY_REQUESTS,
                headers={"Retry-After": retry_after},
            )
        if runtime_response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT:
            detail = runtime_response.json().get("detail", {})
            raise _upstream_error(
                "INVALID_INFERENCE_INPUT",
                str(detail.get("message", "推理输入不符合运行时要求")),
                status.HTTP_422_UNPROCESSABLE_CONTENT,
            )
        if not runtime_response.is_success:
            raise _upstream_error(
                "RUNTIME_FAILED",
                "推理运行时执行失败",
                status.HTTP_502_BAD_GATEWAY,
            )
        return runtime_response

    @application.get("/health/live")
    def live() -> dict[str, str]:
        return {"service": "sensemu-inference-gateway", "status": "ok"}

    @application.get("/health/ready")
    async def ready() -> JSONResponse:
        async def probe_control_plane(client: httpx.AsyncClient) -> dict[str, Any]:
            try:
                response = await client.get(
                    f"{settings.control_plane_url.rstrip('/')}/health/ready",
                    timeout=settings.health_timeout_seconds,
                )
                if response.is_success:
                    return {"status": "ready"}
            except httpx.HTTPError:
                pass
            return {"status": "unavailable"}

        async def probe_runtime(client: httpx.AsyncClient) -> dict[str, Any]:
            if not settings.runtime_url:
                return {"configured": False, "status": "not_configured"}
            try:
                response = await client.get(
                    f"{settings.runtime_url.rstrip('/')}/health/ready",
                    timeout=settings.health_timeout_seconds,
                )
                if response.is_success:
                    payload = response.json()
                    return {"configured": True, **payload}
            except (httpx.HTTPError, ValueError):
                pass
            return {"configured": True, "status": "unavailable"}

        async with httpx.AsyncClient(transport=outbound_transport) as client:
            control_plane, runtime = await asyncio.gather(
                probe_control_plane(client),
                probe_runtime(client),
            )

        is_ready = control_plane["status"] == "ready" and runtime["status"] == "ready"
        payload = {
            "status": "ready" if is_ready else "not_ready",
            "control_plane": control_plane,
            "runtime": runtime,
        }
        return JSONResponse(
            content=payload,
            status_code=status.HTTP_200_OK if is_ready else status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    @application.get("/inference/v1/runtimes", response_model=RuntimeSummary)
    def runtimes() -> RuntimeSummary:
        return RuntimeSummary(
            configured=bool(settings.runtime_url),
            supported_contracts=["detections.v1"],
        )

    @application.post(
        "/inference/v1/workspaces/{workspace_slug}/endpoints/{endpoint_slug}:prewarm"
    )
    async def prewarm(
        workspace_slug: str,
        endpoint_slug: str,
        response: Response,
        api_key: Annotated[str, Header(alias="X-API-Key", min_length=16, max_length=160)],
        request_id_header: Annotated[
            str | None,
            Header(alias="X-Request-ID", min_length=8, max_length=100),
        ] = None,
    ) -> dict[str, Any]:
        request_id = request_id_header or f"req_{uuid4().hex}"
        async with httpx.AsyncClient(transport=outbound_transport) as client:
            deployment = await resolve_deployment(
                client, workspace_slug, endpoint_slug, api_key
            )
            runtime_response = await call_runtime(
                client,
                "/v1/models:prewarm",
                request_id,
                {
                    "request_id": request_id,
                    "contract": deployment["contract"],
                    "model": {
                        "version_id": deployment["model_version_id"],
                        "artifact_uri": deployment["artifact_uri"],
                        "task_type": deployment["task_type"],
                    },
                },
            )
        response.headers["X-Request-ID"] = request_id
        return {
            "request_id": request_id,
            "workspace": workspace_slug,
            "endpoint": endpoint_slug,
            "model_version_id": deployment["model_version_id"],
            "runtime": runtime_response.json(),
        }

    @application.post(
        "/inference/v1/workspaces/{workspace_slug}/endpoints/{endpoint_slug}:predict"
    )
    async def predict(
        workspace_slug: str,
        endpoint_slug: str,
        request: PredictionRequest,
        response: Response,
        api_key: Annotated[str, Header(alias="X-API-Key", min_length=16, max_length=160)],
        request_id_header: Annotated[
            str | None,
            Header(alias="X-Request-ID", min_length=8, max_length=100),
        ] = None,
    ) -> dict[str, Any]:
        request_id = request_id_header or f"req_{uuid4().hex}"
        async with httpx.AsyncClient(transport=outbound_transport) as client:
            deployment = await authorize_deployment(
                client,
                workspace_slug,
                endpoint_slug,
                api_key,
                request_id,
                len(request.inputs),
            )
            try:
                runtime_response = await call_runtime(
                    client,
                    "/v1/predict",
                    request_id,
                    {
                        "request_id": request_id,
                        "contract": deployment["contract"],
                        "model": {
                            "version_id": deployment["model_version_id"],
                            "artifact_uri": deployment["artifact_uri"],
                            "task_type": deployment["task_type"],
                        },
                        "inputs": request.inputs,
                        "parameters": request.parameters,
                    },
                )
            except HTTPException:
                await release_reservation(
                    client, deployment.get("reservation_id"), request_id
                )
                raise
            try:
                usage_response = await client.post(
                    (
                        f"{settings.control_plane_url.rstrip('/')}/api/v1/internal/"
                        "inference/usage-records"
                    ),
                    headers=control_headers,
                    json={
                        "deployment_id": deployment["deployment_id"],
                        "reservation_id": deployment.get("reservation_id"),
                        "request_id": request_id,
                        "capability_id": deployment["capability_id"],
                        "billable_units": len(request.inputs),
                        "unit": "image",
                        "dimensions": {
                            "contract": deployment["contract"],
                            "input_count": len(request.inputs),
                        },
                        "occurred_at": datetime.now(UTC).isoformat(),
                    },
                    timeout=settings.metering_timeout_seconds,
                )
            except httpx.TimeoutException as error:
                raise _upstream_error(
                    "METERING_TIMEOUT",
                    "推理成功但调用计量确认超时",
                    status.HTTP_502_BAD_GATEWAY,
                ) from error
            except httpx.HTTPError as error:
                raise _upstream_error(
                    "METERING_UNAVAILABLE",
                    "推理成功但暂时无法连接调用计量服务",
                    status.HTTP_502_BAD_GATEWAY,
                ) from error
            if not usage_response.is_success:
                raise _upstream_error(
                    "METERING_FAILED",
                    "推理成功但调用计量未能确认",
                    status.HTTP_502_BAD_GATEWAY,
                )
            runtime_outputs = runtime_response.json()
            events = _ppe_event_payloads(
                workflow_bindings=deployment.get("workflow_bindings", []),
                inputs=request.inputs,
                event_context=request.event_context,
                runtime_outputs=runtime_outputs,
                request_id=request_id,
                occurred_at=datetime.now(UTC),
            )
            await _dispatch_vision_events(
                client,
                control_plane_url=settings.control_plane_url,
                control_headers=control_headers,
                timeout_seconds=settings.control_plane_timeout_seconds,
                events=events,
            )

        response.headers["X-Request-ID"] = request_id
        return {
            "request_id": request_id,
            "workspace": workspace_slug,
            "endpoint": endpoint_slug,
            "model_version_id": deployment["model_version_id"],
            "contract": deployment["contract"],
            "outputs": runtime_outputs,
        }

    return application


app = create_app()


def run() -> None:
    settings = get_settings()
    uvicorn.run(
        "sensemu_gateway.main:app",
        host=settings.host,
        port=settings.port,
        reload=False,
    )


if __name__ == "__main__":
    run()
