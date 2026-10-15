"""Wallet / billing endpoints for the local ledger and Stripe top-ups.

Two classes of route live here:

* Org-scoped reads/updates (balance, transactions, usage, auto-recharge) guarded
  by ``get_user``.
* The unauthenticated Stripe webhook, verified by HMAC signature.

The wallet is a local mirror for the ``/billing`` dashboard. Pricing and the
pre-call guard are platform-level settings edited from the admin SPA; only
auto-recharge is self-service per org.
"""

import hashlib
import hmac
import json
import time
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from loguru import logger

from api.constants import STRIPE_WEBHOOK_SECRET, STRIPE_WEBHOOK_TOLERANCE_SECONDS
from api.db import db_client
from api.db.models import UserModel
from api.schemas.wallet_billing import (
    PaymentLinkResponse,
    UpdateWalletSettingsRequest,
    UsageRecordResponse,
    UsageRecordsResponse,
    WalletOverviewResponse,
    WalletSettingsResponse,
    WalletTotalsResponse,
    WalletTransactionResponse,
    WalletTransactionsResponse,
)
from api.services.auth.depends import get_user
from api.services.wallet_billing import get_effective_settings

router = APIRouter(prefix="/organizations", tags=["organizations"])


def _require_org(user: UserModel) -> int:
    if not user.selected_organization_id:
        raise HTTPException(status_code=400, detail="No organization selected")
    return user.selected_organization_id


def verify_stripe_signature(
    payload: bytes,
    header: Optional[str],
    secret: Optional[str],
    tolerance: int = 300,
) -> bool:
    """Verify a Stripe ``Stripe-Signature`` header per their v1 HMAC-SHA256 scheme.

    Implemented with the stdlib rather than the Stripe SDK: the algorithm is a
    documented, signed ``"{timestamp}.{payload}"`` HMAC compared in constant time.
    """
    if not header or not secret:
        return False

    values: dict[str, List[str]] = {}
    for item in header.split(","):
        if "=" not in item:
            continue
        key, value = item.split("=", 1)
        values.setdefault(key.strip(), []).append(value.strip())

    try:
        timestamp = int(values["t"][0])
    except (KeyError, IndexError, ValueError):
        return False

    if tolerance and abs(time.time() - timestamp) > tolerance:
        return False

    signed_payload = f"{timestamp}.".encode("utf-8") + payload
    expected = hmac.new(
        secret.encode("utf-8"), signed_payload, hashlib.sha256
    ).hexdigest()
    return any(
        hmac.compare_digest(expected, candidate) for candidate in values.get("v1", [])
    )


@router.get("/billing/wallet", response_model=WalletOverviewResponse)
async def get_wallet_overview(user: UserModel = Depends(get_user)):
    organization_id = _require_org(user)
    settings = await get_effective_settings(organization_id)
    balance_cents = await db_client.get_balance_cents(organization_id)
    totals = await db_client.get_usage_totals(organization_id)
    return WalletOverviewResponse(
        balance_cents=balance_cents,
        settings=WalletSettingsResponse(
            rate_cents_per_minute=settings.rate_cents_per_minute,
            minimum_balance_cents=settings.minimum_balance_cents,
            enforce_pre_call_balance=settings.enforce_pre_call_balance,
            auto_recharge_enabled=settings.auto_recharge_enabled,
            auto_recharge_threshold_cents=settings.auto_recharge_threshold_cents,
            auto_recharge_amount_cents=settings.auto_recharge_amount_cents,
        ),
        payment_links=[
            PaymentLinkResponse(**link)
            for link in settings.payment_links
            if isinstance(link, dict) and link.get("url")
        ],
        totals=WalletTotalsResponse(**totals),
    )


