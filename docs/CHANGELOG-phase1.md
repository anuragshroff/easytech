# Phase 1 Changelog — Admin SPA & Platform Management

**Status:** released (commit `c248538`, 2026-10-14)
**Scope:** consolidate superadmin / platform management into the standalone admin SPA; add the `users.is_active` flag and enforce it; remove the Next.js superadmin pages.

## Backend

- **`users.is_active`** column added to `UserModel` (`api/db/models.py`) with migration `add_is_active_to_users`.
- **Disabled-account enforcement**: auth dependency now rejects inactive users (`api/services/auth/depends.py`, `api/routes/auth.py`).
- **`api/routes/superuser.py`** (new, `/superuser`, registered in `api/routes/main.py`):
  - `POST /impersonate`
  - `GET /workflow-runs`
  - `GET /stats`
  - `GET /users`, `POST /users/{user_id}/superuser`, `POST /users/{user_id}/active`
  - `GET /organizations`, `GET /organizations/{org_id}`
  - `GET /organizations/{org_id}/members`, `/workflows`, `/runs`
  - `GET /usage`, `GET /settings`
- **DB clients**: `api/db/organization_client.py` (list + detail), `api/db/organization_usage_client.py` (usage rollups), `api/db/user_client.py` (list / toggle superuser / toggle active).

## Admin SPA (`admin/`, Vite + React 18 + Tailwind v4)

- Pages: `Dashboard`, `Organizations`, `OrganizationDetail` (drill-down into members / workflows / runs), `Users` (with actions), `Usage`, `Settings`, plus `Layout` / `App` wiring.
- Plain `fetch` against the superuser endpoints; base path `/superadmin/`.

## Frontend (`ui/`)

- Removed the Next.js superadmin pages: `ui/src/app/superadmin/page.tsx`, `ui/src/app/superadmin/runs/page.tsx`.
- Updated the root redirect in `ui/src/app/page.tsx` to point at the SPA.

## Notes

- No automated tests added in this phase.
- This changelog covers work that is already committed; Phase 2 work is uncommitted (see `CHANGELOG-phase2.md`).
