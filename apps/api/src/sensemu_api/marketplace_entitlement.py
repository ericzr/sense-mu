from datetime import UTC, datetime, timedelta

from sensemu_api.db.models import MarketplaceOrder, MarketplaceSubscription

PAID_ORDER_STATUSES = {"paid", "partially_refunded", "waived"}


def activate_entitlement(
    subscription: MarketplaceSubscription,
    order: MarketplaceOrder,
    activated_at: datetime,
) -> None:
    effective_at = (
        activated_at.replace(tzinfo=UTC)
        if activated_at.tzinfo is None
        else activated_at.astimezone(UTC)
    )
    expires_at = effective_at + timedelta(days=30)
    subscription.status = "active"
    subscription.quota_units = order.quota_units
    subscription.reserved_units = 0
    subscription.consumed_units = 0
    subscription.price_per_1000_cents = order.price_per_1000_cents
    subscription.api_key_prefix = None
    subscription.api_key_hash = None
    subscription.credential_claimed_at = None
    subscription.started_at = effective_at
    subscription.expires_at = expires_at
    order.status = "entitlement_issued"
    order.entitlement_started_at = effective_at
    order.entitlement_expires_at = expires_at


def revoke_entitlement(
    subscription: MarketplaceSubscription,
    order: MarketplaceOrder,
) -> None:
    subscription.status = "refunded"
    subscription.api_key_prefix = None
    subscription.api_key_hash = None
    subscription.credential_claimed_at = None
    order.status = "entitlement_revoked"
