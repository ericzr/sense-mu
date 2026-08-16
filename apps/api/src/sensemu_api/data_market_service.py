import json
from datetime import UTC, datetime
from hashlib import sha256
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from sensemu_api.catalog_schemas import DatasetVersionQualityReport
from sensemu_api.catalog_service import build_dataset_quality_report, conflict
from sensemu_api.data_market_schemas import (
    DataDeliverySpecResponse,
    DataListingCreate,
    DataListingResponse,
)
from sensemu_api.db.models import (
    DataDeliverySpec,
    DataMarketplaceListing,
    Dataset,
    DatasetVersion,
    Project,
    Workspace,
)
from sensemu_api.storage import Storage

DELIVERY_MODE = "workspace_copy_after_authorization"
DELIVERY_STATUS = "prepared_not_open"
ACCESS_BOUNDARY = [
    "公开目录不提供对象地址、内部清单或样本下载链接",
    "交付仅导入已授权的买方工作区",
    "原始对象存储不会向买方生成直链",
    "撤销仅阻断后续平台访问，已取得副本按许可合同处理",
]
ACTIVATION_REQUIREMENTS = [
    "有效的数据访问授权",
    "许可条款确认",
    "买方工作区确认",
]


def _delivery_document(
    listing: DataMarketplaceListing,
    version: DatasetVersion,
    quality_report: DatasetVersionQualityReport | None,
) -> dict[str, object]:
    return {
        "apiVersion": "sensemu.ai/v1",
        "kind": "DataDeliverySpec",
        "metadata": {
            "listing_id": str(listing.id),
            "dataset_version_id": str(version.id),
            "schema_version": "1.0",
            "status": DELIVERY_STATUS,
        },
        "spec": {
            "delivery_mode": DELIVERY_MODE,
            "access_boundary": ACCESS_BOUNDARY,
            "activation_requirements": ACTIVATION_REQUIREMENTS,
            "dataset_snapshot": {
                "dataset_version_id": str(version.id),
                "version_number": version.version_number,
                "asset_count": version.asset_count,
                "class_map": version.class_map,
                "frozen_at": version.frozen_at.isoformat() if version.frozen_at else None,
                "quality_report": (
                    quality_report.model_dump(mode="json") if quality_report else None
                ),
            },
            "license_snapshot": {
                "license_code": listing.license_code,
                "custom_license_terms": listing.custom_license_terms,
                "allow_commercial_use": listing.allow_commercial_use,
                "allow_model_training": listing.allow_model_training,
                "allow_derivative_models": listing.allow_derivative_models,
                "allow_redistribution": listing.allow_redistribution,
            },
        },
    }


def _delivery_response(spec: DataDeliverySpec) -> DataDeliverySpecResponse:
    return DataDeliverySpecResponse(
        listing_id=spec.listing_id,
        schema_version=spec.schema_version,
        delivery_mode=spec.delivery_mode,
        delivery_status=spec.delivery_status,
        access_boundary=spec.access_boundary,
        activation_requirements=spec.activation_requirements,
        content_hash=spec.content_hash,
        created_at=spec.created_at,
    )


def _quality_report(
    storage: Storage,
    version: DatasetVersion,
) -> DatasetVersionQualityReport | None:
    try:
        manifest = storage.get_json(version.manifest_uri)
    except (OSError, ValueError, KeyError):
        return None
    report = manifest.get("quality_report")
    if not isinstance(report, dict):
        assets = manifest.get("assets")
        class_map = manifest.get("class_map")
        if not isinstance(assets, list) or not isinstance(class_map, dict):
            return None
        report = build_dataset_quality_report(storage, assets, class_map)
    return DatasetVersionQualityReport.model_validate(
        {"dataset_version_id": version.id, **report}
    )


def _listing_response(
    session: Session,
    storage: Storage,
    listing: DataMarketplaceListing,
) -> DataListingResponse:
    record = session.execute(
        select(DatasetVersion, Dataset, Project, Workspace, DataDeliverySpec)
        .join(Dataset, Dataset.id == DatasetVersion.dataset_id)
        .join(Project, Project.id == Dataset.project_id)
        .join(Workspace, Workspace.id == Project.workspace_id)
        .outerjoin(DataDeliverySpec, DataDeliverySpec.listing_id == listing.id)
        .where(DatasetVersion.id == listing.dataset_version_id)
    ).one()
    version, dataset, project, provider, delivery_spec = record
    quality_report = _quality_report(storage, version)
    return DataListingResponse(
        id=listing.id,
        provider_workspace_id=listing.provider_workspace_id,
        provider_name=provider.name,
        dataset_version_id=version.id,
        dataset_id=dataset.id,
        dataset_name=dataset.name,
        dataset_version_number=version.version_number,
        project_name=project.name,
        task_type=project.task_type,
        asset_count=version.asset_count,
        class_map=version.class_map,
        quality_report=quality_report,
        title=listing.title,
        summary=listing.summary,
        source_summary=listing.source_summary,
        collection_method=listing.collection_method,
        coverage_summary=listing.coverage_summary,
        known_limitations=listing.known_limitations,
        license_code=listing.license_code,
        custom_license_terms=listing.custom_license_terms,
        allow_commercial_use=listing.allow_commercial_use,
        allow_model_training=listing.allow_model_training,
        allow_derivative_models=listing.allow_derivative_models,
        allow_redistribution=listing.allow_redistribution,
        contains_personal_data=listing.contains_personal_data,
        privacy_treatment=listing.privacy_treatment,
        review_basis=listing.review_basis,
        status=listing.status,
        delivery_mode=(delivery_spec.delivery_mode if delivery_spec else "not_prepared"),
        delivery_status=(delivery_spec.delivery_status if delivery_spec else "not_open"),
        delivery_spec_hash=(delivery_spec.content_hash if delivery_spec else None),
        published_at=listing.published_at,
    )


