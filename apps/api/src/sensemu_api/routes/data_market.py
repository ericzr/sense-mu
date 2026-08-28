from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from sensemu_api import data_market_service
from sensemu_api.data_market_schemas import (
    DataDeliverySpecResponse,
    DataListingCreate,
    DataListingResponse,
)
from sensemu_api.db.session import get_session
from sensemu_api.dependencies import WorkspaceAdminId, WorkspaceId
from sensemu_api.storage import Storage, get_storage

router = APIRouter(prefix="/api/v1", tags=["data-market"])
SessionDep = Annotated[Session, Depends(get_session)]
StorageDep = Annotated[Storage, Depends(get_storage)]


@router.get("/data-market/listings", response_model=list[DataListingResponse])
def list_data_listings(
    _workspace_id: WorkspaceId,
    session: SessionDep,
    storage: StorageDep,
) -> list[DataListingResponse]:
    return data_market_service.list_listings(session, storage)


@router.get("/data-market/listings/public", response_model=list[DataListingResponse])
def list_public_data_listings(
    session: SessionDep,
    storage: StorageDep,
) -> list[DataListingResponse]:
    return data_market_service.list_listings(session, storage)


@router.post(
    "/dataset-versions/{dataset_version_id}/data-listing",
    response_model=DataListingResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_data_listing(
    dataset_version_id: UUID,
    payload: DataListingCreate,
    workspace_id: WorkspaceAdminId,
    session: SessionDep,
    storage: StorageDep,
) -> DataListingResponse:
    return data_market_service.create_listing(
        session, storage, workspace_id, dataset_version_id, payload
    )


@router.get(
    "/data-market/listings/{listing_id}/delivery-spec",
    response_model=DataDeliverySpecResponse,
)
def get_data_delivery_spec(
    listing_id: UUID,
    _workspace_id: WorkspaceId,
    session: SessionDep,
) -> DataDeliverySpecResponse:
    return data_market_service.get_delivery_spec(session, listing_id)
