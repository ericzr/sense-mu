from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class IdentityMembershipResponse(BaseModel):
    workspace_id: UUID
    workspace_slug: str
    workspace_name: str
    role: str
    joined_at: datetime


class IdentityMeResponse(BaseModel):
    id: UUID
    email: str | None
    email_verified: bool
    display_name: str | None
    auth_mode: str
    memberships: list[IdentityMembershipResponse]
