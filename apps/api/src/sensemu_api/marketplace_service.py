from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from hashlib import sha256
from secrets import compare_digest, token_urlsafe
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, aliased

from sensemu_api.catalog_service import conflict, require_workspace
from sensemu_api.config import get_settings
from sensemu_api.db.models import (
    CapabilitySpec,
    Deployment,
    MarketplaceLedgerEntry,
    MarketplaceListing,
    MarketplaceListingReview,
    MarketplaceOrder,
    MarketplacePaymentEvent,
    MarketplacePaymentIntent,
    MarketplaceSubscription,
    Model,
    ModelVersion,
    Project,
    UsageRecord,
    UsageReservation,
    Workspace,
)
from sensemu_api.deployment_service import _contract_for
from sensemu_api.marketplace_entitlement import (
    PAID_ORDER_STATUSES,
    activate_entitlement,
)
from sensemu_api.marketplace_schemas import (
    GatewayAuthorizationResponse,
    InferenceAuthorizationCreate,
    MarketplaceBillingResponse,
    MarketplaceCheckoutResponse,
    MarketplaceDailyReconciliationResponse,
    MarketplaceEarningResponse,
    MarketplaceListingCreate,
    MarketplaceListingResponse,
    MarketplaceListingReviewCreate,
    MarketplaceListingReviewResponse,
    MarketplaceListingSubmissionResponse,
    MarketplaceOrderResponse,
    MarketplaceReconciliationIssue,
    MarketplaceSubscriptionResponse,
    MarketplaceUsageRecordResponse,
    UsageReservationRecoveryItem,
    UsageReservationResponse,
)
from sensemu_api.workflow_service import event_bindings_for_deployment


def _key_hash(api_key: str) -> str:
    return sha256(api_key.encode()).hexdigest()


def _new_marketplace_key() -> tuple[str, str, str]:
    api_key = f"smu_market_{token_urlsafe(32)}"
    return api_key, api_key[:18], _key_hash(api_key)


def _new_order_number() -> str:
    return f"smu_ord_{uuid4().hex[:24]}"


def _latest_order(
    session: Session,
    subscription_id: UUID,
) -> MarketplaceOrder | None:
    return session.scalar(
        select(MarketplaceOrder)
        .where(MarketplaceOrder.subscription_id == subscription_id)
        .order_by(MarketplaceOrder.created_at.desc(), MarketplaceOrder.id.desc())
        .limit(1)
    )


def _micros_to_yuan(amount_micros: int) -> float:
    return float(Decimal(amount_micros) / Decimal(1_000_000))


def _endpoint_url(workspace_slug: str, endpoint_slug: str) -> str:
    settings = get_settings()
    return (
        f"{settings.inference_gateway_public_url.rstrip('/')}/inference/v1/workspaces/"
        f"{workspace_slug}/endpoints/{endpoint_slug}:predict"
    )


def create_listing(
    session: Session,
    workspace_id: UUID,
    capability_spec_id: UUID,
    payload: MarketplaceListingCreate,
) -> MarketplaceListingResponse:
    record = session.execute(
        select(CapabilitySpec, Deployment, ModelVersion, Model, Project)
        .join(Deployment, Deployment.id == CapabilitySpec.deployment_id)
        .join(ModelVersion, ModelVersion.id == Deployment.model_version_id)
        .join(Model, Model.id == ModelVersion.model_id)
        .join(Project, Project.id == Model.project_id)
        .where(
            CapabilitySpec.id == capability_spec_id,
            CapabilitySpec.workspace_id == workspace_id,
        )
        .with_for_update()
    ).one_or_none()
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="未找到能力契约")
    capability, deployment, _, _, project = record
    if capability.status != "published":
        raise conflict("只有已发布的能力契约可以提交算法市场")
    if deployment.status != "published" or deployment.environment != "production":
        raise conflict("能力契约关联的生产服务不可用")
    if project.task_type != "object-detection":
        raise conflict("当前算法市场只开放目标检测推理服务")
    existing = session.scalar(
        select(MarketplaceListing).where(
            MarketplaceListing.capability_spec_id == capability.id
        )
    )
    if existing is None:
        existing = session.scalar(
            select(MarketplaceListing).where(
                MarketplaceListing.deployment_id == deployment.id
            )
        )
    if existing is not None:
        if existing.status not in {"rejected", "legacy_unbound"}:
            detail = (
                "该能力版本已在等待平台审核"
                if existing.status == "pending_review"
                else "该能力版本已经在算法市场公开"
            )
            raise conflict(detail)
        listing = existing
        listing.capability_spec_id = capability.id
        listing.title = payload.title
        listing.summary = payload.summary
        listing.price_per_1000_cents = payload.price_per_1000_cents
        listing.monthly_quota_units = payload.monthly_quota_units
        listing.status = "pending_review"
        listing.published_at = None
    else:
        listing = MarketplaceListing(
            id=uuid4(),
            provider_workspace_id=workspace_id,
            deployment_id=deployment.id,
            capability_spec_id=capability.id,
            title=payload.title,
            summary=payload.summary,
            category="目标检测",
            pricing_unit="image",
            price_per_1000_cents=payload.price_per_1000_cents,
            monthly_quota_units=payload.monthly_quota_units,
            status="pending_review",
            published_at=None,
        )
        session.add(listing)
    session.flush()
    return _listing_response(session, listing, workspace_id)


