from secrets import compare_digest
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status

from sensemu_api.config import get_settings


def verify_platform_review_token(
    token: Annotated[str, Header(alias="X-SenseMu-Platform-Review-Token")],
) -> None:
    if not compare_digest(token, get_settings().platform_review_token):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="平台审核凭据无效",
        )


PlatformReviewAuth = Annotated[None, Depends(verify_platform_review_token)]
