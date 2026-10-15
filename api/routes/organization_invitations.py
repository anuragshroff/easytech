"""Organization invitation endpoints.

An invitation lets an email address join an existing organization. In OSS the
default signup provisions a fresh one-org-per-user organization; a pending
invitation for that email overrides it (see ``api/routes/auth.py``).

Email delivery is NOT wired up in OSS — no SMTP/transport exists yet. Until it
is, ``create`` returns the raw invite ``token`` in the response so an operator
can pass it along manually. Wire an email sender where ``_deliver_invitation``
is defined; nothing else here changes.
"""

from typing import List

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger

from api.db import db_client
from api.db.models import UserModel
from api.db.organization_invitation_client import (
    OrganizationInvitationConflictError,
)
from api.schemas.organization_invitation import (
    InvitationAcceptRequest,
    InvitationCreateRequest,
    InvitationListResponse,
    InvitationResponse,
)
from api.services.auth.depends import get_user

router = APIRouter(prefix="/organizations", tags=["organizations"])


def _to_response(row, include_token: str | None = None) -> InvitationResponse:
    response = InvitationResponse.model_validate(row)
    response.token = include_token
    return response


def _require_org(user: UserModel) -> int:
    if not user.selected_organization_id:
        raise HTTPException(status_code=400, detail="No organization selected")
    return user.selected_organization_id


async def _deliver_invitation(
    email: str, organization_id: int, raw_token: str
) -> None:
    """Send the invite to the invitee.

    ponytail: no email transport exists in OSS. Log the token so a manual
    operator flow is possible; replace with a real sender (SMTP / provider API)
    when outbound email is introduced. Token is also returned by the API.
    """
    logger.info(
        f"Organization invitation created for {email} "
        f"(organization_id={organization_id}); deliver token out-of-band"
    )


@router.post("/invitations", response_model=InvitationResponse)
async def create_invitation(
    request: InvitationCreateRequest,
    user: UserModel = Depends(get_user),
):
    organization_id = _require_org(user)

    try:
        row, raw_token = await db_client.create_invitation(
            organization_id=organization_id,
            email=request.email,
            invited_by=user.id,
            role=request.role,
        )
    except OrganizationInvitationConflictError:
        raise HTTPException(
            status_code=409,
            detail="A pending invitation for this email already exists.",
        )

    await _deliver_invitation(row.email, organization_id, raw_token)
    return _to_response(row, include_token=raw_token)


@router.get("/invitations", response_model=InvitationListResponse)
async def list_invitations(user: UserModel = Depends(get_user)):
    organization_id = _require_org(user)
    rows: List = await db_client.list_invitations(organization_id)
    return InvitationListResponse(invitations=[_to_response(r) for r in rows])


@router.delete("/invitations/{invitation_id}")
async def revoke_invitation(
    invitation_id: int,
    user: UserModel = Depends(get_user),
):
    organization_id = _require_org(user)
    revoked = await db_client.revoke_invitation(invitation_id, organization_id)
    if not revoked:
        raise HTTPException(status_code=404, detail="Invitation not found")
    return {"ok": True}


@router.post("/invitations/accept")
async def accept_invitation(
    request: InvitationAcceptRequest,
    user: UserModel = Depends(get_user),
):
    """Join the inviting organization via a token.

    Works for an already-authenticated user; new users join at signup time
    (``api/routes/auth.py``). Idempotent: accepting twice is a no-op.
    """
    invitation = await db_client.get_pending_invitation_by_token(request.token)
    if not invitation:
        raise HTTPException(
            status_code=404, detail="Invitation not found, expired, or already used"
        )

    await db_client.add_user_to_organization(user.id, invitation.organization_id)
    await db_client.update_user_selected_organization(
        user.id, invitation.organization_id
    )
    await db_client.accept_invitation(invitation.id, user.id)

    return {
        "ok": True,
        "organization_id": invitation.organization_id,
    }
