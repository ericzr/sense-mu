import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from sensemu_api.config import get_settings
from sensemu_api.routes.batch_inference import router as batch_inference_router
from sensemu_api.routes.catalog import router as catalog_router
from sensemu_api.routes.collaboration import router as collaboration_router
from sensemu_api.routes.data_market import router as data_market_router
from sensemu_api.routes.deployments import router as deployments_router
from sensemu_api.routes.dev_storage import router as dev_storage_router
from sensemu_api.routes.evaluation import router as evaluation_router
from sensemu_api.routes.health import router as health_router
from sensemu_api.routes.identity import router as identity_router
from sensemu_api.routes.marketplace import router as marketplace_router
from sensemu_api.routes.overview import router as overview_router
from sensemu_api.routes.payments import router as payments_router
from sensemu_api.routes.providers import router as providers_router
from sensemu_api.routes.training import router as training_router
from sensemu_api.routes.vision_events import router as vision_events_router
from sensemu_api.routes.workflows import router as workflows_router


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(
        title="SenseMu API",
        version="0.1.0",
        description="Core business API for the SenseMu vision AI platform.",
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.web_origin],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "Idempotency-Key",
            "X-Workspace-ID",
        ],
    )
    application.include_router(health_router)
    application.include_router(identity_router)
    application.include_router(overview_router)
    application.include_router(catalog_router)
    application.include_router(collaboration_router)
    application.include_router(data_market_router)
    application.include_router(training_router)
    application.include_router(batch_inference_router)
    application.include_router(workflows_router)
    application.include_router(vision_events_router)
    application.include_router(evaluation_router)
    application.include_router(deployments_router)
    application.include_router(marketplace_router)
    application.include_router(payments_router)
    application.include_router(providers_router)
    application.include_router(dev_storage_router)
    return application


app = create_app()


def run() -> None:
    uvicorn.run("sensemu_api.main:app", host="0.0.0.0", port=8000, reload=False)


if __name__ == "__main__":
    run()