def review_listing(
    session: Session,
    listing_id: UUID,
    payload: MarketplaceListingReviewCreate,
) -> MarketplaceListingReviewResponse:
    listing = session.scalar(
        select(MarketplaceListing)
        .where(MarketplaceListing.id == listing_id)
        .with_for_update()
    )
    if listing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="未找到算法商品")
    if listing.status != "pending_review":
        raise conflict("该算法商品当前不在待审核状态")
    if payload.decision == "approved":
        eligible_capability = session.execute(
            select(CapabilitySpec)
            .join(Deployment, Deployment.id == CapabilitySpec.deployment_id)
            .where(
                CapabilitySpec.id == listing.capability_spec_id,
                CapabilitySpec.status == "published",
                Deployment.status == "published",
                Deployment.environment == "production",
            )
        ).scalar_one_or_none()
        if eligible_capability is None:
            raise conflict("能力契约或关联的生产服务已不可用，不能批准公开")
    reviewed_at = datetime.now(UTC)
    listing.status = "published" if payload.decision == "approved" else "rejected"
    listing.published_at = reviewed_at if payload.decision == "approved" else None
    review = MarketplaceListingReview(
        listing_id=listing.id,
        decision=payload.decision,
        reviewer_identity=payload.reviewer_identity,
        note=payload.note,
        reviewed_at=reviewed_at,
    )
    session.add(review)
    session.flush()
    return MarketplaceListingReviewResponse(
        listing_id=listing.id,
        status=listing.status,
        decision=review.decision,
        reviewer_identity=review.reviewer_identity,
        note=review.note,
        reviewed_at=review.reviewed_at,
    )


def list_listings(
    session: Session,
    buyer_workspace_id: UUID,
) -> list[MarketplaceListingResponse]:
    require_workspace(session, buyer_workspace_id)
    listings = session.scalars(
        select(MarketplaceListing)
        .where(
            MarketplaceListing.status == "published",
            MarketplaceListing.capability_spec_id.is_not(None),
        )
        .order_by(MarketplaceListing.published_at.desc())
    ).all()
    return [
        _listing_response(session, listing, buyer_workspace_id) for listing in listings
    ]


def list_public_listings(session: Session) -> list[MarketplaceListingResponse]:
    listings = session.scalars(
        select(MarketplaceListing)
        .where(
            MarketplaceListing.status == "published",
            MarketplaceListing.capability_spec_id.is_not(None),
        )
        .order_by(MarketplaceListing.published_at.desc())
    ).all()
    return [_listing_response(session, listing, None) for listing in listings]


def list_submissions(
    session: Session,
    provider_workspace_id: UUID,
) -> list[MarketplaceListingSubmissionResponse]:
    require_workspace(session, provider_workspace_id)
    listings = session.scalars(
        select(MarketplaceListing)
        .where(MarketplaceListing.provider_workspace_id == provider_workspace_id)
        .order_by(MarketplaceListing.created_at.desc())
    ).all()
    responses: list[MarketplaceListingSubmissionResponse] = []
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
        listing_response = _listing_response(
            session,
            listing,
            provider_workspace_id,
        )
        responses.append(
            MarketplaceListingSubmissionResponse(
                **listing_response.model_dump(),
                review_note=latest_review.note if latest_review else None,
                reviewed_at=latest_review.reviewed_at if latest_review else None,
            )
        )
    return responses


