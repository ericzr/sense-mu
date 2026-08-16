from secrets import compare_digest
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status

from sensemu_api.config import get_settings


def verify_gateway_token(
    token: Annotated[str, Header(alias="X-SenseMu-Gateway-Token")],
) -> None:
    if not compare_digest(token, get_settings().gateway_token):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="推理网关凭据无效",
        )


GatewayAuth = Annotated[None, Depends(verify_gateway_token)]
