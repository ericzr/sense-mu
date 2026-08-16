from datetime import UTC, datetime
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from sensemu_api.catalog_service import conflict
from sensemu_api.db.models import (
    MarketplaceOrder,
    MarketplacePaymentEvent,
    MarketplacePaymentIntent,
    MarketplaceRefund,
    MarketplaceSubscription,
)
from sensemu_api.marketplace_entitlement import activate_entitlement, revoke_entitlement
from sensemu_api.payment_schemas import (
    NormalizedPaymentEventCreate,
    NormalizedPaymentEventResponse,
)


def _micros_to_yuan(amount_micros: int) -> float:
    return float(Decimal(amount_micros) / Decimal(1_000_000))


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _same_event(
    event: MarketplacePaymentEvent,
    payload: NormalizedPaymentEventCreate,
) -> bool:
    return (
        event.payment_intent_id == payload.payment_intent_id
        and event.provider == payload.provider
        and event.external_event_id == payload.external_event_id
        and event.provider_payment_id == payload.provider_payment_id
        and event.event_type == payload.event_type
        and event.amount_micros == payload.amount_micros
        and event.currency == payload.currency
        and event.payload_sha256.lower() == payload.payload_sha256.lower()
    )


def _response(
    event: MarketplacePaymentEvent,
    intent: MarketplacePaymentIntent,
    order: MarketplaceOrder,
    subscription: MarketplaceSubscription,
    *,
    reused: bool,
) -> NormalizedPaymentEventResponse:
    return NormalizedPaymentEventResponse(
        event_id=event.id,
        payment_intent_id=intent.id,
        order_id=order.id,
        event_type=event.event_type,
        processing_status=event.processing_status,
        payment_intent_status=intent.status,
        order_payment_status=order.payment_status,
        order_status=order.status,
        subscription_id=subscription.id,
        subscription_status=subscription.status,
        paid_amount_yuan=_micros_to_yuan(intent.paid_amount_micros),
        refunded_amount_yuan=_micros_to_yuan(intent.refunded_amount_micros),
        reused=reused,
    )


