from secrets import compare_digest
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status

from sensemu_api.config import get_settings


def verify_payment_adapter_token(
    token: Annotated[str, Header(alias="X-SenseMu-Payment-Adapter-Token")],
) -> None:
    if not compare_digest(token, get_settings().payment_adapter_token):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="支付适配器凭据无效",
        )


PaymentAdapterAuth = Annotated[None, Depends(verify_payment_adapter_token)]
