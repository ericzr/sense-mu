from secrets import compare_digest
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status

from sensemu_api.config import get_settings


def verify_worker_token(
    token: Annotated[str, Header(alias="X-SenseMu-Worker-Token")],
) -> None:
    if not compare_digest(token, get_settings().worker_token):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Worker 凭据无效",
        )


WorkerAuth = Annotated[None, Depends(verify_worker_token)]
