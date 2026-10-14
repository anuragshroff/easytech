import uuid
from datetime import datetime, timezone

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.future import select

from api.db.base_client import BaseDBClient
from api.db.models import UserConfigurationModel, UserModel


class UserClient(BaseDBClient):
    async def get_or_create_user_by_provider_id(
        self, provider_id: str
    ) -> tuple[UserModel, bool]:
        """Return (user, was_created) tuple."""
        async with self.async_session() as session:
            # First try to get existing user
            result = await session.execute(
                select(UserModel).where(UserModel.provider_id == provider_id)
            )
            user = result.scalars().first()

            if user is not None:
                return user, False

            # Use PostgreSQL's INSERT ... ON CONFLICT DO NOTHING
            # This is atomic and handles race conditions at the database level
            stmt = insert(UserModel.__table__).values(
                provider_id=provider_id,
                created_at=datetime.now(timezone.utc),
                selected_organization_id=None,  # Will be set later
                is_superuser=False,  # Default value
            )
            # ON CONFLICT DO NOTHING - if another request already inserted, this becomes a no-op
            stmt = stmt.on_conflict_do_nothing(index_elements=["provider_id"])

            result = await session.execute(stmt)
            await session.commit()
            was_created = result.rowcount > 0

            # Now fetch the user (either the one we just created or the one that existed)
            result = await session.execute(
                select(UserModel).where(UserModel.provider_id == provider_id)
            )
            user = result.scalars().first()

            if user is None:
                # This should never happen, but handle it just in case
                error_msg = (
                    f"Failed to create or fetch user with provider_id {provider_id}"
                )
                raise ValueError(error_msg)
        return user, was_created

    async def get_user_by_id(self, user_id: int) -> UserModel | None:
        """Fetch a user by their internal ID."""
        async with self.async_session() as session:
            result = await session.execute(
                select(UserModel).where(UserModel.id == user_id)
            )
            return result.scalars().first()

    async def _get_user_configuration_row(
        self, session, user_id: int, key: str
    ) -> UserConfigurationModel | None:
        result = await session.execute(
            select(UserConfigurationModel).where(
                UserConfigurationModel.user_id == user_id,
                UserConfigurationModel.key == key,
            )
        )
        return result.scalars().first()

    async def get_user_configuration_value(self, user_id: int, key: str) -> dict | None:
        """Get the JSON value stored for a user under `key`, or None."""
        async with self.async_session() as session:
            row = await self._get_user_configuration_row(session, user_id, key)
            return row.configuration if row else None

    async def upsert_user_configuration_value(
        self, user_id: int, key: str, value: dict
    ) -> dict:
        """Create or update the JSON value stored for a user under `key`."""
        async with self.async_session() as session:
            stmt = insert(UserConfigurationModel.__table__).values(
                user_id=user_id,
                key=key,
                configuration=value,
            )
            stmt = stmt.on_conflict_do_update(
                constraint="_user_configuration_key_uc",
                set_={"configuration": stmt.excluded.configuration},
            ).returning(UserConfigurationModel.configuration)
            try:
                result = await session.execute(stmt)
                await session.commit()
            except Exception as e:
                await session.rollback()
                raise e
            return result.scalar_one()

    async def update_user_selected_organization(
        self, user_id: int, organization_id: int
    ) -> None:
        """Update the user's selected organization ID."""
        async with self.async_session() as session:
            from sqlalchemy import update

            # Use a direct UPDATE statement to avoid race conditions
            # This is atomic at the database level
            stmt = (
                update(UserModel)
                .where(UserModel.id == user_id)
                .values(selected_organization_id=organization_id)
            )

            result = await session.execute(stmt)

            if result.rowcount == 0:
                raise ValueError(f"User with ID {user_id} not found")

            await session.commit()

    async def update_user_email(self, user_id: int, email: str) -> None:
        """Update the user's email address."""
        async with self.async_session() as session:
            from sqlalchemy import update

            stmt = (
                update(UserModel)
                .where(UserModel.id == user_id)
                .values(email=email.lower())
            )
            await session.execute(stmt)
            await session.commit()

    async def set_superuser(self, user_id: int, is_superuser: bool) -> bool | None:
        """Set a user's superuser flag. Returns the new value, or None if the
        user does not exist."""
        from sqlalchemy import update

        async with self.async_session() as session:
            stmt = (
                update(UserModel)
                .where(UserModel.id == user_id)
                .values(is_superuser=is_superuser)
            )
            result = await session.execute(stmt)
            await session.commit()
            if result.rowcount == 0:
                return None
            return is_superuser

    async def set_user_active(self, user_id: int, is_active: bool) -> bool | None:
        """Enable or disable a user account. Returns the new value, or None if
        the user does not exist."""
        from sqlalchemy import update

        async with self.async_session() as session:
            stmt = (
                update(UserModel)
                .where(UserModel.id == user_id)
                .values(is_active=is_active)
            )
            result = await session.execute(stmt)
            await session.commit()
            if result.rowcount == 0:
                return None
            return is_active

    async def get_user_by_email(self, email: str) -> UserModel | None:
        """Fetch a user by their email address (case-insensitive).

        Email addresses are case-insensitive in practice, so a user who
        signed up as "User@example.com" must still be found when they later
        log in as "user@example.com". Compare on lower(email) so lookups are
        robust to capitalization differences across sign-in flows.
        """
        normalized_email = email.lower()
        async with self.async_session() as session:
            result = await session.execute(
                select(UserModel).where(func.lower(UserModel.email) == normalized_email)
            )
            return result.scalars().first()

    async def create_user_with_email(
        self, email: str, password_hash: str, name: str | None = None
    ) -> UserModel:
        """Create a new user with email and password hash."""
        async with self.async_session() as session:
            user = UserModel(
                provider_id=f"oss_{int(datetime.now(timezone.utc).timestamp())}_{uuid.uuid4()}",
                email=email.lower(),
                password_hash=password_hash,
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
            return user

    async def get_users_for_superadmin(
        self,
        limit: int = 50,
        offset: int = 0,
        search: str | None = None,
    ) -> tuple[list[dict], int]:
        """Paginated all-users list for the admin panel, with org info."""
        async with self.async_session() as session:
            base_query = select(UserModel)
            if search:
                base_query = base_query.where(
                    func.lower(UserModel.email).ilike(f"%{search.strip().lower()}%")
                )

            count_result = await session.execute(
                select(func.count()).select_from(base_query.subquery())
            )
            total_count = count_result.scalar() or 0

            result = await session.execute(
                base_query.order_by(UserModel.created_at.desc())
                .offset(offset)
                .limit(limit)
            )
            rows = result.scalars().all()

            users = [
                {
                    "id": user.id,
                    "email": user.email,
                    "provider_id": user.provider_id,
                    "is_superuser": user.is_superuser,
                    "is_active": user.is_active,
                    "organization_id": user.selected_organization_id,
                    "created_at": user.created_at,
                }
                for user in rows
            ]
            return users, total_count