@router.get(
    "/billing/wallet/transactions", response_model=WalletTransactionsResponse
)
async def list_wallet_transactions(
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    user: UserModel = Depends(get_user),
):
    organization_id = _require_org(user)
    rows = await db_client.list_transactions(organization_id, limit=limit, offset=offset)
    return WalletTransactionsResponse(
        transactions=[WalletTransactionResponse.model_validate(r) for r in rows]
    )


@router.get("/billing/wallet/usage", response_model=UsageRecordsResponse)
async def list_wallet_usage(
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    user: UserModel = Depends(get_user),
):
    organization_id = _require_org(user)
    rows = await db_client.list_usage_records(
        organization_id, limit=limit, offset=offset
    )
    return UsageRecordsResponse(
        usage_records=[UsageRecordResponse.model_validate(r) for r in rows]
    )


@router.put("/billing/settings", response_model=WalletSettingsResponse)
async def update_wallet_settings(
    request: UpdateWalletSettingsRequest,
    user: UserModel = Depends(get_user),
):
    """Update the org's self-service wallet settings (auto-recharge only)."""
    organization_id = _require_org(user)
    fields = request.model_dump(exclude_none=True)
    if fields:
        await db_client.upsert_org_settings(organization_id, **fields)
    settings = await get_effective_settings(organization_id)
    return WalletSettingsResponse(
        rate_cents_per_minute=settings.rate_cents_per_minute,
        minimum_balance_cents=settings.minimum_balance_cents,
        enforce_pre_call_balance=settings.enforce_pre_call_balance,
        auto_recharge_enabled=settings.auto_recharge_enabled,
        auto_recharge_threshold_cents=settings.auto_recharge_threshold_cents,
        auto_recharge_amount_cents=settings.auto_recharge_amount_cents,
    )


@router.post("/billing/stripe/webhook")
async def stripe_webhook(request: Request):
    """Credit the wallet on a completed Stripe Payment Link checkout.

    The top-up link must append ``?client_reference_id=<organization_id>`` so the
    completed session names the org to credit.

    ponytail: Payment Links are static, so ``client_reference_id`` is buyer-
    supplied and anyone holding the link can name the org to credit. The amount
    still comes from Stripe (``amount_total``), so the exposure is misdirected
    credit, not forged credit. Move to server-created Checkout sessions if that
    becomes unacceptable.
    """
    payload = await request.body()
    header = request.headers.get("stripe-signature")
    if not verify_stripe_signature(
        payload, header, STRIPE_WEBHOOK_SECRET, STRIPE_WEBHOOK_TOLERANCE_SECONDS
    ):
        raise HTTPException(status_code=400, detail="Invalid Stripe signature")

    try:
        event = json.loads(payload)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid payload")

    if event.get("type") != "checkout.session.completed":
        return {"ok": True, "ignored": event.get("type")}

    session = (event.get("data") or {}).get("object") or {}
    if session.get("payment_status") != "paid":
        return {"ok": True, "ignored": "not_paid"}

    session_id = session.get("id")
    amount_total = session.get("amount_total")
    org_ref = session.get("client_reference_id")
    if not session_id or not isinstance(amount_total, int) or not org_ref:
        logger.warning(
            "Stripe webhook: incomplete checkout session {} (org={}, amount={})",
            session_id,
            org_ref,
            amount_total,
        )
        return {"ok": True, "ignored": "incomplete_session"}

    try:
        organization_id = int(org_ref)
    except (TypeError, ValueError):
        logger.warning("Stripe webhook: bad client_reference_id {!r}", org_ref)
        return {"ok": True, "ignored": "bad_org_ref"}

    row = await db_client.add_transaction(
        organization_id,
        amount_total,
        kind="topup",
        source="stripe",
        description=f"Stripe top-up {session_id}",
        external_ref=session_id,
    )
    if row is None:
        logger.info("Stripe webhook: session {} already applied", session_id)
    else:
        logger.info(
            "Stripe webhook: credited {} cents to org {} (session {})",
            amount_total,
            organization_id,
            session_id,
        )
    return {"ok": True}
