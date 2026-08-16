from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session, aliased

from sensemu_api.db.models import (
    DataMarketplaceListing,
    Dataset,
    DatasetVersion,
    MarketplaceLedgerEntry,
    MarketplaceListing,
    MarketplaceListingReview,
    MarketplaceOrder,
    MarketplacePaymentIntent,
    MarketplaceSubscription,
    ProviderProfile,
    UsageRecord,
    Workspace,
)
from sensemu_api.provider_schemas import (
    ProviderAlgorithmListingResponse,
    ProviderDashboardResponse,
    ProviderDataListingResponse,
    ProviderEarningResponse,
    ProviderProfileResponse,
    ProviderProfileUpdate,
    ProviderSaleResponse,
)


def _micros_to_yuan(amount_micros: int | Decimal) -> float:
    return float(Decimal(amount_micros) / Decimal(1_000_000))


def _profile_response(profile: ProviderProfile) -> ProviderProfileResponse:
    return ProviderProfileResponse(
        id=profile.id,
        workspace_id=profile.workspace_id,
        public_name=profile.public_name,
        summary=profile.summary,
        provider_type=profile.provider_type,
        support_email=profile.support_email,
        website_url=profile.website_url,
        service_regions=profile.service_regions,
        support_commitment=profile.support_commitment,
        onboarding_status=profile.onboarding_status,
        identity_verification_status=profile.identity_verification_status,
        payout_onboarding_status=profile.payout_onboarding_status,
        review_status=profile.review_status,
        created_at=profile.created_at,
        updated_at=profile.updated_at,
    )


def get_profile(
    session: Session,
    workspace_id: UUID,
) -> ProviderProfileResponse | None:
    profile = session.scalar(
        select(ProviderProfile).where(ProviderProfile.workspace_id == workspace_id)
    )
    return _profile_response(profile) if profile else None


def update_profile(
    session: Session,
    workspace_id: UUID,
    payload: ProviderProfileUpdate,
) -> ProviderProfileResponse:
    profile = session.scalar(
        select(ProviderProfile)
        .where(ProviderProfile.workspace_id == workspace_id)
        .with_for_update()
    )
    values = payload.model_dump(mode="json")
    if profile is None:
        profile = ProviderProfile(
            workspace_id=workspace_id,
            **values,
            onboarding_status="profile_complete",
            identity_verification_status="not_started",
            payout_onboarding_status="not_started",
            review_status="not_submitted",
        )
        session.add(profile)
    else:
        for field, value in values.items():
            setattr(profile, field, value)
        profile.onboarding_status = "profile_complete"
    session.flush()
    return _profile_response(profile)


def _algorithm_listings(
    session: Session,
    workspace_id: UUID,
) -> list[ProviderAlgorithmListingResponse]:
    now = datetime.now(UTC)
    listings = session.scalars(
        select(MarketplaceListing)
        .where(MarketplaceListing.provider_workspace_id == workspace_id)
        .order_by(MarketplaceListing.published_at.desc())
    ).all()
    responses: list[ProviderAlgorithmListingResponse] = []
    for listing in listings:
        latest_review = session.scalar(
            select(MarketplaceListingReview)
            .where(MarketplaceListingReview.listing_id == listing.id)
            .order_by(
                MarketplaceListingReview.reviewed_at.desc(),
                MarketplaceListingReview.id.desc(),
            )
            .limit(1)
        )
        active_grants = session.scalar(
            select(func.count(MarketplaceSubscription.id)).where(
                MarketplaceSubscription.listing_id == listing.id,
                MarketplaceSubscription.status == "active",
                MarketplaceSubscription.expires_at > now,
                MarketplaceSubscription.consumed_units
                + MarketplaceSubscription.reserved_units
                < MarketplaceSubscription.quota_units,
            )
        )
        successful_units = session.scalar(
            select(func.coalesce(func.sum(UsageRecord.billable_units), 0))
            .join(
                MarketplaceSubscription,
                MarketplaceSubscription.id == UsageRecord.subscription_id,
            )
            .where(MarketplaceSubscription.listing_id == listing.id)
        )
        responses.append(
            ProviderAlgorithmListingResponse(
                id=listing.id,
                title=listing.title,
                category=listing.category,
                status=listing.status,
                price_per_1000_cents=listing.price_per_1000_cents,
                monthly_quota_units=listing.monthly_quota_units,
                active_customer_grants=int(active_grants or 0),
                successful_units=float(successful_units or 0),
                published_at=listing.published_at,
                review_note=latest_review.note if latest_review else None,
                reviewed_at=latest_review.reviewed_at if latest_review else None,
            )
        )
    return responses


def _data_listings(
    session: Session,
    workspace_id: UUID,
) -> list[ProviderDataListingResponse]:
    rows = session.execute(
        select(DataMarketplaceListing, DatasetVersion, Dataset)
        .join(
            DatasetVersion,
            DatasetVersion.id == DataMarketplaceListing.dataset_version_id,
        )
        .join(Dataset, Dataset.id == DatasetVersion.dataset_id)
        .where(DataMarketplaceListing.provider_workspace_id == workspace_id)
        .order_by(DataMarketplaceListing.published_at.desc())
    ).all()
    return [
        ProviderDataListingResponse(
            id=listing.id,
            title=listing.title,
            dataset_name=dataset.name,
            dataset_version_number=version.version_number,
            asset_count=version.asset_count,
            license_code=listing.license_code,
            status=listing.status,
            published_at=listing.published_at,
        )
        for listing, version, dataset in rows
    ]


