"""Database access for the local wallet ledger.

Three tables back this: ``billing_settings`` (pricing + guard config, platform
default row plus optional per-org override), ``wallet_transactions`` (the
append-only money ledger; balance is the signed sum), and ``usage_records``
(one row per completed billable run).

Money is integer cents everywhere — never floats.
"""

from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from api.db.base_client import BaseDBClient
from api.db.models import (
    BillingSettingsModel,
    UsageRecordModel,
    WalletTransactionModel,
)

_SETTINGS_FIELDS = (
    "rate_cents_per_minute",
    "minimum_balance_cents",
    "enforce_pre_call_balance",
    "auto_recharge_enabled",
    "auto_recharge_threshold_cents",
    "auto_recharge_amount_cents",
    "payment_links",
)


class WalletClient(BaseDBClient):
    # --- settings ---------------------------------------------------------
    async def get_platform_settings(self) -> Optional[BillingSettingsModel]:
        async with self.async_session() as session:
            result = await session.execute(
                select(BillingSettingsModel).where(
                    BillingSettingsModel.organization_id.is_(None)
                )
            )
            return result.scalars().first()

    async def get_org_settings(
        self, organization_id: int
    ) -> Optional[BillingSettingsModel]:
        async with self.async_session() as session:
            result = await session.execute(
                select(BillingSettingsModel).where(
                    BillingSettingsModel.organization_id == organization_id
                )
            )
            return result.scalars().first()

    async def _upsert_settings(
        self, organization_id: Optional[int], fields: Dict[str, Any]
    ) -> BillingSettingsModel:
        values = {k: v for k, v in fields.items() if k in _SETTINGS_FIELDS}
        async with self.async_session() as session:
            stmt = select(BillingSettingsModel)
            if organization_id is None:
                stmt = stmt.where(BillingSettingsModel.organization_id.is_(None))
            else:
                stmt = stmt.where(
                    BillingSettingsModel.organization_id == organization_id
                )
            row = (await session.execute(stmt)).scalars().first()
            if row is None:
                row = BillingSettingsModel(organization_id=organization_id, **values)
                session.add(row)
            else:
                for key, value in values.items():
                    setattr(row, key, value)
            await session.commit()
            await session.refresh(row)
            return row

    async def upsert_platform_settings(self, **fields: Any) -> BillingSettingsModel:
        return await self._upsert_settings(None, fields)

    async def upsert_org_settings(
        self, organization_id: int, **fields: Any
    ) -> BillingSettingsModel:
        return await self._upsert_settings(organization_id, fields)

    # --- ledger -----------------------------------------------------------
    async def get_balance_cents(self, organization_id: int) -> int:
        async with self.async_session() as session:
            result = await session.execute(
                select(func.coalesce(func.sum(WalletTransactionModel.amount_cents), 0)).where(
                    WalletTransactionModel.organization_id == organization_id
                )
            )
            return int(result.scalar_one())

    async def add_transaction(
        self,
        organization_id: int,
        amount_cents: int,
        *,
        kind: str,
        source: str,
        description: Optional[str] = None,
        external_ref: Optional[str] = None,
        workflow_run_id: Optional[int] = None,
        created_by: Optional[int] = None,
    ) -> Optional[WalletTransactionModel]:
        """Append a ledger row. Returns None if the idempotency key already exists."""
        async with self.async_session() as session:
            stmt = (
                pg_insert(WalletTransactionModel)
                .values(
                    organization_id=organization_id,
                    amount_cents=amount_cents,
                    kind=kind,
                    source=source,
                    description=description,
                    external_ref=external_ref,
                    workflow_run_id=workflow_run_id,
                    created_by=created_by,
                )
                # ON CONFLICT DO NOTHING covers every unique constraint on the
                # table, so a replayed Stripe event or usage debit is a no-op
                # instead of an exception that would poison the session.
                .on_conflict_do_nothing()
                .returning(WalletTransactionModel)
            )
            row = (await session.execute(stmt)).scalars().first()
            await session.commit()
            return row

    async def list_transactions(
        self, organization_id: int, limit: int = 50, offset: int = 0
    ) -> List[WalletTransactionModel]:
        async with self.async_session() as session:
            result = await session.execute(
                select(WalletTransactionModel)
                .where(WalletTransactionModel.organization_id == organization_id)
                .order_by(WalletTransactionModel.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
            return list(result.scalars().all())

    # --- usage ------------------------------------------------------------
    async def record_usage_and_debit(
        self,
        organization_id: int,
        workflow_run_id: int,
        *,
        duration_seconds: int,
        rate_cents_per_minute: int,
        amount_cents: int,
    ) -> Optional[Tuple[UsageRecordModel, WalletTransactionModel]]:
        """Atomically record usage and its wallet debit for one run.

        Returns None when the run was already settled (unique workflow_run_id),
        which makes the settlement worker safe to retry.
        """
        async with self.async_session() as session:
            usage_stmt = (
                pg_insert(UsageRecordModel)
                .values(
                    organization_id=organization_id,
                    workflow_run_id=workflow_run_id,
                    duration_seconds=duration_seconds,
                    rate_cents_per_minute=rate_cents_per_minute,
                    amount_cents=amount_cents,
                )
                .on_conflict_do_nothing()
                .returning(UsageRecordModel)
            )
            usage = (await session.execute(usage_stmt)).scalars().first()
            if usage is None:
                # Already settled for this run; make the whole call a no-op.
                return None

            debit_stmt = (
                pg_insert(WalletTransactionModel)
                .values(
                    organization_id=organization_id,
                    amount_cents=-abs(amount_cents),
                    kind="usage",
                    source="usage",
                    description=f"Call usage for run {workflow_run_id}",
                    workflow_run_id=workflow_run_id,
                )
                .on_conflict_do_nothing()
                .returning(WalletTransactionModel)
            )
            debit = (await session.execute(debit_stmt)).scalars().first()
            if debit is None:
                await session.rollback()
                return None
            await session.commit()
            return usage, debit

    async def has_usage_record(self, workflow_run_id: int) -> bool:
        async with self.async_session() as session:
            result = await session.execute(
                select(func.count())
                .select_from(UsageRecordModel)
                .where(UsageRecordModel.workflow_run_id == workflow_run_id)
            )
            return int(result.scalar_one()) > 0

    async def list_usage_records(
        self, organization_id: int, limit: int = 50, offset: int = 0
    ) -> List[UsageRecordModel]:
        async with self.async_session() as session:
            result = await session.execute(
                select(UsageRecordModel)
                .where(UsageRecordModel.organization_id == organization_id)
                .order_by(UsageRecordModel.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
            return list(result.scalars().all())

    async def get_usage_totals(self, organization_id: int) -> Dict[str, int]:
        async with self.async_session() as session:
            result = await session.execute(
                select(
                    func.count(UsageRecordModel.id),
                    func.coalesce(func.sum(UsageRecordModel.duration_seconds), 0),
                    func.coalesce(func.sum(UsageRecordModel.amount_cents), 0),
                ).where(UsageRecordModel.organization_id == organization_id)
            )
            calls, duration, amount = result.one()
            return {
                "call_count": int(calls),
                "total_duration_seconds": int(duration),
                "total_amount_cents": int(amount),
            }
