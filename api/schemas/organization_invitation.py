"""Request/response schemas for organization invitations."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class InvitationCreateRequest(BaseModel):
    email: EmailStr
    role: str = Field(default="member", max_length=32)


class InvitationAcceptRequest(BaseModel):
    token: str = Field(..., min_length=8)


class InvitationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    email: str
    role: str
    invited_by: Optional[int] = None
    accepted_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    created_at: datetime
    # Only returned on create — never persisted or echoed on reads.
    token: Optional[str] = None


class InvitationListResponse(BaseModel):
    invitations: list[InvitationResponse]
