"""Tests for the local wallet ledger, pre-call guard, and Stripe webhook."""

import hashlib
import hmac
import json
import time
import uuid

import pytest

from api.db.models import OrganizationModel, UserModel
from api.enums import WorkflowRunMode
from api.routes.organization_billing import verify_stripe_signature
from api.services.wallet_billing import compute_charge_cents, get_effective_settings


def test_compute_charge_cents_rounds_up():
    assert compute_charge_cents(0, 10) == 0
    assert compute_charge_cents(10, 10) == 2  # partial minute still bills
    assert compute_charge_cents(60, 10) == 10
    assert compute_charge_cents(61, 10) == 11
    assert compute_charge_cents(150, 12) == 30


def _sign(payload: bytes, secret: str, timestamp: int) -> str:
    signed = f"{timestamp}.".encode("utf-8") + payload
    digest = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()
    return f"t={timestamp},v1={digest}"


def test_verify_stripe_signature():
    secret = "whsec_test"
    payload = b'{"type":"checkout.session.completed"}'
    now = int(time.time())

    assert verify_stripe_signature(payload, _sign(payload, secret, now), secret)
    # tampered payload
    assert not verify_stripe_signature(payload + b"x", _sign(payload, secret, now), secret)
    # wrong secret
    assert not verify_stripe_signature(payload, _sign(payload, "other", now), secret)
    # expired
    assert not verify_stripe_signature(
        payload, _sign(payload, secret, now - 10_000), secret, tolerance=300
    )
    # missing pieces
    assert not verify_stripe_signature(payload, None, secret)
    assert not verify_stripe_signature(payload, _sign(payload, secret, now), None)
    assert not verify_stripe_signature(payload, "garbage", secret)
    # one valid v1 among several still passes
    assert verify_stripe_signature(
        payload, f"t={now},v1=deadbeef,{_sign(payload, secret, now)}", secret
    )


async def _make_org(async_session):
    suffix = uuid.uuid4().hex
    org = OrganizationModel(provider_id=f"wallet-org-{suffix}")
    async_session.add(org)
    await async_session.flush()
    user = UserModel(
        provider_id=f"wallet-user-{suffix}",
        selected_organization_id=org.id,
    )
    async_session.add(user)
    await async_session.flush()
    # Return plain ids: later commits/rollbacks expire the ORM instances, and
    # touching an expired attribute outside the greenlet raises MissingGreenlet.
    return org.id, user.id


@pytest.mark.asyncio
async def test_settings_merge_org_over_platform(db_session, async_session):
    org_id, _ = await _make_org(async_session)

    effective = await get_effective_settings(org_id)
    assert effective.rate_cents_per_minute == 10  # built-in default

    await db_session.upsert_platform_settings(
        rate_cents_per_minute=25, minimum_balance_cents=500
    )
    effective = await get_effective_settings(org_id)
    assert effective.rate_cents_per_minute == 25
    assert effective.minimum_balance_cents == 500

    await db_session.upsert_org_settings(org_id, rate_cents_per_minute=40)
    effective = await get_effective_settings(org_id)
    assert effective.rate_cents_per_minute == 40  # org wins
    assert effective.minimum_balance_cents == 500  # platform still applies


@pytest.mark.asyncio
async def test_topup_idempotency_and_balance(db_session, async_session):
    org_id, _ = await _make_org(async_session)
    assert await db_session.get_balance_cents(org_id) == 0

    first = await db_session.add_transaction(
        org_id, 2000, kind="topup", source="stripe", external_ref="evt_same"
    )
    assert first is not None
    dup = await db_session.add_transaction(
        org_id, 2000, kind="topup", source="stripe", external_ref="evt_same"
    )
    assert dup is None
    assert await db_session.get_balance_cents(org_id) == 2000


@pytest.mark.asyncio
async def test_record_usage_and_debit_is_idempotent(db_session, async_session):
    org_id, user_id = await _make_org(async_session)
    await db_session.add_transaction(org_id, 10000, kind="topup", source="manual")

    workflow = await db_session.create_workflow(
        name="Wallet test",
        workflow_definition={},
        user_id=user_id,
        organization_id=org_id,
    )
    run = await db_session.create_workflow_run(
        name="Wallet run",
        workflow_id=workflow.id,
        mode=WorkflowRunMode.SMALLWEBRTC.value,
        user_id=user_id,
        organization_id=org_id,
    )
    run_id = run.id

    first = await db_session.record_usage_and_debit(
        org_id, run_id, duration_seconds=65, rate_cents_per_minute=10, amount_cents=11
    )
    assert first is not None
    retry = await db_session.record_usage_and_debit(
        org_id, run_id, duration_seconds=65, rate_cents_per_minute=10, amount_cents=11
    )
    assert retry is None

    assert await db_session.has_usage_record(run_id)
    assert await db_session.get_balance_cents(org_id) == 10000 - 11
    totals = await db_session.get_usage_totals(org_id)
    assert totals["call_count"] == 1
    assert totals["total_amount_cents"] == 11


@pytest.mark.asyncio
async def test_stripe_webhook_credits_wallet(test_client_factory, db_session, async_session):
    org_id, user_id = await _make_org(async_session)
    user = await async_session.get(UserModel, user_id)

    payload = json.dumps(
        {
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_test_1",
                    "payment_status": "paid",
                    "amount_total": 5000,
                    "client_reference_id": str(org_id),
                }
            },
        }
    ).encode()

    secret = "whsec_test"
    from api.routes import organization_billing

    original = organization_billing.STRIPE_WEBHOOK_SECRET
    organization_billing.STRIPE_WEBHOOK_SECRET = secret
    try:
        async with test_client_factory(user) as client:
            bad = await client.post(
                "/api/v1/organizations/billing/stripe/webhook",
                content=payload,
                headers={"stripe-signature": "t=1,v1=nope"},
            )
            assert bad.status_code == 400

            ok = await client.post(
                "/api/v1/organizations/billing/stripe/webhook",
                content=payload,
                headers={
                    "stripe-signature": _sign(payload, secret, int(time.time()))
                },
            )
            assert ok.status_code == 200

            # replay is idempotent
            again = await client.post(
                "/api/v1/organizations/billing/stripe/webhook",
                content=payload,
                headers={
                    "stripe-signature": _sign(payload, secret, int(time.time()))
                },
            )
            assert again.status_code == 200
    finally:
        organization_billing.STRIPE_WEBHOOK_SECRET = original

    assert await db_session.get_balance_cents(org_id) == 5000
