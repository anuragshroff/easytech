# Phase 3 Changelog — Self-hosted Wallet & Billing Ledger

**Status:** uncommitted (working tree, 2026-10-15)
**Scope:** add a local wallet/billing ledger to the self-hosted app — usage records and wallet
transactions, an optional pre-call balance guard, post-call settlement, admin-editable pricing,
Stripe Payment Link top-ups with a signed webhook, an admin billing page, and a wallet panel on
the `/billing` dashboard.

**Design:** the platform (MPS) stays authoritative for gating hosted deployments. The wallet is a
local mirror for self-hosted operators: it records usage, mirrors balances, and credits local
top-ups. Enforcement defaults to off and is toggleable by a platform admin.

## Data model & migration

- New models in `api/db/models.py`: `BillingSettingsModel`, `WalletTransactionModel`,
  `UsageRecordModel`.
- `BillingSettingsModel` holds a platform default row (`organization_id IS NULL`) plus optional
  per-org override rows whose unset columns stay `NULL` so they inherit the platform value.
- All pricing/config columns are **nullable** (no `server_default`) — a partial override row must
  fall through to the platform row. (Original migration had `NOT NULL` defaults, which masked the
  org-over-platform merge; fixed in place before landing.)
- Migration `d3e4f5a6b7c8_add_wallet_billing.py` (adds both tables; applied to dev DB, single head).

## Wallet client (`api/db/wallet_client.py`)

- `WalletClient` on `db_client`: `get_platform_settings`, `get_org_settings`, `upsert_platform_settings`,
  `upsert_org_settings`, `get_balance_cents`, `add_transaction`, `list_transactions`,
  `record_usage_and_debit`, `has_usage_record`, `list_usage_records`, `get_usage_totals`.
- Idempotency via PostgreSQL `pg_insert(...).on_conflict_do_nothing().returning(...)`
  (no `index_elements` — partial unique indexes require predicate inference). Avoids
  `IntegrityError`/session-poisoning on replayed events.
- Money is integer cents everywhere; never floats.

## Billing service (`api/services/wallet_billing.py`)

- `get_effective_settings(organization_id)` — org-over-platform-over-built-in-defaults merge.
- `compute_charge_cents(duration_seconds, rate_cents_per_minute)` — ceils to the cent.
- `check_pre_call_balance(organization_id)` — reporting-only unless the platform enables
  enforcement; returns `(allowed, settings, balance_cents)`.
- `settle_workflow_run_wallet(workflow_run_id)` — post-call settlement (idempotent via the client).

## Pre-call guard & settlement

- `authorize_workflow_run_start` (`api/services/quota_service.py`) is the single dispatch chokepoint;
  the wallet guard is placed there once. When enforcement is on and the balance is below the
  minimum, returns `has_quota=False`, `error_code="insufficient_balance"`, status **402**.
- `api/tasks/wallet_settlement.py` (`settle_wallet_for_workflow_run`) added to the ARQ worker
  (`api/tasks/arq.py`, `function_names.py`) and enqueued from `workflow_completion.py`.

## API routes

- `api/routes/organization_billing.py` (mounted in `api/routes/main.py`):
  - `GET /organizations/billing/wallet` → `WalletOverviewResponse` (balance, effective settings,
    payment links, usage totals).
  - `GET /organizations/billing/wallet/transactions` (limit/offset).
  - `GET /organizations/billing/wallet/usage` (limit/offset).
  - `PUT /organizations/billing/settings` — org self-service (auto-recharge only).
  - `POST /organizations/billing/stripe/webhook` — unauthenticated; verifies signature, handles
    `checkout.session.completed` + `payment_status=="paid"`, credits the org wallet idempotently,
    always returns 200 except a bad signature (400).
  - `verify_stripe_signature(payload, header, secret, tolerance=300)` — stdlib HMAC-SHA256,
    `t=`/`v1=` parsing, constant-time compare, timestamp tolerance.
- `api/routes/superuser.py`: `GET`/`PUT /superuser/billing/settings` for platform pricing, payment
  links, and the enforcement toggle (admin SPA).
- `api/constants.py`: `STRIPE_WEBHOOK_SECRET`, `STRIPE_WEBHOOK_TOLERANCE_SECONDS` (default 300).

## UI

- `ui/src/app/billing/WalletPanel.tsx` (new) — balance, rate, all-time usage totals, top-up Payment
  Link buttons, auto-recharge controls (PUT settings), recent transactions, and usage history;
  included in `ui/src/app/billing/page.tsx`.
- Regenerated `ui/src/client` from the OpenAPI spec (wallet endpoints + response types).
- Admin SPA: `admin/src/Billing.jsx` (pricing, enforcement toggle, editable payment-link list),
  routed at `/billing` in `admin/src/App.jsx` and linked in `admin/src/Layout.jsx`.

## Tests

- New `api/tests/test_wallet_billing.py` (6): `compute_charge_cents` ceil, `verify_stripe_signature`
  (valid / tampered / wrong secret / expired / missing / multi-`v1`), org-over-platform settings
  merge, top-up idempotency + balance, `record_usage_and_debit` idempotency, Stripe webhook credits
  the wallet and replay is idempotent.
- Combined run (`test_wallet_billing.py`, `test_quota_service.py`, `test_auth_depends.py`,
  `api/tests/telephony/test_number_search.py`): **63 passed**.
- Admin SPA `vite build` passes; `ui` `tsc --maxNodeModuleJsDepth 0` + eslint clean.

## Known gaps

- "Stripe top-ups feed MPS" has no MPS credit API to call — top-ups credit the local ledger only.
- No live Stripe keys; the `stripe` package is not installed (stdlib HMAC is used). Webhook
  signature and behavior are verified by unit + TestClient tests, not a live Stripe delivery.
- Payment Links are static, so `client_reference_id=<organization_id>` is buyer-supplied; the amount
  still comes from Stripe, so the exposure is misdirected credit, not forged credit.
