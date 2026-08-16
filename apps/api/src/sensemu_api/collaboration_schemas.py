from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

WorkspaceRole = Literal["viewer", "member", "admin"]


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class WorkspaceMemberResponse(BaseModel):
    id: UUID
    user_id: UUID
    email: str | None
    display_name: str | None
    role: str
    status: str
    joined_at: datetime
    is_current_user: bool = False


class WorkspaceInvitationCreate(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    role: WorkspaceRole = "member"

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        cleaned = value.strip()
        local, separator, domain = cleaned.rpartition("@")
        if not separator or not local or "." not in domain or any(
            character.isspace() for character in cleaned
        ):
            raise ValueError("请输入有效的邮箱地址")
        return cleaned


class WorkspaceInvitationResponse(BaseModel):
    id: UUID
    email: str
    role: str
    status: str
    token_prefix: str
    invited_by_user_id: UUID
    expires_at: datetime
    accepted_at: datetime | None
    revoked_at: datetime | None
    created_at: datetime


class WorkspaceInvitationSecretResponse(WorkspaceInvitationResponse):
    invite_token: str
    acceptance_url: str


class WorkspaceInvitationAccept(BaseModel):
    invite_token: str = Field(
        min_length=32,
        max_length=160,
        pattern=r"^smu_invite_[A-Za-z0-9_-]+$",
    )


class WorkspaceMemberRoleUpdate(BaseModel):
    role: WorkspaceRole


class WorkspaceAccessEventResponse(BaseModel):
    id: UUID
    event_type: str
    actor_user_id: UUID
    actor_name: str
    target_user_id: UUID | None
    target_name: str | None
    invitation_id: UUID | None
    details: dict[str, Any]
    occurred_at: datetime
