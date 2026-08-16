from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class NormalizedPaymentEventCreate(BaseModel):
    payment_intent_id: UUID
    provider: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{1,63}$")
    external_event_id: str = Field(
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{1,179}$"
    )
    provider_payment_id: str = Field(
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{1,179}$"
    )
    event_type: Literal[
        "payment.succeeded",
        "payment.failed",
        "refund.succeeded",
    ]
    amount_micros: int = Field(ge=0)
    currency: Literal["CNY"] = "CNY"
    payload_sha256: str = Field(pattern=r"^[A-Fa-f0-9]{64}$")
    occurred_at: datetime
    provider_refund_id: str | None = Field(
        default=None,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{1,179}$",
    )
    reason: str | None = Field(default=None, max_length=240)


class NormalizedPaymentEventResponse(BaseModel):
    event_id: UUID
    payment_intent_id: UUID
    order_id: UUID
    event_type: str
    processing_status: str
    payment_intent_status: str
    order_payment_status: str
    order_status: str
    subscription_id: UUID
    subscription_status: str
    paid_amount_yuan: float
    refunded_amount_yuan: float
    reused: bool
