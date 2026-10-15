"""Database access for organization invitations.

An invitation lets an email join an existing organization instead of the
one-per-signup organization OSS creates by default. Only the SHA256 hash of the
token is stored; the raw token is returned once, at creation, and must travel
to the invitee out-of-band (email — see ``api/routes/organization_invitations``).
"""

import secrets
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError

from api.db.base_client import BaseDBClient
from api.db.models import OrganizationInvitationModel
from api.utils.api_key import hash_api_key

INVITATION_TTL_DAYS = 14


class OrganizationInvitationConflictError(Exception):
    """Raised when a pending invitation for (org, email) already exists."""


def _normalize_email(email: str) -> str:
    return email.strip().lower()


class OrganizationInvitationClient(BaseDBClient):
    async def create_invitation(
        self,
        organization_id: int,
        email: str,
        invited_by: Optional[int] = None,
        role: str = "member",
        ttl_days: int = INVITATION_TTL_DAYS,
    ) -> Tuple[OrganizationInvitationModel, str]:
        """Create a pending invitation. Returns (row, raw_token).

        The raw token is only ever available here — callers must surface it to
        the invitee (email / link) immediately.
        """
        email = _normalize_email(email)
        raw_token = f"inv_{secrets.token_urlsafe(32)}"
        expires_at = datetime.now(timezone.utc) + timedelta(days=ttl_days)

        async with self.async_session() as session:
            row = OrganizationInvitationModel(
                organization_id=organization_id,
                email=email,
                role=role,
                token_hash=hash_api_key(raw_token),
                invited_by=invited_by,
                expires_at=expires_at,
            )
            session.add(row)
            try:
                await session.commit()
            except IntegrityError as e:
                await session.rollback()
                raise OrganizationInvitationConflictError(str(e)) from e
            await session.refresh(row)
            return row, raw_token

    async def list_invitations(
        self, organization_id: int, include_accepted: bool = False
    ) -> List[OrganizationInvitationModel]:
        async with self.async_session() as session:
            stmt = select(OrganizationInvitationModel).where(
                OrganizationInvitationModel.organization_id == organization_id
            )
            if not include_accepted:
                stmt = stmt.where(OrganizationInvitationModel.accepted_at.is_(None))
            result = await session.execute(
                stmt.order_by(OrganizationInvitationModel.created_at.desc())
            )
            return list(result.scalars().all())

    async def get_invitation(
        self, invitation_id: int, organization_id: int
    ) -> Optional[OrganizationInvitationModel]:
        async with self.async_session() as session:
            result = await session.execute(
                select(OrganizationInvitationModel).where(
                    OrganizationInvitationModel.id == invitation_id,
                    OrganizationInvitationModel.organization_id == organization_id,
                )
            )
            return result.scalars().first()

    async def get_pending_invitation_by_token(
        self, raw_token: str
    ) -> Optional[OrganizationInvitationModel]:
        async with self.async_session() as session:
            result = await session.execute(
                select(OrganizationInvitationModel).where(
                    OrganizationInvitationModel.token_hash == hash_api_key(raw_token),
                    OrganizationInvitationModel.accepted_at.is_(None),
                )
            )
            row = result.scalars().first()
            return row if row and not self._is_expired(row) else None

    async def get_pending_invitations_for_email(
        self, email: str
    ) -> List[OrganizationInvitationModel]:
        """Pending, unexpired invitations for an email, newest first."""
        async with self.async_session() as session:
            result = await session.execute(
                select(OrganizationInvitationModel)
                .where(
                    func.lower(OrganizationInvitationModel.email) == _normalize_email(email),
                    OrganizationInvitationModel.accepted_at.is_(None),
                )
                .order_by(OrganizationInvitationModel.created_at.desc())
            )
            now = datetime.now(timezone.utc)
            return [r for r in result.scalars().all() if not self._is_expired(r, now)]

    async def accept_invitation(
        self, invitation_id: int, user_id: int
    ) -> Optional[OrganizationInvitationModel]:
        async with self.async_session() as session:
            row = await session.get(OrganizationInvitationModel, invitation_id)
            if not row or row.accepted_at is not None:
                return None
            row.accepted_at = datetime.now(timezone.utc)
            row.accepted_by = user_id
            await session.commit()
            await session.refresh(row)
            return row

    async def revoke_invitation(self, invitation_id: int, organization_id: int) -> bool:
        async with self.async_session() as session:
            result = await session.execute(
                delete(OrganizationInvitationModel).where(
                    OrganizationInvitationModel.id == invitation_id,
                    OrganizationInvitationModel.organization_id == organization_id,
                    OrganizationInvitationModel.accepted_at.is_(None),
                )
            )
            await session.commit()
            return result.rowcount > 0

    @staticmethod
    def _is_expired(
        row: OrganizationInvitationModel, now: Optional[datetime] = None
    ) -> bool:
        if row.expires_at is None:
            return False
        now = now or datetime.now(timezone.utc)
        expires_at = row.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        return expires_at < now