def _listing_response(
    session: Session,
    listing: MarketplaceListing,
    buyer_workspace_id: UUID | None,
) -> MarketplaceListingResponse:
    record = session.execute(
        select(Deployment, Workspace, ModelVersion, Model, Project, CapabilitySpec)
        .join(Workspace, Workspace.id == Deployment.workspace_id)
        .join(ModelVersion, ModelVersion.id == Deployment.model_version_id)
        .join(Model, Model.id == ModelVersion.model_id)
        .join(Project, Project.id == Model.project_id)
        .outerjoin(CapabilitySpec, CapabilitySpec.id == listing.capability_spec_id)
        .where(Deployment.id == listing.deployment_id)
    ).one()
    deployment, provider, model_version, model, project, capability = record
    subscription = (
        session.scalar(
            select(MarketplaceSubscription).where(
                MarketplaceSubscription.listing_id == listing.id,
                MarketplaceSubscription.buyer_workspace_id == buyer_workspace_id,
            )
        )
        if buyer_workspace_id is not None
        else None
    )
    subscription_status = _effective_status(subscription) if subscription else None
    return MarketplaceListingResponse(
        id=listing.id,
        provider_workspace_id=listing.provider_workspace_id,
        provider_name=provider.name,
        deployment_id=listing.deployment_id,
        capability_spec_id=listing.capability_spec_id,
        capability_slug=capability.capability_slug if capability else None,
        capability_version_number=capability.version_number if capability else None,
        capability_display_name=capability.display_name if capability else None,
        capability_problem_definition=capability.problem_definition if capability else None,
        capability_output_contract=(
            str(capability.output_spec.get("contract")) if capability else None
        ),
        capability_verified_scenes=(
            list(capability.applicability.get("verified_scenes", [])) if capability else []
        ),
        capability_unsupported_conditions=(
            list(capability.applicability.get("unsupported_conditions", []))
            if capability
            else []
        ),
        endpoint_url=_endpoint_url(provider.slug, deployment.endpoint_slug),
        model_name=model.name,
        model_version_number=model_version.version_number,
        task_type=project.task_type,
        title=listing.title,
        summary=listing.summary,
        category=listing.category,
        pricing_unit=listing.pricing_unit,
        price_per_1000_cents=listing.price_per_1000_cents,
        monthly_quota_units=listing.monthly_quota_units,
        status=listing.status,
        published_at=listing.published_at,
        subscription_id=subscription.id if subscription else None,
        subscription_status=subscription_status,
        remaining_units=_remaining_units(subscription) if subscription else None,
    )


def subscribe(
    session: Session,
    buyer_workspace_id: UUID,
    listing_id: UUID,
) -> MarketplaceCheckoutResponse:
    require_workspace(session, buyer_workspace_id)
    listing = session.scalar(
        select(MarketplaceListing)
        .where(MarketplaceListing.id == listing_id)
        .with_for_update()
    )
    if (
        listing is None
        or listing.status != "published"
        or listing.capability_spec_id is None
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="未找到算法商品")
    if listing.provider_workspace_id == buyer_workspace_id:
        raise conflict("供应方工作区不能购买自己的算法商品")
    subscription = session.scalar(
        select(MarketplaceSubscription)
        .where(
            MarketplaceSubscription.listing_id == listing.id,
            MarketplaceSubscription.buyer_workspace_id == buyer_workspace_id,
        )
        .with_for_update()
    )
    if subscription is not None and _effective_status(subscription) == "active":
        raise conflict("当前工作区已经获得该算法的调用授权")
    if subscription is not None and subscription.status in {
        "pending_payment",
        "payment_failed",
    }:
        pending_order = _latest_order(session, subscription.id)
        if pending_order is not None:
            pending_intent = session.scalar(
                select(MarketplacePaymentIntent).where(
                    MarketplacePaymentIntent.order_id == pending_order.id
                )
            )
            if pending_intent is not None and pending_order.payment_status not in {
                "paid",
                "partially_refunded",
                "waived",
            }:
                return _checkout_response(
                    session,
                    subscription,
                    pending_order,
                    pending_intent,
                    reused=True,
                )

    if subscription is None:
        subscription = MarketplaceSubscription(
            listing_id=listing.id,
            buyer_workspace_id=buyer_workspace_id,
            status="pending_payment",
            quota_units=listing.monthly_quota_units,
            reserved_units=0,
            consumed_units=0,
            price_per_1000_cents=listing.price_per_1000_cents,
            api_key_prefix=None,
            api_key_hash=None,
            credential_claimed_at=None,
            started_at=None,
            expires_at=None,
        )
        session.add(subscription)
    else:
        subscription.status = "pending_payment"
        subscription.quota_units = listing.monthly_quota_units
        subscription.price_per_1000_cents = listing.price_per_1000_cents
        subscription.api_key_prefix = None
        subscription.api_key_hash = None
        subscription.credential_claimed_at = None
        subscription.started_at = None
        subscription.expires_at = None
    session.flush()
    order_created_at = datetime.now(UTC)
    order = MarketplaceOrder(
        order_number=_new_order_number(),
        listing_id=listing.id,
        subscription_id=subscription.id,
        buyer_workspace_id=buyer_workspace_id,
        provider_workspace_id=listing.provider_workspace_id,
        currency="CNY",
        price_per_1000_cents=listing.price_per_1000_cents,
        quota_units=listing.monthly_quota_units,
        authorization_amount_micros=(
            listing.monthly_quota_units * listing.price_per_1000_cents * 10
        ),
        status="payment_pending",
        payment_status="not_collected",
        entitlement_started_at=None,
        entitlement_expires_at=None,
        created_at=order_created_at,
        updated_at=order_created_at,
    )
    session.add(order)
    session.flush()
    free_entitlement = order.authorization_amount_micros == 0
    payment_intent = MarketplacePaymentIntent(
        order_id=order.id,
        expected_amount_micros=order.authorization_amount_micros,
        currency=order.currency,
        status="not_required" if free_entitlement else "requires_provider",
        paid_amount_micros=0,
        refunded_amount_micros=0,
    )
    session.add(payment_intent)
    if free_entitlement:
        order.payment_status = "waived"
        activate_entitlement(subscription, order, order_created_at)
    session.flush()
    return _checkout_response(
        session,
        subscription,
        order,
        payment_intent,
        reused=False,
    )


