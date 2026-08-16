from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, status
from sqlalchemy.orm import Session

from sensemu_api import marketplace_service
from sensemu_api.config import get_settings
from sensemu_api.db.session import get_session
from sensemu_api.dependencies import WorkspaceAdminId, WorkspaceId
from sensemu_api.gateway_auth import GatewayAuth
from sensemu_api.marketplace_schemas import (
    GatewayAuthorizationResponse,
    InferenceAuthorizationCreate,
    MarketplaceBillingResponse,
    MarketplaceCheckoutResponse,
    MarketplaceDailyReconciliationResponse,
    MarketplaceListingCreate,
    MarketplaceListingResponse,
    MarketplaceListingReviewCreate,
    MarketplaceListingReviewResponse,
    MarketplaceListingSubmissionResponse,
    MarketplaceSubscriptionResponse,
    MarketplaceSubscriptionSecretResponse,
    MarketplaceUsageRecordResponse,
    UsageReservationRecoveryResponse,
    UsageReservationRelease,
    UsageReservationResponse,
)
from sensemu_api.platform_review_auth import PlatformReviewAuth
from sensemu_api.worker_auth import WorkerAuth

router = APIRouter(prefix="/api/v1", tags=["marketplace"])
SessionDep = Annotated[Session, Depends(get_session)]
ApiKey = Annotated[str, Header(alias="X-API-Key", min_length=16, max_length=160)]


@router.post(
    "/capability-specs/{capability_spec_id}/marketplace-listing",
    response_model=MarketplaceListingResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_marketplace_listing(
    capability_spec_id: UUID,
    payload: MarketplaceListingCreate,
    workspace_id: WorkspaceAdminId,
    session: SessionDep,
) -> MarketplaceListingResponse:
    return marketplace_service.create_listing(
        session, workspace_id, capability_spec_id, payload
    )


@router.post(
    "/internal/marketplace/listings/{listing_id}:review",
    response_model=MarketplaceListingReviewResponse,
    include_in_schema=False,
)
def review_marketplace_listing(
    listing_id: UUID,
    payload: MarketplaceListingReviewCreate,
    session: SessionDep,
    _platform_review_auth: PlatformReviewAuth,
) -> MarketplaceListingReviewResponse:
    return marketplace_service.review_listing(session, listing_id, payload)


@router.get(
    "/marketplace/listings",
    response_model=list[MarketplaceListingResponse],
)
def list_marketplace_listings(
    workspace_id: WorkspaceId,
    session: SessionDep,
) -> list[MarketplaceListingResponse]:
    return marketplace_service.list_listings(session, workspace_id)


@router.get(
    "/marketplace/submissions",
    response_model=list[MarketplaceListingSubmissionResponse],
)
def list_marketplace_submissions(
    workspace_id: WorkspaceId,
    session: SessionDep,
) -> list[MarketplaceListingSubmissionResponse]:
    return marketplace_service.list_submissions(session, workspace_id)


@router.post(
    "/marketplace/listings/{listing_id}/subscriptions",
    response_model=MarketplaceCheckoutResponse,
    status_code=status.HTTP_201_CREATED,
)
def subscribe_marketplace_listing(
    listing_id: UUID,
    workspace_id: WorkspaceAdminId,
    session: SessionDep,
) -> MarketplaceCheckoutResponse:
    return marketplace_service.subscribe(session, workspace_id, listing_id)


@router.get(
    "/marketplace/subscriptions",
    response_model=list[MarketplaceSubscriptionResponse],
)
def list_marketplace_subscriptions(
    workspace_id: WorkspaceId,
    session: SessionDep,
) -> list[MarketplaceSubscriptionResponse]:
    return marketplace_service.list_subscriptions(session, workspace_id)


@router.get(
    "/marketplace/usage-records",
    response_model=list[MarketplaceUsageRecordResponse],
)
def list_marketplace_usage_records(
    workspace_id: WorkspaceId,
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[MarketplaceUsageRecordResponse]:
    return marketplace_service.list_usage_records(
        session, workspace_id, limit=limit
    )


@router.get(
    "/marketplace/billing",
    response_model=MarketplaceBillingResponse,
)
def get_marketplace_billing(
    workspace_id: WorkspaceId,
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> MarketplaceBillingResponse:
    return marketplace_service.get_billing(
        session, workspace_id, limit=limit
    )


@router.get(
    "/internal/marketplace/reconciliation/daily",
    response_model=MarketplaceDailyReconciliationResponse,
    include_in_schema=False,
)
def get_daily_marketplace_reconciliation(
    session: SessionDep,
    _platform_review_auth: PlatformReviewAuth,
    report_date: Annotated[date | None, Query(alias="date")] = None,
) -> MarketplaceDailyReconciliationResponse:
    return marketplace_service.reconcile_daily(session, report_date)


@router.post(
    "/marketplace/subscriptions/{subscription_id}:claim-key",
    response_model=MarketplaceSubscriptionSecretResponse,
)
def claim_marketplace_subscription_key(
    subscription_id: UUID,
    workspace_id: WorkspaceAdminId,
    session: SessionDep,
) -> MarketplaceSubscriptionSecretResponse:
    subscription, api_key = marketplace_service.claim_subscription_key(
        session, workspace_id, subscription_id
    )
    return MarketplaceSubscriptionSecretResponse(
        **subscription.model_dump(), api_key=api_key
    )


@router.post(
    "/marketplace/subscriptions/{subscription_id}:rotate-key",
    response_model=MarketplaceSubscriptionSecretResponse,
)
def rotate_marketplace_subscription_key(
    subscription_id: UUID,
    workspace_id: WorkspaceAdminId,
    session: SessionDep,
) -> MarketplaceSubscriptionSecretResponse:
    subscription, api_key = marketplace_service.rotate_subscription_key(
        session, workspace_id, subscription_id
    )
    return MarketplaceSubscriptionSecretResponse(
        **subscription.model_dump(), api_key=api_key
    )


@router.post(
    "/internal/inference/workspaces/{workspace_slug}/endpoints/{endpoint_slug}:authorize",
    response_model=GatewayAuthorizationResponse,
    include_in_schema=False,
)
def authorize_marketplace_inference(
    workspace_slug: str,
    endpoint_slug: str,
    payload: InferenceAuthorizationCreate,
    api_key: ApiKey,
    session: SessionDep,
    _gateway_auth: GatewayAuth,
) -> GatewayAuthorizationResponse:
    return marketplace_service.authorize_inference(
        session, workspace_slug, endpoint_slug, api_key, payload
    )


@router.post(
    "/internal/inference/usage-reservations/{reservation_id}:release",
    response_model=UsageReservationResponse,
    include_in_schema=False,
)
def release_marketplace_reservation(
    reservation_id: UUID,
    payload: UsageReservationRelease,
    session: SessionDep,
    _gateway_auth: GatewayAuth,
) -> UsageReservationResponse:
    return marketplace_service.release_reservation(
        session, reservation_id, payload.request_id
    )


@router.post(
    "/internal/inference/usage-reservations:recover-stale",
    response_model=UsageReservationRecoveryResponse,
    include_in_schema=False,
)
def recover_stale_marketplace_reservations(
    session: SessionDep,
    _worker_auth: WorkerAuth,
) -> UsageReservationRecoveryResponse:
    recovered = marketplace_service.recover_stale_reservations(
        session,
        timeout_seconds=get_settings().inference_reservation_timeout_seconds,
    )
    return UsageReservationRecoveryResponse(recovered=recovered)
