from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from sensemu_api.catalog_schemas import DatasetVersionQualityReport


class DataListingCreate(BaseModel):
    title: str = Field(min_length=2, max_length=180)
    summary: str = Field(min_length=12, max_length=1_200)
    source_summary: str = Field(min_length=12, max_length=2_000)
    collection_method: str = Field(min_length=8, max_length=2_000)
    coverage_summary: str = Field(min_length=8, max_length=2_000)
    known_limitations: str = Field(min_length=8, max_length=2_000)
    license_code: Literal[
        "CC0-1.0",
        "CC-BY-4.0",
        "ODC-BY-1.0",
        "CUSTOM-COMMERCIAL",
    ]
    custom_license_terms: str | None = Field(default=None, max_length=4_000)
    allow_commercial_use: bool
    allow_model_training: bool
    allow_derivative_models: bool
    allow_redistribution: bool
    contains_personal_data: bool
    privacy_treatment: str = Field(min_length=4, max_length=2_000)
    rights_confirmed: Literal[True]

    @model_validator(mode="after")
    def validate_custom_terms(self) -> "DataListingCreate":
        if self.license_code == "CUSTOM-COMMERCIAL" and not (
            self.custom_license_terms and self.custom_license_terms.strip()
        ):
            raise ValueError("自定义商业许可必须填写完整授权条款")
        return self


class DataListingResponse(BaseModel):
    id: UUID
    provider_workspace_id: UUID
    provider_name: str
    dataset_version_id: UUID
    dataset_id: UUID
    dataset_name: str
    dataset_version_number: int
    project_name: str
    task_type: str
    asset_count: int
    class_map: dict[str, str]
    quality_report: DatasetVersionQualityReport | None
    title: str
    summary: str
    source_summary: str
    collection_method: str
    coverage_summary: str
    known_limitations: str
    license_code: str
    custom_license_terms: str | None
    allow_commercial_use: bool
    allow_model_training: bool
    allow_derivative_models: bool
    allow_redistribution: bool
    contains_personal_data: bool
    privacy_treatment: str
    review_basis: str
    status: str
    delivery_mode: str
    delivery_status: str
    delivery_spec_hash: str | None
    published_at: datetime


class DataDeliverySpecResponse(BaseModel):
    listing_id: UUID
    schema_version: str
    delivery_mode: str
    delivery_status: str
    access_boundary: list[str]
    activation_requirements: list[str]
    content_hash: str
    created_at: datetime