def _checkout_response(
    session: Session,
    subscription: MarketplaceSubscription,
    order: MarketplaceOrder,
    payment_intent: MarketplacePaymentIntent,
    *,
    reused: bool,
) -> MarketplaceCheckoutResponse:
    subscription_response = _subscription_response(session, subscription)
    return MarketplaceCheckoutResponse(
        **subscription_response.model_dump(),
        payment_intent_id=payment_intent.id,
        payment_intent_status=payment_intent.status,
        expected_amount_yuan=_micros_to_yuan(payment_intent.expected_amount_micros),
        payment_provider=payment_intent.provider,
        checkout_available=False,
        reused=reused,
    )


def list_subscriptions(
    session: Session,
    buyer_workspace_id: UUID,
) -> list[MarketplaceSubscriptionResponse]:
    require_workspace(session, buyer_workspace_id)
    subscriptions = session.scalars(
        select(MarketplaceSubscription)
        .where(MarketplaceSubscription.buyer_workspace_id == buyer_workspace_id)
        .order_by(MarketplaceSubscription.created_at.desc())
    ).all()
    return [_subscription_response(session, item) for item in subscriptions]


def rotate_subscription_key(
    session: Session,
    buyer_workspace_id: UUID,
    subscription_id: UUID,
) -> tuple[MarketplaceSubscriptionResponse, str]:
    subscription = session.scalar(
        select(MarketplaceSubscription)
        .where(
            MarketplaceSubscription.id == subscription_id,
            MarketplaceSubscription.buyer_workspace_id == buyer_workspace_id,
        )
        .with_for_update()
    )
    if subscription is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="未找到调用授权")
    if _effective_status(subscription) != "active":
        raise conflict("只有有效调用授权可以轮换密钥")
    if subscription.api_key_hash is None:
        raise conflict("请先领取首次显示的市场密钥")
    api_key, key_prefix, key_hash = _new_marketplace_key()
    subscription.api_key_prefix = key_prefix
    subscription.api_key_hash = key_hash
    session.flush()
    return _subscription_response(session, subscription), api_key


def claim_subscription_key(
    session: Session,
    buyer_workspace_id: UUID,
    subscription_id: UUID,
) -> tuple[MarketplaceSubscriptionResponse, str]:
    subscription = session.scalar(
        select(MarketplaceSubscription)
        .where(
            MarketplaceSubscription.id == subscription_id,
            MarketplaceSubscription.buyer_workspace_id == buyer_workspace_id,
        )
        .with_for_update()
    )
    if subscription is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="未找到调用授权")
    if _effective_status(subscription) != "active":
        raise conflict("只有已收款且生效的授权可以领取密钥")
    latest_order = _latest_order(session, subscription.id)
    if latest_order is None or latest_order.payment_status not in PAID_ORDER_STATUSES:
        raise conflict("尚未确认该授权的收款事实")
    if subscription.api_key_hash is not None:
        raise conflict("首次密钥已经领取；如果遗失请轮换密钥")
    api_key, key_prefix, key_hash = _new_marketplace_key()
    subscription.api_key_prefix = key_prefix
    subscription.api_key_hash = key_hash
    subscription.credential_claimed_at = datetime.now(UTC)
    session.flush()
    return _subscription_response(session, subscription), api_key


def _effective_status(subscription: MarketplaceSubscription) -> str:
    expires_at = subscription.expires_at
    if subscription.status != "active" or expires_at is None:
        return subscription.status
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if subscription.status == "active" and expires_at <= datetime.now(UTC):
        return "expired"
    if subscription.status == "active" and _remaining_units(subscription) <= 0:
        return "exhausted"
    return subscription.status


def _remaining_units(subscription: MarketplaceSubscription) -> int:
    return max(0, subscription.quota_units - subscription.reserved_units - subscription.consumed_units)