def create_listing(
    session: Session,
    storage: Storage,
    workspace_id: UUID,
    dataset_version_id: UUID,
    payload: DataListingCreate,
) -> DataListingResponse:
    record = session.execute(
        select(DatasetVersion, Dataset, Project)
        .join(Dataset, Dataset.id == DatasetVersion.dataset_id)
        .join(Project, Project.id == Dataset.project_id)
        .where(
            DatasetVersion.id == dataset_version_id,
            Project.workspace_id == workspace_id,
        )
        .with_for_update()
    ).one_or_none()
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="未找到可发布的数据版本",
        )
    version, _dataset, _project = record
    if version.status != "frozen" or version.frozen_at is None:
        raise conflict("只有已冻结的数据版本可以发布数据卡")
    if version.asset_count <= 0:
        raise conflict("空数据版本不能发布到数据市场")
    if payload.contains_personal_data:
        raise conflict("首阶段不开放含个人数据的数据资产，请先完成脱敏与专项审核")
    existing = session.scalar(
        select(DataMarketplaceListing).where(
            DataMarketplaceListing.dataset_version_id == dataset_version_id
        )
    )
    if existing is not None:
        raise conflict("该数据版本已经发布数据卡")
    listing = DataMarketplaceListing(
        provider_workspace_id=workspace_id,
        dataset_version_id=dataset_version_id,
        title=payload.title,
        summary=payload.summary,
        source_summary=payload.source_summary,
        collection_method=payload.collection_method,
        coverage_summary=payload.coverage_summary,
        known_limitations=payload.known_limitations,
        license_code=payload.license_code,
        custom_license_terms=payload.custom_license_terms,
        allow_commercial_use=payload.allow_commercial_use,
        allow_model_training=payload.allow_model_training,
        allow_derivative_models=payload.allow_derivative_models,
        allow_redistribution=payload.allow_redistribution,
        contains_personal_data=payload.contains_personal_data,
        privacy_treatment=payload.privacy_treatment,
        rights_confirmed=payload.rights_confirmed,
        review_basis="provider_attestation",
        status="published",
        published_at=datetime.now(UTC),
    )
    session.add(listing)
    session.flush()
    quality_report = _quality_report(storage, version)
    document = _delivery_document(listing, version, quality_report)
    encoded_document = json.dumps(
        document,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    delivery_spec = DataDeliverySpec(
        listing_id=listing.id,
        schema_version="1.0",
        delivery_mode=DELIVERY_MODE,
        delivery_status=DELIVERY_STATUS,
        access_boundary=ACCESS_BOUNDARY,
        activation_requirements=ACTIVATION_REQUIREMENTS,
        content_hash=sha256(encoded_document).hexdigest(),
        spec_uri=storage.put_json(
            f"data-market/listings/{listing.id}/delivery-spec.json",
            document,
        ),
    )
    session.add(delivery_spec)
    session.flush()
    return _listing_response(session, storage, listing)


def list_listings(session: Session, storage: Storage) -> list[DataListingResponse]:
    listings = session.scalars(
        select(DataMarketplaceListing)
        .where(DataMarketplaceListing.status == "published")
        .order_by(DataMarketplaceListing.published_at.desc())
    ).all()
    return [_listing_response(session, storage, listing) for listing in listings]


def get_delivery_spec(
    session: Session,
    listing_id: UUID,
) -> DataDeliverySpecResponse:
    spec = session.scalar(
        select(DataDeliverySpec)
        .join(
            DataMarketplaceListing,
            DataMarketplaceListing.id == DataDeliverySpec.listing_id,
        )
        .where(
            DataDeliverySpec.listing_id == listing_id,
            DataMarketplaceListing.status == "published",
        )
    )
    if spec is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="未找到已公开数据卡的交付规范",
        )
    return _delivery_response(spec)