def _sales(
    session: Session,
    workspace_id: UUID,
    limit: int,
) -> list[ProviderSaleResponse]:
    buyer = aliased(Workspace)
    rows = session.execute(
        select(
            MarketplaceOrder,
            MarketplaceListing,
            buyer,
            MarketplacePaymentIntent,
        )
        .join(MarketplaceListing, MarketplaceListing.id == MarketplaceOrder.listing_id)
        .join(buyer, buyer.id == MarketplaceOrder.buyer_workspace_id)
        .outerjoin(
            MarketplacePaymentIntent,
            MarketplacePaymentIntent.order_id == MarketplaceOrder.id,
        )
        .where(MarketplaceOrder.provider_workspace_id == workspace_id)
        .order_by(MarketplaceOrder.created_at.desc(), MarketplaceOrder.id)
        .limit(limit)
    ).all()
    return [
        ProviderSaleResponse(
            id=order.id,
            order_number=order.order_number,
            listing_title=listing.title,
            buyer_name=buyer_workspace.name,
            authorization_amount_yuan=_micros_to_yuan(
                order.authorization_amount_micros
            ),
            payment_status=order.payment_status,
            payment_intent_status=payment_intent.status if payment_intent else None,
            payment_provider=payment_intent.provider if payment_intent else None,
            paid_amount_yuan=(
                _micros_to_yuan(payment_intent.paid_amount_micros)
                if payment_intent
                else 0
            ),
            refunded_amount_yuan=(
                _micros_to_yuan(payment_intent.refunded_amount_micros)
                if payment_intent
                else 0
            ),
            created_at=order.created_at,
        )
        for order, listing, buyer_workspace, payment_intent in rows
    ]


def _earnings(
    session: Session,
    workspace_id: UUID,
    limit: int,
) -> list[ProviderEarningResponse]:
    buyer = aliased(Workspace)
    rows = session.execute(
        select(MarketplaceLedgerEntry, UsageRecord, MarketplaceListing, buyer)
        .join(UsageRecord, UsageRecord.id == MarketplaceLedgerEntry.usage_record_id)
        .join(
            MarketplaceListing,
            MarketplaceListing.id == MarketplaceLedgerEntry.listing_id,
        )
        .join(buyer, buyer.id == MarketplaceLedgerEntry.buyer_workspace_id)
        .where(MarketplaceLedgerEntry.provider_workspace_id == workspace_id)
        .order_by(
            MarketplaceLedgerEntry.occurred_at.desc(),
            MarketplaceLedgerEntry.id,
        )
        .limit(limit)
    ).all()
    return [
        ProviderEarningResponse(
            id=entry.id,
            listing_title=listing.title,
            buyer_name=buyer_workspace.name,
            request_id=usage.request_id,
            amount_yuan=_micros_to_yuan(entry.amount_micros),
            settlement_status=entry.settlement_status,
            occurred_at=entry.occurred_at,
        )
        for entry, usage, listing, buyer_workspace in rows
    ]


def get_dashboard(
    session: Session,
    workspace_id: UUID,
    *,
    limit: int = 50,
) -> ProviderDashboardResponse:
    profile = get_profile(session, workspace_id)
    algorithm_listings = _algorithm_listings(session, workspace_id)
    data_listings = _data_listings(session, workspace_id)
    sales = _sales(session, workspace_id, limit)
    earnings = _earnings(session, workspace_id, limit)
    sales_totals = session.execute(
        select(
            func.coalesce(func.sum(MarketplaceOrder.authorization_amount_micros), 0),
            func.coalesce(func.sum(MarketplacePaymentIntent.paid_amount_micros), 0),
            func.coalesce(func.sum(MarketplacePaymentIntent.refunded_amount_micros), 0),
        )
        .outerjoin(
            MarketplacePaymentIntent,
            MarketplacePaymentIntent.order_id == MarketplaceOrder.id,
        )
        .where(MarketplaceOrder.provider_workspace_id == workspace_id)
    ).one()
    unsettled_micros = session.scalar(
        select(func.coalesce(func.sum(MarketplaceLedgerEntry.amount_micros), 0)).where(
            MarketplaceLedgerEntry.provider_workspace_id == workspace_id,
            MarketplaceLedgerEntry.settlement_status == "unsettled",
        )
    )
    return ProviderDashboardResponse(
        profile=profile,
        algorithm_listing_count=len(algorithm_listings),
        data_listing_count=len(data_listings),
        active_customer_grants=sum(
            listing.active_customer_grants for listing in algorithm_listings
        ),
        successful_units=sum(
            listing.successful_units for listing in algorithm_listings
        ),
        authorized_sales_yuan=_micros_to_yuan(sales_totals[0] or 0),
        paid_sales_yuan=_micros_to_yuan(sales_totals[1] or 0),
        refunded_sales_yuan=_micros_to_yuan(sales_totals[2] or 0),
        unsettled_earnings_yuan=_micros_to_yuan(unsettled_micros or 0),
        algorithm_listings=algorithm_listings,
        data_listings=data_listings,
        sales=sales,
        earnings=earnings,
    )