def _subscription_response(
    session: Session,
    subscription: MarketplaceSubscription,
) -> MarketplaceSubscriptionResponse:
    listing = session.get(MarketplaceListing, subscription.listing_id)
    if listing is None:
        raise conflict("调用授权关联的算法商品不存在")
    record = session.execute(
        select(Deployment, Workspace)
        .join(Workspace, Workspace.id == Deployment.workspace_id)
        .where(Deployment.id == listing.deployment_id)
    ).one()
    deployment, provider = record
    latest_order = _latest_order(session, subscription.id)
    return MarketplaceSubscriptionResponse(
        id=subscription.id,
        listing_id=listing.id,
        buyer_workspace_id=subscription.buyer_workspace_id,
        listing_title=listing.title,
        provider_name=provider.name,
        endpoint_url=_endpoint_url(provider.slug, deployment.endpoint_slug),
        status=_effective_status(subscription),
        quota_units=subscription.quota_units,
        reserved_units=subscription.reserved_units,
        consumed_units=subscription.consumed_units,
        remaining_units=_remaining_units(subscription),
        price_per_1000_cents=subscription.price_per_1000_cents,
        api_key_prefix=subscription.api_key_prefix,
        credential_claimed_at=subscription.credential_claimed_at,
        started_at=subscription.started_at,
        expires_at=subscription.expires_at,
        order_number=latest_order.order_number if latest_order else None,
        payment_status=latest_order.payment_status if latest_order else None,
    )


def authorize_inference(
    session: Session,
    workspace_slug: str,
    endpoint_slug: str,
    api_key: str,
    payload: InferenceAuthorizationCreate,
) -> GatewayAuthorizationResponse:
    record = session.execute(
        select(Deployment, ModelVersion, Project, Workspace)
        .join(ModelVersion, ModelVersion.id == Deployment.model_version_id)
        .join(Model, Model.id == ModelVersion.model_id)
        .join(Project, Project.id == Model.project_id)
        .join(Workspace, Workspace.id == Deployment.workspace_id)
        .where(
            Workspace.slug == workspace_slug,
            Deployment.endpoint_slug == endpoint_slug,
        )
    ).one_or_none()
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="未找到推理端点")
    deployment, model_version, project, workspace = record
    if deployment.status != "published":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="未找到推理端点")
    owner_key_valid = bool(
        deployment.api_key_hash
        and compare_digest(deployment.api_key_hash, _key_hash(api_key))
    )
    if owner_key_valid:
        return _authorization_response(
            session,
            deployment, model_version, project, workspace, None, None
        )

    subscription_record = session.execute(
        select(MarketplaceSubscription, MarketplaceListing)
        .join(
            MarketplaceListing,
            MarketplaceListing.id == MarketplaceSubscription.listing_id,
        )
        .where(
            MarketplaceListing.deployment_id == deployment.id,
            MarketplaceListing.status == "published",
            MarketplaceListing.capability_spec_id.is_not(None),
            MarketplaceSubscription.api_key_hash == _key_hash(api_key),
        )
        .with_for_update()
    ).one_or_none()
    if subscription_record is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="API 密钥无效")
    subscription, _ = subscription_record
    if not subscription.api_key_hash or not compare_digest(
        subscription.api_key_hash, _key_hash(api_key)
    ):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="API 密钥无效")
    effective_status = _effective_status(subscription)
    if effective_status == "expired":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="调用授权已到期")
    if effective_status != "active":
        detail = {
            "pending_payment": "调用授权尚未完成收款",
            "payment_failed": "调用授权的支付已失败",
            "refunded": "调用授权已因全额退款撤销",
            "exhausted": "调用额度已用尽",
        }.get(effective_status, "调用授权当前不可用")
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=detail,
        )

    reservation = session.scalar(
        select(UsageReservation)
        .where(UsageReservation.request_id == payload.request_id)
        .with_for_update()
    )
    if reservation is not None:
        if (
            reservation.subscription_id != subscription.id
            or reservation.deployment_id != deployment.id
            or reservation.units != payload.billable_units
        ):
            raise conflict("请求编号已用于另一条额度预留")
        if reservation.status == "released":
            _reserve_units(subscription, payload.billable_units)
            reservation.status = "pending"
            reservation.finalized_at = None
    else:
        _reserve_units(subscription, payload.billable_units)
        reservation = UsageReservation(
            subscription_id=subscription.id,
            deployment_id=deployment.id,
            request_id=payload.request_id,
            units=payload.billable_units,
            status="pending",
        )
        session.add(reservation)
    session.flush()
    return _authorization_response(
        session,
        deployment,
        model_version,
        project,
        workspace,
        reservation,
        subscription,
    )


def _reserve_units(subscription: MarketplaceSubscription, units: int) -> None:
    if _remaining_units(subscription) < units:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="本次请求超过剩余调用额度",
        )
    subscription.reserved_units += units


def _authorization_response(
    session: Session,
    deployment: Deployment,
    model_version: ModelVersion,
    project: Project,
    workspace: Workspace,
    reservation: UsageReservation | None,
    subscription: MarketplaceSubscription | None,
) -> GatewayAuthorizationResponse:
    return GatewayAuthorizationResponse(
        deployment_id=deployment.id,
        workspace_id=deployment.workspace_id,
        workspace_slug=workspace.slug,
        endpoint_slug=deployment.endpoint_slug,
        model_version_id=model_version.id,
        artifact_uri=model_version.artifact_uri,
        task_type=project.task_type,
        contract=_contract_for(project.task_type),
        workflow_bindings=event_bindings_for_deployment(session, deployment.id),
        reservation_id=reservation.id if reservation else None,
        subscription_id=subscription.id if subscription else None,
        remaining_units=_remaining_units(subscription) if subscription else None,
    )