def apply_normalized_event(
    session: Session,
    payload: NormalizedPaymentEventCreate,
) -> NormalizedPaymentEventResponse:
    existing = session.scalar(
        select(MarketplacePaymentEvent)
        .where(
            MarketplacePaymentEvent.provider == payload.provider,
            MarketplacePaymentEvent.external_event_id == payload.external_event_id,
        )
        .with_for_update()
    )
    if existing is not None:
        if not _same_event(existing, payload):
            raise conflict("支付事件编号已对应另一份事实")
        intent = session.get(MarketplacePaymentIntent, existing.payment_intent_id)
        if intent is None:
            raise conflict("支付事件关联的支付意图不存在")
        order = session.get(MarketplaceOrder, intent.order_id)
        if order is None:
            raise conflict("支付意图关联的订单不存在")
        subscription = session.get(MarketplaceSubscription, order.subscription_id)
        if subscription is None:
            raise conflict("订单关联的调用授权不存在")
        return _response(existing, intent, order, subscription, reused=True)

    intent = session.scalar(
        select(MarketplacePaymentIntent)
        .where(MarketplacePaymentIntent.id == payload.payment_intent_id)
        .with_for_update()
    )
    if intent is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="未找到支付意图",
        )
    order = session.scalar(
        select(MarketplaceOrder)
        .where(MarketplaceOrder.id == intent.order_id)
        .with_for_update()
    )
    if order is None:
        raise conflict("支付意图关联的订单不存在")
    subscription = session.scalar(
        select(MarketplaceSubscription)
        .where(MarketplaceSubscription.id == order.subscription_id)
        .with_for_update()
    )
    if subscription is None:
        raise conflict("订单关联的调用授权不存在")
    if payload.currency != intent.currency:
        raise conflict("支付事件币种与订单不一致")
    if intent.status == "not_required":
        raise conflict("免费订单不接受支付事件")

    is_payment_event = payload.event_type.startswith("payment.")
    if is_payment_event and payload.amount_micros != intent.expected_amount_micros:
        raise conflict("支付事件金额与订单不一致")

    may_rebind_failed_attempt = intent.status == "failed" and is_payment_event
    if intent.provider is None or may_rebind_failed_attempt:
        intent.provider = payload.provider
        intent.provider_payment_id = payload.provider_payment_id
    elif (
        intent.provider != payload.provider
        or intent.provider_payment_id != payload.provider_payment_id
    ):
        raise conflict("支付事件与已绑定的渠道支付不一致")

    processing_status = "applied"
    pending_refund: tuple[str, str | None] | None = None
    occurred_at = _as_utc(payload.occurred_at)
    latest_order = session.scalar(
        select(MarketplaceOrder)
        .where(MarketplaceOrder.subscription_id == subscription.id)
        .order_by(MarketplaceOrder.created_at.desc(), MarketplaceOrder.id.desc())
        .limit(1)
    )
    is_current_order = latest_order is not None and latest_order.id == order.id
    if payload.event_type == "payment.succeeded":
        if intent.status in {"succeeded", "partially_refunded", "refunded"}:
            processing_status = "ignored_duplicate_state"
        else:
            intent.status = "succeeded"
            intent.paid_amount_micros = payload.amount_micros
            order.payment_status = "paid"
            if is_current_order:
                activate_entitlement(subscription, order, occurred_at)
            else:
                order.status = "payment_received_without_entitlement"
                processing_status = "applied_superseded_order"
    elif payload.event_type == "payment.failed":
        if intent.status in {"succeeded", "partially_refunded", "refunded"}:
            processing_status = "ignored_stale"
        else:
            intent.status = "failed"
            order.payment_status = "not_collected"
            order.status = "payment_failed"
            if is_current_order:
                subscription.status = "payment_failed"
    else:
        if intent.status not in {"succeeded", "partially_refunded"}:
            raise conflict("只有已收款订单可以记录退款")
        if not payload.provider_refund_id:
            raise conflict("退款成功事件缺少渠道退款编号")
        if payload.amount_micros <= 0:
            raise conflict("退款金额必须大于零")
        existing_refund = session.scalar(
            select(MarketplaceRefund).where(
                MarketplaceRefund.provider == payload.provider,
                MarketplaceRefund.provider_refund_id == payload.provider_refund_id,
            )
        )
        if existing_refund is not None:
            if (
                existing_refund.payment_intent_id != intent.id
                or existing_refund.amount_micros != payload.amount_micros
            ):
                raise conflict("渠道退款编号已对应另一笔退款")
            processing_status = "ignored_duplicate_refund"
        else:
            next_refunded = intent.refunded_amount_micros + payload.amount_micros
            if next_refunded > intent.paid_amount_micros:
                raise conflict("累计退款金额不能超过已收款金额")
            intent.refunded_amount_micros = next_refunded
            if next_refunded == intent.paid_amount_micros:
                intent.status = "refunded"
                order.payment_status = "refunded"
                if is_current_order:
                    revoke_entitlement(subscription, order)
            else:
                intent.status = "partially_refunded"
                order.payment_status = "partially_refunded"
            pending_refund = (payload.provider_refund_id, payload.reason)

    previous_event_at = (
        _as_utc(intent.last_event_at) if intent.last_event_at else occurred_at
    )
    intent.last_event_at = max(previous_event_at, occurred_at)
    event = MarketplacePaymentEvent(
        payment_intent_id=intent.id,
        provider=payload.provider,
        external_event_id=payload.external_event_id,
        provider_payment_id=payload.provider_payment_id,
        event_type=payload.event_type,
        amount_micros=payload.amount_micros,
        currency=payload.currency,
        payload_sha256=payload.payload_sha256.lower(),
        processing_status=processing_status,
        occurred_at=occurred_at,
        verified_at=datetime.now(UTC),
    )
    session.add(event)
    session.flush()
    if pending_refund is not None:
        provider_refund_id, reason = pending_refund
        session.add(
            MarketplaceRefund(
                payment_intent_id=intent.id,
                order_id=order.id,
                payment_event_id=event.id,
                provider=payload.provider,
                provider_refund_id=provider_refund_id,
                amount_micros=payload.amount_micros,
                currency=payload.currency,
                reason=reason,
                status="succeeded",
                occurred_at=occurred_at,
            )
        )
        session.flush()
    return _response(event, intent, order, subscription, reused=False)
