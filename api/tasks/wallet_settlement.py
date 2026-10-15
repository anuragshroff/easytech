"""ARQ task: settle a completed run against the local wallet ledger."""

from loguru import logger

from api.services.wallet_billing import settle_workflow_run_wallet


async def settle_wallet_for_workflow_run(_ctx, workflow_run_id: int) -> None:
    """Record usage + wallet debit for a completed run. Safe to retry."""
    try:
        await settle_workflow_run_wallet(workflow_run_id)
    except Exception as e:
        logger.error(
            "Error settling wallet for workflow run {}: {}", workflow_run_id, e
        )
