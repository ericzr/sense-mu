from pathlib import Path
from secrets import compare_digest
from typing import Annotated, Any
from uuid import UUID

import uvicorn
from fastapi import FastAPI, Header, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from sensemu_runtime.config import get_settings
from sensemu_runtime.service import (
    ModelCache,
    PredictionService,
    RuntimeBusyError,
    RuntimeExecutionError,
    RuntimeInputError,
    ultralytics_predictor_factory,
)
from sensemu_runtime.storage import create_object_store

RuntimeInput = Annotated[str, Field(min_length=1, max_length=12_000_000)]


class RuntimeModel(BaseModel):
    version_id: UUID
    artifact_uri: str = Field(min_length=1, max_length=2048)
    task_type: str = Field(min_length=1, max_length=40)


class RuntimeParameters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    confidence: float = Field(default=0.25, ge=0, le=1, allow_inf_nan=False)
    iou: float = Field(default=0.7, ge=0, le=1, allow_inf_nan=False)
    max_detections: int = Field(default=300, ge=1, le=300)
    image_size: int = Field(default=640, ge=320, le=1536, multiple_of=32)


class RuntimePredictionRequest(BaseModel):
    request_id: str = Field(min_length=8, max_length=100)
    contract: str = Field(min_length=1, max_length=64)
    model: RuntimeModel
    inputs: list[RuntimeInput] = Field(min_length=1, max_length=4)
    parameters: RuntimeParameters = Field(default_factory=RuntimeParameters)


class RuntimePrewarmRequest(BaseModel):
    request_id: str = Field(min_length=8, max_length=100)
    contract: str = Field(min_length=1, max_length=64)
    model: RuntimeModel


def create_prediction_service() -> PredictionService:
    settings = get_settings()
    store = create_object_store(settings)
    cache = ModelCache(
        store,
        cache_root=Path(settings.cache_path),
        factory=ultralytics_predictor_factory,
        max_models=settings.max_cached_models,
        max_model_bytes=settings.max_model_bytes,
    )
    return PredictionService(
        store,
        cache,
        device=settings.device,
        max_input_bytes=settings.max_input_bytes,
        max_concurrent_requests=settings.max_concurrent_requests,
        queue_timeout_seconds=settings.queue_timeout_seconds,
    )


def create_app(prediction_service: PredictionService | None = None) -> FastAPI:
    settings = get_settings()
    service = prediction_service or create_prediction_service()
    application = FastAPI(
        title="SenseMu Ultralytics Runtime",
        version="0.1.0",
        description="Restricted internal object-detection runtime.",
    )

    @application.get("/health/live")
    def live() -> dict[str, str]:
        return {"service": "sensemu-inference-runtime", "status": "ok"}

    @application.get("/health/ready")
    def ready() -> dict[str, Any]:
        capacity = service.capacity_summary()
        return {
            "status": "ready",
            "accepting_requests": capacity["available_slots"] > 0,
            "cache": service.cache.summary(),
            "capacity": capacity,
        }

    def authorize_runtime(runtime_token: str) -> None:
        if not compare_digest(runtime_token, settings.token):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "INVALID_RUNTIME_TOKEN", "message": "运行时凭据无效"},
            )

    def validate_contract(contract: str) -> None:
        if contract != "detections.v1":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail={"code": "UNSUPPORTED_CONTRACT", "message": "运行时不支持该推理协议"},
            )

    def raise_runtime_error(error: Exception) -> None:
        if isinstance(error, RuntimeBusyError):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                headers={"Retry-After": str(max(1, round(service.queue_timeout_seconds)))},
                detail={"code": "RUNTIME_BUSY", "message": str(error)},
            ) from error
        if isinstance(error, RuntimeInputError):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail={"code": "INVALID_INFERENCE_INPUT", "message": str(error)},
            ) from error
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "INFERENCE_FAILED", "message": str(error)},
        ) from error

    @application.post("/v1/models:prewarm")
    def prewarm(
        payload: RuntimePrewarmRequest,
        runtime_token: Annotated[
            str,
            Header(alias="X-SenseMu-Runtime-Token", min_length=16, max_length=160),
        ],
    ) -> dict[str, Any]:
        authorize_runtime(runtime_token)
        validate_contract(payload.contract)
        try:
            cache_hit = service.prewarm(
                model_version_id=str(payload.model.version_id),
                artifact_uri=payload.model.artifact_uri,
                task_type=payload.model.task_type,
            )
        except (RuntimeBusyError, RuntimeInputError, RuntimeExecutionError) as error:
            raise_runtime_error(error)
        return {
            "request_id": payload.request_id,
            "model_version_id": str(payload.model.version_id),
            "cache_hit": cache_hit,
            "cache": service.cache.summary(),
            "capacity": service.capacity_summary(),
        }

    @application.post("/v1/predict")
    def predict(
        payload: RuntimePredictionRequest,
        runtime_token: Annotated[
            str,
            Header(alias="X-SenseMu-Runtime-Token", min_length=16, max_length=160),
        ],
    ) -> dict[str, Any]:
        authorize_runtime(runtime_token)
        validate_contract(payload.contract)
        try:
            predictions, inference_ms = service.predict(
                model_version_id=str(payload.model.version_id),
                artifact_uri=payload.model.artifact_uri,
                task_type=payload.model.task_type,
                inputs=payload.inputs,
                confidence=payload.parameters.confidence,
                iou=payload.parameters.iou,
                max_detections=payload.parameters.max_detections,
                image_size=payload.parameters.image_size,
            )
        except (RuntimeBusyError, RuntimeInputError, RuntimeExecutionError) as error:
            raise_runtime_error(error)
        return {
            "request_id": payload.request_id,
            "contract": payload.contract,
            "predictions": predictions,
            "runtime": {
                "engine": "ultralytics",
                "device": settings.device,
                "inference_ms": round(inference_ms, 3),
            },
        }

    return application


app = create_app()


def run() -> None:
    settings = get_settings()
    uvicorn.run(
        "sensemu_runtime.main:app",
        host=settings.host,
        port=settings.port,
        reload=False,
    )


if __name__ == "__main__":
    run()