def release_reservation(
    session: Session,
    reservation_id: UUID,
    request_id: str,
) -> UsageReservationResponse:
    reservation = session.scalar(
        select(UsageReservation)
        .where(UsageReservation.id == reservation_id)
        .with_for_update()
    )
    if reservation is None or reservation.request_id != request_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="未找到额度预留")
    if reservation.status == "pending":
        subscription = session.scalar(
            select(MarketplaceSubscription)
            .where(MarketplaceSubscription.id == reservation.subscription_id)
            .with_for_update()
        )
        if subscription is None:
            raise conflict("额度预留关联的调用授权不存在")
        subscription.reserved_units = max(0, subscription.reserved_units - reservation.units)
        reservation.status = "released"
        reservation.finalized_at = datetime.now(UTC)
        session.flush()
    return UsageReservationResponse(
        id=reservation.id,
        request_id=reservation.request_id,
        subscription_id=reservation.subscription_id,
        deployment_id=reservation.deployment_id,
        units=reservation.units,
        status=reservation.status,
        finalized_at=reservation.finalized_at,
    )


def recover_stale_reservations(
    session: Session,
    *,
    timeout_seconds: int,
    now: datetime | None = None,
    limit: int = 100,
) -> list[UsageReservationRecoveryItem]:
    recovered_at = now or datetime.now(UTC)
    cutoff = recovered_at - timedelta(seconds=timeout_seconds)
    statement = (
        select(UsageReservation, MarketplaceSubscription)
        .join(
            MarketplaceSubscription,
            MarketplaceSubscription.id == UsageReservation.subscription_id,
        )
        .where(
            UsageReservation.status == "pending",
            UsageReservation.created_at < cutoff,
        )
        .order_by(UsageReservation.created_at, UsageReservation.id)
        .limit(limit)
        .with_for_update(skip_locked=True)
    )
    recovered: list[UsageReservationRecoveryItem] = []
    for reservation, subscription in session.execute(statement):
        subscription.reserved_units = max(
            0, subscription.reserved_units - reservation.units
        )
        reservation.status = "released"
        reservation.finalized_at = recovered_at
        recovered.append(
            UsageReservationRecoveryItem(
                reservation_id=reservation.id,
                subscription_id=subscription.id,
                request_id=reservation.request_id,
                released_units=reservation.units,
                recovered_at=recovered_at,
            )
        )
    session.flush()
    return recovered


def list_usage_records(
    session: Session,
    buyer_workspace_id: UUID,
    *,
    limit: int = 50,
) -> list[MarketplaceUsageRecordResponse]:
    require_workspace(session, buyer_workspace_id)
    statement = (
        select(
            UsageRecord,
            MarketplaceSubscription,
            MarketplaceListing,
            Workspace,
        )
        .join(
            MarketplaceSubscription,
            MarketplaceSubscription.id == UsageRecord.subscription_id,
        )
        .join(
            MarketplaceListing,
            MarketplaceListing.id == MarketplaceSubscription.listing_id,
        )
        .join(Workspace, Workspace.id == MarketplaceListing.provider_workspace_id)
        .where(MarketplaceSubscription.buyer_workspace_id == buyer_workspace_id)
        .order_by(UsageRecord.occurred_at.desc(), UsageRecord.id)
        .limit(limit)
    )
    records: list[MarketplaceUsageRecordResponse] = []
    for usage, subscription, listing, provider in session.execute(statement):
        estimated_cost_yuan = (
            usage.billable_units
            * Decimal(subscription.price_per_1000_cents)
            / Decimal(100_000)
        )
        records.append(
            MarketplaceUsageRecordResponse(
                id=usage.id,
                request_id=usage.request_id,
                subscription_id=subscription.id,
                listing_id=listing.id,
                listing_title=listing.title,
                provider_name=provider.name,
                billable_units=float(usage.billable_units),
                unit=usage.unit,
                estimated_cost_yuan=float(estimated_cost_yuan),
                dimensions=usage.dimensions,
                occurred_at=usage.occurred_at,
            )
        )
    return records


