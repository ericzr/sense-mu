from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from sensemu_api.storage import LocalStorage, Storage, get_storage

router = APIRouter(prefix="/api/v1/dev-storage", tags=["development"])
MAX_LOCAL_UPLOAD_BYTES = 250 * 1024 * 1024
StorageDependency = Annotated[Storage, Depends(get_storage)]


@router.put("/{key:path}", status_code=status.HTTP_204_NO_CONTENT)
async def put_local_object(
    key: str,
    request: Request,
    storage: StorageDependency,
) -> Response:
    if not isinstance(storage, LocalStorage):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    content_length = int(request.headers.get("content-length", "0") or 0)
    if content_length > MAX_LOCAL_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail="Local upload exceeds 250 MB",
        )
    payload = await request.body()
    if len(payload) > MAX_LOCAL_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail="Local upload exceeds 250 MB",
        )
    storage.put_bytes(key, payload)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
