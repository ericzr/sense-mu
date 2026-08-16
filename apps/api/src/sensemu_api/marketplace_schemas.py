from datetime import date, datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

from sensemu_api.deployment_schemas import GatewayDeploymentResponse


class MarketplaceListingCreate(BaseModel):
    title: str = Field(min_length=2, max_length=180)
    summary: str = Field(min_length=8, max_length=1000)
    price_per_1000_cents: int = Field(ge=0, le=10_000_000)
    monthly_quota_units: int = Field(ge=10, le=10_000_000)


class MarketplaceListingResponse(BaseModel):
    id: UUID
    provider_workspace_id: UUID
    provider_name: str
    deployment_id: UUID
    capability_spec_id: UUID | None
    capability_slug: str | None
    capability_version_number: int | None
    capability_display_name: str | None
    capability_problem_definition: str | None
    capability_output_contract: str | None
    capability_verified_scenes: list[str]
    capability_unsupported_conditions: list[str]
    endpoint_url: str
    model_name: str
    model_version_number: int
    task_type: str
    title: str
    summary: str
    category: str
    pricing_unit: str
    price_per_1000_cents: int
    monthly_quota_units: int
    status: str
    published_at: datetime | None
    subscription_id: UUID | None = None
    subscription_status: str | None = None
    remaining_units: int | None = None


class MarketplaceListingSubmissionResponse(MarketplaceListingResponse):
    review_note: str | None = None
    reviewed_at: datetime | None = None


class MarketplaceSubscriptionResponse(BaseModel):
    id: UUID
    listing_id: UUID
    buyer_workspace_id: UUID
    listing_title: str
    provider_name: str
    endpoint_url: str
    status: str
    quota_units: int
    reserved_units: int
    consumed_units: int
    remaining_units: int
    price_per_1000_cents: int
    api_key_prefix: str | None
    credential_claimed_at: datetime | None
    started_at: datetime | None
    expires_at: datetime | None
    order_number: str | None = None
    payment_status: str | None = None


class MarketplaceSubscriptionSecretResponse(MarketplaceSubscriptionResponse):
    api_key: str


class MarketplaceCheckoutResponse(MarketplaceSubscriptionResponse):
    payment_intent_id: UUID
    payment_intent_status: str
    expected_amount_yuan: float
    payment_provider: str | None
    checkout_available: bool = False
    reused: bool = False


class MarketplaceListingReviewCreate(BaseModel):
    decision: Literal["approved", "rejected"]
    reviewer_identity: str = Field(min_length=2, max_length=160)
    note: str | None = Field(default=None, max_length=1_200)


class MarketplaceListingReviewResponse(BaseModel):
    listing_id: UUID
    status: str
    decision: str
    reviewer_identity: str
    note: str | None
    reviewed_at: datetime


class InferenceAuthorizationCreate(BaseModel):
    request_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,99}$")
    billable_units: int = Field(ge=1, le=4)
    unit: Literal["image"] = "image"


class GatewayAuthorizationResponse(GatewayDeploymentResponse):
    reservation_id: UUID | None = None
    subscription_id: UUID | None = None
    remaining_units: int | None = None


class UsageReservationRelease(BaseModel):
    request_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,99}$")


class UsageReservationResponse(BaseModel):
    id: UUID
    request_id: str
    subscription_id: UUID
    deployment_id: UUID
    units: int
    status: str
    finalized_at: datetime | None


class UsageReservationRecoveryItem(BaseModel):
    reservation_id: UUID
    subscription_id: UUID
    request_id: str
    released_units: int
    recovered_at: datetime


class UsageReservationRecoveryResponse(BaseModel):
    recovered: list[UsageReservationRecoveryItem]


class MarketplaceUsageRecordResponse(BaseModel):
    id: UUID
    request_id: str
    subscription_id: UUID
    listing_id: UUID
    listing_title: str
    provider_name: str
    billable_units: float
    unit: str
    estimated_cost_yuan: float
    dimensions: dict[str, Any]
    occurred_at: datetime


class MarketplaceOrderResponse(BaseModel):
    id: UUID
    order_number: str
    listing_id: UUID
    subscription_id: UUID
    listing_title: str
    provider_name: str
    currency: str
    price_per_1000_cents: int
    quota_units: int
    authorization_amount_yuan: float
    status: str
    payment_status: str
    entitlement_started_at: datetime | None
    entitlement_expires_at: datetime | None
    created_at: datetime
    payment_intent_id: UUID | None = None
    payment_intent_status: str | None = None
    payment_provider: str | None = None
    paid_amount_yuan: float = 0
    refunded_amount_yuan: float = 0


class MarketplaceEarningResponse(BaseModel):
    id: UUID
    usage_record_id: UUID
    request_id: str
    listing_title: str
    buyer_name: str
    amount_yuan: float
    currency: str
    settlement_status: str
    occurred_at: datetime


class MarketplaceBillingResponse(BaseModel):
    authorization_ceiling_yuan: float
    unsettled_earnings_yuan: float
    orders: list[MarketplaceOrderResponse]
    earnings: list[MarketplaceEarningResponse]


class MarketplaceReconciliationIssue(BaseModel):
    code: str
    count: int
    detail: str


class MarketplaceDailyReconciliationResponse(BaseModel):
    report_date: date
    timezone: Literal["UTC"] = "UTC"
    orders_created: int
    order_authorization_yuan: float
    payment_success_events: int
    payment_success_yuan: float
    refund_success_events: int
    refund_success_yuan: float
    successful_usage_requests: int
    successful_usage_units: float
    marketplace_usage_requests: int
    marketplace_usage_units: float
    provider_earnings_yuan: float
    ledger_entries: int
    stale_pending_reservations: int
    stale_pending_reservation_units: int
    issues: list[MarketplaceReconciliationIssue]
    is_reconciled: bool
