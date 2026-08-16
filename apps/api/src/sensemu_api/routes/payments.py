from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from sensemu_api import payment_service
from sensemu_api.db.session import get_session
from sensemu_api.payment_auth import PaymentAdapterAuth
from sensemu_api.payment_schemas import (
    NormalizedPaymentEventCreate,
    NormalizedPaymentEventResponse,
)

router = APIRouter(prefix="/api/v1", tags=["payments"])
SessionDep = Annotated[Session, Depends(get_session)]


@router.post(
    "/internal/payments/normalized-events",
    response_model=NormalizedPaymentEventResponse,
    include_in_schema=False,
)
def receive_normalized_payment_event(
    payload: NormalizedPaymentEventCreate,
    session: SessionDep,
    _payment_adapter_auth: PaymentAdapterAuth,
) -> NormalizedPaymentEventResponse:
    return payment_service.apply_normalized_event(session, payload)
