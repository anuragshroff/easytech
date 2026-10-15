# Phase 2 Changelog — EasyTech White-label, Tenant & Telephony Features

**Status:** uncommitted (working tree, 2026-10-15)
**Scope:** rebrand the product as **EasyTech**, adapt CI/CD to this fork, and ship multi-tenant / telephony capabilities: organization invitations, tenant context, a master-carrier seam, DID search + purchase, and the `/numbers` dashboard.

> Continues in `CHANGELOG-phase3.md` (self-hosted wallet & billing ledger).

## Branding (EasyTech)

- New assets: `ui/public/easytech-logo.svg`, `easytech-logo-inverse.svg`, `easytech-mark.svg`, `og-image.svg`, `ui/src/app/icon.svg`.
- Removed `ui/src/app/favicon.ico`; regenerated `ui/public/brand-imprint-light.svg` / `brand-imprint-dark.svg`.
- Updated `ui/src/app/globals.css` (brand tokens), `ui/src/app/layout.tsx`, `ui/src/components/BrandLogo.tsx`.
- Removed upstream links/branding from `AppLayout.tsx`, `AppSidebar.tsx`, `WorkflowEditorHeader.tsx`, `AuthShell.tsx`.

## CI/CD

- Deleted upstream-only workflows: `release-automation.yml`, `release-deployment.yml`, `slack-announcements.yml`.
- Removed the `notify-slack-failure` job from `api-tests.yml`.
- Kept `docker-image.yml`, `build-api-image.yml`, `pre-pr-drift-check.yml`, `pr-conventional-labeler.yml`.
- Migration rename: `a1b2c3d4e5f6_add_is_active_to_users.py` → `b1c2d3e4f5a6_add_is_active_to_users.py`.

## Feature: Organization invitations

- `OrganizationInvitationModel` (`api/db/models.py`) with partial unique index `uq_organization_invitations_pending`, plus `ix_organization_invitations_email_lower` and `ix_organization_invitations_org`; migration `c2d3e4f5a6b7_add_organization_invitations.py`.
- `api/db/organization_invitation_client.py`: `OrganizationInvitationClient`, `OrganizationInvitationConflictError`, `INVITATION_TTL_DAYS=14`, reuses `hash_api_key`, `raw_token = f"inv_{secrets.token_urlsafe(32)}"`.
- `api/schemas/organization_invitation.py` and `api/routes/organization_invitations.py` (`POST`/`GET /invitations`, `DELETE /invitations/{id}`, `POST /invitations/accept`), mounted in `api/routes/main.py`.
- **Signup**: `api/routes/auth.py::signup` checks `get_pending_invitations_for_email` first — joins the invited org — and otherwise provisions a fresh org.

## Feature: Tenant context

- `get_current_tenant_context` + `TenantContext` in `api/services/auth/depends.py`; returns 400 when no organization is selected.
- `TenantContext.user` is typed `Any` with `ConfigDict(arbitrary_types_allowed=True)`.

## Feature: Master carrier seam

- `api/services/carrier_service.py` (opt-in, **not wired**): `MASTER_CARRIER_ENV`, `get_master_carrier_credentials`, `is_master_carrier_configured`, `build_master_provider`, plus `python -m api.services.carrier_service` self-check.

## Feature: DID search + purchase

- `api/services/telephony/base.py`: `AvailablePhoneNumber` dataclass + `search_available_numbers(...)` (default `NotImplementedError`).
- Twilio provider: `search_available_numbers` (`GET .../AvailablePhoneNumbers/{ISO}/Local.json`) and idempotent `provision_phone_number` (`POST .../IncomingPhoneNumbers.json`).
- Telnyx provider: `search_available_numbers` (`GET /v2/available_phone_numbers`) and idempotent `provision_phone_number` (`POST /v2/number_orders`).
- `api/schemas/telephony_phone_number.py`: `AvailablePhoneNumberResponse`, `PhoneNumberSearchResponse`.
- Route `GET /telephony-configs/{config_id}/phone-numbers/search` in `api/routes/organization.py` (declared before `/{phone_number_id}`); maps `NotImplementedError` → 400, `ProviderPhoneNumberLookupError` → 502, `ValueError` → 400.

## Feature: `/numbers` dashboard (UI)

- New `ui/src/app/numbers/page.tsx`: org-wide numbers view with config filter, DID search dialog, one-click buy, and one-click agent assignment (`inbound_workflow_id` / `clear_inbound_workflow`).
- Nav entry added in `ui/src/components/layout/AppSidebar.tsx`.
- Regenerated `ui/src/client` from the OpenAPI spec (adds the search endpoint and response types).

## Tests

- New `api/tests/telephony/test_number_search.py`: Twilio/Telnyx search + idempotent provision, credential errors, and route mapping.
- `api/tests/test_auth_routes.py`: signup invite-join vs. new-org provisioning.
- `api/tests/test_auth_depends.py`: tenant-context resolution via a dependency-override app.
- Combined run (`test_auth_routes.py`, `test_auth_depends.py`, `api/tests/telephony/`): **486 passed**.

## Known gaps

- Invitation email delivery is a no-op (`_deliver_invitation`); the raw token is returned in the response and logged.
- `carrier_service.py` is a seam only — buying on the master account and binding the inbound webhook on it is follow-up work.
- No real Twilio/Telnyx credentials were available to verify search/purchase end to end.
