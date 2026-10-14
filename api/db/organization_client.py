from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import exists, func, insert, select

from api.db.base_client import BaseDBClient
from api.db.models import (
    APIKeyModel,
    OrganizationModel,
    UserModel,
    WorkflowModel,
    WorkflowRunModel,
    organization_users_association,
)
from api.utils.api_key import generate_api_key


class OrganizationClient(BaseDBClient):
    async def get_organization_by_id(
        self, organization_id: int
    ) -> Optional[OrganizationModel]:
        """Get an organization by its ID."""
        async with self.async_session() as session:
            result = await session.execute(
                select(OrganizationModel).where(OrganizationModel.id == organization_id)
            )
            return result.scalars().first()

    async def get_organization_users(self, organization_id: int) -> list[UserModel]:
        """Get all users linked to an organization (many-to-many)."""
        async with self.async_session() as session:
            result = await session.execute(
                select(UserModel)
                .join(
                    organization_users_association,
                    organization_users_association.c.user_id == UserModel.id,
                )
                .where(
                    organization_users_association.c.organization_id == organization_id
                )
                .order_by(UserModel.id)
            )
            return list(result.scalars().all())

    async def get_or_create_organization_by_provider_id(
        self, org_provider_id: str, user_id: int
    ) -> tuple[OrganizationModel, bool]:
        """Get an existing organization by provider_id or create a new one.

        Returns:
            A tuple of (organization, was_created) where was_created is True if the organization
            was created in this call, False if it already existed.
        """
        async with self.async_session() as session:
            # First try to get existing organization
            result = await session.execute(
                select(OrganizationModel).where(
                    OrganizationModel.provider_id == org_provider_id
                )
            )
            organization = result.scalars().first()

            if organization is None:
                # Use PostgreSQL's INSERT ... ON CONFLICT DO NOTHING
                # This is atomic and handles race conditions at the database level

                stmt = insert(OrganizationModel.__table__).values(
                    provider_id=org_provider_id, created_at=datetime.now(timezone.utc)
                )
                # ON CONFLICT DO NOTHING - if another request already inserted, this becomes a no-op
                stmt = stmt.on_conflict_do_nothing(index_elements=["provider_id"])

                result = await session.execute(stmt)
                await session.commit()

                # Check if we actually inserted (rowcount > 0) or if there was a conflict (rowcount == 0)
                was_created = result.rowcount > 0

                # Now fetch the organization (either the one we just created or the one that existed)
                result = await session.execute(
                    select(OrganizationModel).where(
                        OrganizationModel.provider_id == org_provider_id
                    )
                )
                organization = result.scalars().first()

                if organization is None:
                    # This should never happen, but handle it just in case
                    error_msg = f"Failed to create or fetch organization with provider_id {org_provider_id}"
                    raise ValueError(error_msg)

                # Only create API key if we actually created the organization
                if was_created:
                    # Create a default API key for the new organization
                    _, key_hash, key_prefix = generate_api_key()

                    api_key = APIKeyModel(
                        organization_id=organization.id,
                        name="Default API Key",
                        key_hash=key_hash,
                        key_prefix=key_prefix,
                        is_active=True,
                        created_by=user_id,
                    )
                    session.add(api_key)
                    await session.commit()

                await session.refresh(organization)
                return organization, was_created
            return organization, False

    async def is_user_member_of_organization(
        self, user_id: int, organization_id: int
    ) -> bool:
        """Return True if the user belongs to the given organization."""
        async with self.async_session() as session:
            result = await session.execute(
                select(
                    exists().where(
                        (organization_users_association.c.user_id == user_id)
                        & (
                            organization_users_association.c.organization_id
                            == organization_id
                        )
                    )
                )
            )
            return bool(result.scalar())

    async def add_user_to_organization(
        self, user_id: int, organization_id: int
    ) -> None:
        """Ensure that a user is linked to an organization (many-to-many).

        The association is created only if it does not already exist.
        Uses INSERT ... ON CONFLICT DO NOTHING to handle race conditions.
        """
        async with self.async_session() as session:
            # Use PostgreSQL's INSERT ... ON CONFLICT DO NOTHING
            # This handles race conditions at the database level

            stmt = insert(organization_users_association).values(
                user_id=user_id, organization_id=organization_id
            )
            # ON CONFLICT DO NOTHING - if another request already inserted, this becomes a no-op
            # The primary key constraint on (user_id, organization_id) will trigger the conflict
            stmt = stmt.on_conflict_do_nothing()

            await session.execute(stmt)
            await session.commit()

    async def get_organizations_for_superadmin(
        self,
        limit: int = 50,
        offset: int = 0,
        search: str | None = None,
    ) -> tuple[list[dict], int]:
        """Paginated all-organizations list for the admin panel, with member and
        run counts."""
        async with self.async_session() as session:
            member_count = (
                select(func.count())
                .select_from(organization_users_association)
                .where(
                    organization_users_association.c.organization_id
                    == OrganizationModel.id
                )
                .correlate(OrganizationModel)
                .scalar_subquery()
                .label("user_count")
            )
            run_count = (
                select(func.count(WorkflowRunModel.id))
                .select_from(WorkflowRunModel)
                .join(WorkflowModel, WorkflowRunModel.workflow_id == WorkflowModel.id)
                .where(WorkflowModel.organization_id == OrganizationModel.id)
                .correlate(OrganizationModel)
                .scalar_subquery()
                .label("run_count")
            )

            base_query = select(
                OrganizationModel.id,
                OrganizationModel.provider_id,
                OrganizationModel.created_at,
                member_count,
                run_count,
            )
            if search:
                base_query = base_query.where(
                    OrganizationModel.provider_id.ilike(f"%{search.strip()}%")
                )

            count_result = await session.execute(
                select(func.count()).select_from(base_query.subquery())
            )
            total_count = count_result.scalar() or 0

            result = await session.execute(
                base_query.order_by(OrganizationModel.created_at.desc())
                .offset(offset)
                .limit(limit)
            )
            organizations = [
                {
                    "id": row.id,
                    "provider_id": row.provider_id,
                    "created_at": row.created_at,
                    "user_count": row.user_count,
                    "run_count": row.run_count,
                }
                for row in result.all()
            ]
            return organizations, total_count

    async def get_organization_detail_superadmin(self, organization_id: int) -> dict | None:
        """Organization header + counts for the admin drill-down page."""
        async with self.async_session() as session:
            member_count = (
                select(func.count())
                .select_from(organization_users_association)
                .where(
                    organization_users_association.c.organization_id
                    == OrganizationModel.id
                )
                .correlate(OrganizationModel)
                .scalar_subquery()
                .label("user_count")
            )
            run_count = (
                select(func.count(WorkflowRunModel.id))
                .select_from(WorkflowRunModel)
                .join(WorkflowModel, WorkflowRunModel.workflow_id == WorkflowModel.id)
                .where(WorkflowModel.organization_id == OrganizationModel.id)
                .correlate(OrganizationModel)
                .scalar_subquery()
                .label("run_count")
            )
            workflow_count = (
                select(func.count(WorkflowModel.id))
                .where(WorkflowModel.organization_id == OrganizationModel.id)
                .correlate(OrganizationModel)
                .scalar_subquery()
                .label("workflow_count")
            )
            result = await session.execute(
                select(
                    OrganizationModel.id,
                    OrganizationModel.provider_id,
                    OrganizationModel.created_at,
                    OrganizationModel.price_per_second_usd,
                    member_count,
                    run_count,
                    workflow_count,
                ).where(OrganizationModel.id == organization_id)
            )
            row = result.first()
            if row is None:
                return None
            return {
                "id": row.id,
                "provider_id": row.provider_id,
                "created_at": row.created_at,
                "price_per_second_usd": row.price_per_second_usd,
                "user_count": row.user_count,
                "run_count": row.run_count,
                "workflow_count": row.workflow_count,
            }

    async def get_organization_workflows_superadmin(
        self, organization_id: int
    ) -> list[dict]:
        """Workflows owned by an organization, with run counts."""
        async with self.async_session() as session:
            run_count = (
                select(func.count(WorkflowRunModel.id))
                .where(WorkflowRunModel.workflow_id == WorkflowModel.id)
                .correlate(WorkflowModel)
                .scalar_subquery()
                .label("run_count")
            )
            result = await session.execute(
                select(
                    WorkflowModel.id,
                    WorkflowModel.name,
                    WorkflowModel.status,
                    WorkflowModel.created_at,
                    run_count,
                )
                .where(WorkflowModel.organization_id == organization_id)
                .order_by(WorkflowModel.created_at.desc())
            )
            return [
                {
                    "id": row.id,
                    "name": row.name,
                    "status": str(row.status),
                    "created_at": row.created_at,
                    "run_count": row.run_count,
                }
                for row in result.all()
            ]

    async def get_organization_runs_superadmin(
        self, organization_id: int, limit: int = 50, offset: int = 0
    ) -> tuple[list[dict], int]:
        """Recent workflow runs for every workflow owned by an organization."""
        async with self.async_session() as session:
            base_query = (
                select(WorkflowRunModel)
                .join(WorkflowModel, WorkflowRunModel.workflow_id == WorkflowModel.id)
                .where(WorkflowModel.organization_id == organization_id)
            )
            count_result = await session.execute(
                base_query.with_only_columns(func.count(WorkflowRunModel.id))
            )
            total_count = count_result.scalar() or 0

            result = await session.execute(
                base_query.add_columns(WorkflowModel.name.label("workflow_name"))
                .order_by(WorkflowRunModel.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
            return (
                [
                    {
                        "id": run.id,
                        "name": run.name,
                        "workflow_id": run.workflow_id,
                        "workflow_name": workflow_name,
                        "mode": run.mode,
                        "is_completed": run.is_completed,
                        "recording_url": run.recording_url,
                        "transcript_url": run.transcript_url,
                        "created_at": run.created_at,
                    }
                    for run, workflow_name in result.all()
                ],
                total_count,
            )
