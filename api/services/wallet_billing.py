"""Local wallet billing: pricing, pre-call guard, post-call settlement.

The wallet is a local ledger (``wallet_transactions`` + ``usage_records``) that
mirrors call usage and Stripe top-ups for the ``/billing`` dashboard. MPS stays
authoritative for credit gating, so the pre-call guard is *reporting-only* until
a platform admin flips ``enforce_pre_call_balance`` on the billing settings.
"""

from dataclasses import dataclass, field
from math import ceil
from typing import Any, List, Optional

from loguru import logger

from api.db import db_client
from api.enums import WorkflowRunMode

DEFAULT_RATE_CENTS_PER_MINUTE = 10
DEFAULT_MINIMUM_BALANCE_CENTS = 100


@dataclass
class EffectiveBillingSettings:
    rate_cents_per_minute: int = DEFAULT_RATE_CENTS_PER_MINUTE
    minimum_balance_cents: int = DEFAULT_MINIMUM_BALANCE_CENTS
    enforce_pre_call_balance: bool = False
    auto_recharge_enabled: bool = False
    auto_recharge_threshold_cents: int = 500
    auto_recharge_amount_cents: int = 2000
    payment_links: List[dict] = field(default_factory=list)


def _value(row: Any, name: str) -> Optional[Any]:
    if row is None:
        return None
    return getattr(row, name, None)


async def get_effective_settings(organization_id: Optional[int]) -> EffectiveBillingSettings:
    """Merge the per-org settings row over the platform default row."""
    platform = await db_client.get_platform_settings()
    org = (
        await db_client.get_org_settings(organization_id)
        if organization_id is not None
        else None
    )

    def pick(name: str, default: Any) -> Any:
        org_value = _value(org, name)
        if org_value is not None:
            return org_value
        platform_value = _value(platform, name)
        return default if platform_value is None else platform_value

    return EffectiveBillingSettings(
        rate_cents_per_minute=int(
            pick("rate_cents_per_minute", DEFAULT_RATE_CENTS_PER_MINUTE)
        ),
        minimum_balance_cents=int(
            pick("minimum_balance_cents", DEFAULT_MINIMUM_BALANCE_CENTS)
        ),
        enforce_pre_call_balance=bool(pick("enforce_pre_call_balance", False)),
        auto_recharge_enabled=bool(pick("auto_recharge_enabled", False)),
        auto_recharge_threshold_cents=int(
            pick("auto_recharge_threshold_cents", 500)
        ),
        auto_recharge_amount_cents=int(pick("auto_recharge_amount_cents", 2000)),
        payment_links=list(_value(platform, "payment_links") or []),
    )


def compute_charge_cents(duration_seconds: float, rate_cents_per_minute: int) -> int:
    """Charge in whole cents, rounded up so a partial minute still bills."""
    if duration_seconds <= 0 or rate_cents_per_minute <= 0:
        return 0
    return int(ceil(duration_seconds / 60.0 * rate_cents_per_minute))


def _duration_seconds(workflow_run: Any) -> Optional[float]:
    usage_info = getattr(workflow_run, "usage_info", None) or {}
    try:
        duration = float(usage_info.get("call_duration_seconds"))
    except (TypeError, ValueError):
        return None
    return duration if duration > 0 else None


async def check_pre_call_balance(
    organization_id: Optional[int],
) -> tuple[bool, EffectiveBillingSettings, int]:
    """Return ``(allowed, settings, balance_cents)``. Never raises.

    When enforcement is off (the default) this always allows the call and just
    reports the balance — the wallet is a mirror, MPS still gates.
    """
    if organization_id is None:
        return True, EffectiveBillingSettings(), 0
    try:
        settings = await get_effective_settings(organization_id)
        balance = await db_client.get_balance_cents(organization_id)
    except Exception as e:  # never block a call on a ledger read failure
        logger.warning(
            "Wallet guard: could not read balance for org {}: {}", organization_id, e
        )
        return True, EffectiveBillingSettings(), 0

    if not settings.enforce_pre_call_balance:
        return True, settings, balance
    return balance >= settings.minimum_balance_cents, settings, balance


async def settle_workflow_run_wallet(workflow_run_id: int) -> None:
    """Post-call settlement: record usage and debit the wallet, atomically.

    Idempotent: the unique ``workflow_run_id`` on both tables means a retry is a
    no-op.
    """
    workflow_run = await db_client.get_workflow_run_by_id(workflow_run_id)
    if not workflow_run:
        logger.warning("Wallet settle: workflow run {} not found", workflow_run_id)
        return

    if getattr(workflow_run, "mode", None) == WorkflowRunMode.TEXTCHAT.value:
        return

    workflow = getattr(workflow_run, "workflow", None)
    organization_id = getattr(workflow, "organization_id", None)
    if organization_id is None:
        logger.warning(
            "Wallet settle: no organization for run {}, skipping", workflow_run_id
        )
        return

    duration = _duration_seconds(workflow_run)
    if duration is None:
        logger.info(
            "Wallet settle: no billable duration for run {}, skipping", workflow_run_id
        )
        return

    settings = await get_effective_settings(organization_id)
    charge = compute_charge_cents(duration, settings.rate_cents_per_minute)
    result = await db_client.record_usage_and_debit(
        organization_id,
        workflow_run_id,
        duration_seconds=int(round(duration)),
        rate_cents_per_minute=settings.rate_cents_per_minute,
        amount_cents=charge,
    )
    if result is None:
        logger.info("Wallet settle: run {} already settled", workflow_run_id)
        return
    logger.info(
        "Wallet settle: run {} charged {} cents ({}s @ {}/min) for org {}",
        workflow_run_id,
        charge,
        int(round(duration)),
        settings.rate_cents_per_minute,
        organization_id,
    )
