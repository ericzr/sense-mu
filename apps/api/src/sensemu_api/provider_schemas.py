from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl, field_validator

ProviderRegion = Literal[
    "中国大陆",
    "中国香港",
    "亚太",
    "欧洲",
    "北美",
    "全球",
]


class ProviderProfileUpdate(BaseModel):
    public_name: str = Field(min_length=2, max_length=160)
    summary: str = Field(min_length=12, max_length=1_200)
    provider_type: Literal["organization", "individual"]
    support_email: str = Field(min_length=3, max_length=320)
    website_url: HttpUrl | None = None
    service_regions: list[ProviderRegion] = Field(min_length=1, max_length=6)
    support_commitment: str = Field(min_length=8, max_length=1_200)

    @field_validator("support_email")
    @classmethod
    def validate_support_email(cls, value: str) -> str:
        cleaned = value.strip()
        local, separator, domain = cleaned.rpartition("@")
        if not separator or not local or "." not in domain or any(
            character.isspace() for character in cleaned
        ):
            raise ValueError("请输入有效的支持邮箱")
        return cleaned

    @field_validator("service_regions")
    @classmethod
    def unique_regions(cls, value: list[ProviderRegion]) -> list[ProviderRegion]:
        return list(dict.fromkeys(value))


class ProviderProfileResponse(BaseModel):
    id: UUID
    workspace_id: UUID
    public_name: str
    summary: str
    provider_type: str
    support_email: str
    website_url: str | None
    service_regions: list[str]
    support_commitment: str
    onboarding_status: str
    identity_verification_status: str
    payout_onboarding_status: str
    review_status: str
    created_at: datetime
    updated_at: datetime


class ProviderAlgorithmListingResponse(BaseModel):
    id: UUID
    title: str
    category: str
    status: str
    price_per_1000_cents: int
    monthly_quota_units: int
    active_customer_grants: int
    successful_units: float
    published_at: datetime | None
    review_note: str | None
    reviewed_at: datetime | None


class ProviderDataListingResponse(BaseModel):
    id: UUID
    title: str
    dataset_name: str
    dataset_version_number: int
    asset_count: int
    license_code: str
    status: str
    published_at: datetime


class ProviderSaleResponse(BaseModel):
    id: UUID
    order_number: str
    listing_title: str
    buyer_name: str
    authorization_amount_yuan: float
    payment_status: str
    payment_intent_status: str | None
    payment_provider: str | None
    paid_amount_yuan: float
    refunded_amount_yuan: float
    created_at: datetime


class ProviderEarningResponse(BaseModel):
    id: UUID
    listing_title: str
    buyer_name: str
    request_id: str
    amount_yuan: float
    settlement_status: str
    occurred_at: datetime


class ProviderDashboardResponse(BaseModel):
    profile: ProviderProfileResponse | None
    algorithm_listing_count: int
    data_listing_count: int
    active_customer_grants: int
    successful_units: float
    authorized_sales_yuan: float
    paid_sales_yuan: float
    refunded_sales_yuan: float
    unsettled_earnings_yuan: float
    algorithm_listings: list[ProviderAlgorithmListingResponse]
    data_listings: list[ProviderDataListingResponse]
    sales: list[ProviderSaleResponse]
    earnings: list[ProviderEarningResponse]