def get_billing(
    session: Session,
    workspace_id: UUID,
    *,
    limit: int = 50,
) -> MarketplaceBillingResponse:
    require_workspace(session, workspace_id)
    provider = aliased(Workspace)
    buyer = aliased(Workspace)

    order_rows = session.execute(
        select(
            MarketplaceOrder,
            MarketplaceListing,
            provider,
            MarketplacePaymentIntent,
        )
        .join(MarketplaceListing, MarketplaceListing.id == MarketplaceOrder.listing_id)
        .join(provider, provider.id == MarketplaceOrder.provider_workspace_id)
        .outerjoin(
            MarketplacePaymentIntent,
            MarketplacePaymentIntent.order_id == MarketplaceOrder.id,
        )
        .where(MarketplaceOrder.buyer_workspace_id == workspace_id)
        .order_by(MarketplaceOrder.created_at.desc(), MarketplaceOrder.id)
        .limit(limit)
    )
    orders = [
        MarketplaceOrderResponse(
            id=order.id,
            order_number=order.order_number,
            listing_id=order.listing_id,
            subscription_id=order.subscription_id,
            listing_title=listing.title,
            provider_name=provider_workspace.name,
            currency=order.currency,
            price_per_1000_cents=order.price_per_1000_cents,
            quota_units=order.quota_units,
            authorization_amount_yuan=_micros_to_yuan(
                order.authorization_amount_micros
            ),
            status=order.status,
            payment_status=order.payment_status,
            entitlement_started_at=order.entitlement_started_at,
            entitlement_expires_at=order.entitlement_expires_at,
            created_at=order.created_at,
            payment_intent_id=payment_intent.id if payment_intent else None,
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
        )
        for order, listing, provider_workspace, payment_intent in order_rows
    ]

    earning_rows = session.execute(
        select(
            MarketplaceLedgerEntry,
            UsageRecord,
            MarketplaceListing,
            buyer,
        )
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
    )
    earnings = [
        MarketplaceEarningResponse(
            id=entry.id,
            usage_record_id=usage.id,
            request_id=usage.request_id,
            listing_title=listing.title,
            buyer_name=buyer_workspace.name,
            amount_yuan=_micros_to_yuan(entry.amount_micros),
            currency=entry.currency,
            settlement_status=entry.settlement_status,
            occurred_at=entry.occurred_at,
        )
        for entry, usage, listing, buyer_workspace in earning_rows
    ]

    authorization_micros = session.scalar(
        select(func.coalesce(func.sum(MarketplaceOrder.authorization_amount_micros), 0))
        .where(MarketplaceOrder.buyer_workspace_id == workspace_id)
    )
    unsettled_micros = session.scalar(
        select(func.coalesce(func.sum(MarketplaceLedgerEntry.amount_micros), 0)).where(
            MarketplaceLedgerEntry.provider_workspace_id == workspace_id,
            MarketplaceLedgerEntry.settlement_status == "unsettled",
        )
    )
    return MarketplaceBillingResponse(
        authorization_ceiling_yuan=_micros_to_yuan(int(authorization_micros or 0)),
        unsettled_earnings_yuan=_micros_to_yuan(int(unsettled_micros or 0)),
        orders=orders,
        earnings=earnings,
    )


def _day_window(report_date: date) -> tuple[datetime, datetime]:
    start = datetime.combine(report_date, datetime.min.time(), tzinfo=UTC)
    return start, start + timedelta(days=1)


def _count_and_sum(
    session: Session,
    statement,
) -> tuple[int, Decimal]:
    count, amount = session.execute(statement).one()
    return int(count or 0), Decimal(amount or 0)


