from datetime import datetime
from ipaddress import ip_address
from urllib.parse import urlparse
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class WorkflowSpecCreate(BaseModel):
    workflow_slug: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{2,79}$")
    display_name: str = Field(min_length=2, max_length=180)
    capability_spec_id: UUID
    event_types: list[str] = Field(min_length=1, max_length=8)
    deduplication_window_seconds: int = Field(ge=0, le=86_400)
    webhook_url: str = Field(min_length=12, max_length=2_000)

    @field_validator("webhook_url")
    @classmethod
    def require_public_https_webhook(cls, value: str) -> str:
        parsed = urlparse(value)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username:
            raise ValueError("Webhook 地址必须为不含凭据的 HTTPS 地址")
        try:
            port = parsed.port
        except ValueError as error:
            raise ValueError("Webhook 地址端口无效") from error
        if port not in {None, 443}:
            raise ValueError("Webhook 地址只能使用默认 HTTPS 端口")
        try:
            address = ip_address(parsed.hostname)
        except ValueError:
            return value
        if not address.is_global:
            raise ValueError("Webhook 地址不能指向本地或私有网络")
        return value


class WorkflowSpecResponse(BaseModel):
    id: UUID
    workspace_id: UUID
    project_id: UUID
    capability_spec_id: UUID
    capability_slug: str
    capability_version_number: int
    workflow_slug: str
    version_number: int
    display_name: str
    template_key: str
    event_types: list[str]
    deduplication_window_seconds: int
    webhook_url: str
    status: str
    content_hash: str
    spec_uri: str
    published_at: datetime
    created_at: datetime