def reconcile_daily(
    session: Session,
    report_date: date | None = None,
) -> MarketplaceDailyReconciliationResponse:
    """Create a read-only UTC reconciliation report from marketplace facts.

    The report deliberately contains aggregates and issue counts only: payment IDs,
    API keys, target endpoints and other sensitive operational details stay in the
    underlying restricted tables.
    """
    effective_date = report_date or datetime.now(UTC).date()
    start_at, end_at = _day_window(effective_date)
    orders_created, authorization_micros = _count_and_sum(
        session,
        select(
            func.count(MarketplaceOrder.id),
            func.coalesce(func.sum(MarketplaceOrder.authorization_amount_micros), 0),
        ).where(
            MarketplaceOrder.created_at >= start_at,
            MarketplaceOrder.created_at < end_at,
        ),
    )

    payment_totals = {
        event_type: (int(count or 0), int(amount or 0))
        for event_type, count, amount in session.execute(
            select(
                MarketplacePaymentEvent.event_type,
                func.count(MarketplacePaymentEvent.id),
                func.coalesce(func.sum(MarketplacePaymentEvent.amount_micros), 0),
            )
            .where(
                MarketplacePaymentEvent.occurred_at >= start_at,
                MarketplacePaymentEvent.occurred_at < end_at,
            )
            .group_by(MarketplacePaymentEvent.event_type)
        )
    }
    payment_success_events, payment_success_micros = payment_totals.get(
        "payment.succeeded", (0, 0)
    )
    refund_success_events, refund_success_micros = payment_totals.get(
        "refund.succeeded", (0, 0)
    )

    successful_usage_requests, successful_usage_units = _count_and_sum(
        session,
        select(
            func.count(UsageRecord.id),
            func.coalesce(func.sum(UsageRecord.billable_units), 0),
        ).where(UsageRecord.occurred_at >= start_at, UsageRecord.occurred_at < end_at),
    )
    marketplace_usage_requests, marketplace_usage_units = _count_and_sum(
        session,
        select(
            func.count(UsageRecord.id),
            func.coalesce(func.sum(UsageRecord.billable_units), 0),
        ).where(
            UsageRecord.subscription_id.is_not(None),
            UsageRecord.occurred_at >= start_at,
            UsageRecord.occurred_at < end_at,
        ),
    )
    ledger_entries, provider_earnings_micros = _count_and_sum(
        session,
        select(
            func.count(MarketplaceLedgerEntry.id),
            func.coalesce(func.sum(MarketplaceLedgerEntry.amount_micros), 0),
        ).where(
            MarketplaceLedgerEntry.occurred_at >= start_at,
            MarketplaceLedgerEntry.occurred_at < end_at,
        ),
    )

    missing_ledger_count = int(
        session.scalar(
            select(func.count(UsageRecord.id))
            .outerjoin(
                MarketplaceLedgerEntry,
                MarketplaceLedgerEntry.usage_record_id == UsageRecord.id,
            )
            .where(
                UsageRecord.subscription_id.is_not(None),
                UsageRecord.occurred_at >= start_at,
                UsageRecord.occurred_at < end_at,
                MarketplaceLedgerEntry.id.is_(None),
            )
        )
        or 0
    )
    ledger_rows = session.execute(
        select(UsageRecord, MarketplaceLedgerEntry, MarketplaceSubscription)
        .join(
            MarketplaceLedgerEntry,
            MarketplaceLedgerEntry.usage_record_id == UsageRecord.id,
        )
        .join(
            MarketplaceSubscription,
            MarketplaceSubscription.id == UsageRecord.subscription_id,
        )
        .where(
            UsageRecord.subscription_id.is_not(None),
            UsageRecord.occurred_at >= start_at,
            UsageRecord.occurred_at < end_at,
        )
    ).all()
    ledger_amount_mismatch_count = sum(
        1
        for usage, entry, subscription in ledger_rows
        if entry.amount_micros
        != int(
            Decimal(usage.billable_units)
            * Decimal(subscription.price_per_1000_cents)
            * Decimal(10)
        )
    )
    report_cutoff = min(
        datetime.now(UTC),
        end_at,
    ) - timedelta(seconds=get_settings().inference_reservation_timeout_seconds)
    stale_pending_reservations, stale_pending_units = _count_and_sum(
        session,
        select(
            func.count(UsageReservation.id),
            func.coalesce(func.sum(UsageReservation.units), 0),
        ).where(
            UsageReservation.status == "pending",
            UsageReservation.created_at < report_cutoff,
        ),
    )
    payment_requires_review_count = int(
        session.scalar(
            select(func.count(MarketplacePaymentEvent.id)).where(
                MarketplacePaymentEvent.occurred_at >= start_at,
                MarketplacePaymentEvent.occurred_at < end_at,
                MarketplacePaymentEvent.processing_status
                == "applied_superseded_order",
            )
        )
        or 0
    )

    issues: list[MarketplaceReconciliationIssue] = []
    if missing_ledger_count:
        issues.append(
            MarketplaceReconciliationIssue(
                code="marketplace_usage_without_ledger",
                count=missing_ledger_count,
                detail="存在已计量的市场调用，但未生成供应方收入账本。",
            )
        )
    if ledger_amount_mismatch_count:
        issues.append(
            MarketplaceReconciliationIssue(
                code="ledger_amount_mismatch",
                count=ledger_amount_mismatch_count,
                detail="供应方收入金额与已记录用量及订单单价不一致。",
            )
        )
    if stale_pending_reservations:
        issues.append(
            MarketplaceReconciliationIssue(
                code="stale_pending_reservation",
                count=stale_pending_reservations,
                detail="存在超过回收窗口仍未完成或释放的调用额度预留。",
            )
        )
    if payment_requires_review_count:
        issues.append(
            MarketplaceReconciliationIssue(
                code="superseded_payment_received",
                count=payment_requires_review_count,
                detail="存在已收款但未发放当前调用授权的历史订单，需人工处理。",
            )
        )

    return MarketplaceDailyReconciliationResponse(
        report_date=effective_date,
        orders_created=orders_created,
        order_authorization_yuan=_micros_to_yuan(int(authorization_micros)),
        payment_success_events=payment_success_events,
        payment_success_yuan=_micros_to_yuan(payment_success_micros),
        refund_success_events=refund_success_events,
        refund_success_yuan=_micros_to_yuan(refund_success_micros),
        successful_usage_requests=successful_usage_requests,
        successful_usage_units=float(successful_usage_units),
        marketplace_usage_requests=marketplace_usage_requests,
        marketplace_usage_units=float(marketplace_usage_units),
        provider_earnings_yuan=_micros_to_yuan(int(provider_earnings_micros)),
        ledger_entries=ledger_entries,
        stale_pending_reservations=stale_pending_reservations,
        stale_pending_reservation_units=int(stale_pending_units),
        issues=issues,
        is_reconciled=not issues,
    )
