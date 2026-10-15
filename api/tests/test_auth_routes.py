from types import SimpleNamespace
from unittest.mock import AsyncMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

import api.routes.auth as auth_routes
from api.routes.auth import router
from api.services.auth import depends as auth_depends
from api.services.auth.depends import get_user


def _make_test_app() -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    return app


def test_stack_mode_hides_email_password_auth_routes(monkeypatch):
    monkeypatch.setattr(auth_depends, "AUTH_PROVIDER", "stack")
    client = TestClient(_make_test_app())

    signup_response = client.post(
        "/auth/signup",
        json={
            "email": "user@example.com",
            "password": "password123",
            "name": "User",
        },
    )
    login_response = client.post(
        "/auth/login",
        json={
            "email": "user@example.com",
            "password": "password123",
        },
    )

    assert signup_response.status_code == 404
    assert signup_response.json() == {"detail": "Not found"}
    assert login_response.status_code == 404
    assert login_response.json() == {"detail": "Not found"}


def test_signup_disabled_returns_403(monkeypatch):
    monkeypatch.setattr(auth_routes, "ENABLE_SIGNUP", False)
    client = TestClient(_make_test_app())

    response = client.post(
        "/auth/signup",
        json={
            "email": "user@example.com",
            "password": "password123",
            "name": "User",
        },
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "Signup is disabled"}


def test_stack_mode_keeps_current_user_route_available(monkeypatch):
    monkeypatch.setattr(auth_depends, "AUTH_PROVIDER", "stack")
    app = _make_test_app()
    app.dependency_overrides[get_user] = lambda: SimpleNamespace(
        id=7,
        email="user@example.com",
        selected_organization_id=42,
        provider_id="stack-user-1",
    )
    client = TestClient(app)

    response = client.get("/auth/me")

    assert response.status_code == 200
    assert response.json() == {
        "id": 7,
        "email": "user@example.com",
        "name": None,
        "organization_id": 42,
        "provider_id": "stack-user-1",
    }


def _stub_signup_deps(monkeypatch, *, invitations, calls):
    """Wire the signup route's dependencies onto a spy-recording db_client.

    ``calls`` collects (method_name, args, kwargs) so a test can assert which
    provisioning path ran (invite-join vs. fresh org).
    """
    monkeypatch.setattr(auth_depends, "AUTH_PROVIDER", "local")
    monkeypatch.setattr(auth_routes, "ENABLE_SIGNUP", True)
    monkeypatch.setattr(auth_routes, "hash_password", lambda pw: "hashed")
    monkeypatch.setattr(auth_routes, "create_jwt_token", lambda *a, **k: "jwt")
    monkeypatch.setattr(auth_routes, "capture_event", lambda *a, **k: None)
    monkeypatch.setattr(
        auth_routes, "ensure_organization_bootstrapped", AsyncMock(return_value=True)
    )

    def _record(name, result=None):
        async def _fn(*args, **kwargs):
            calls.append((name, args, kwargs))
            return result

        return _fn

    user = SimpleNamespace(
        id=7, provider_id="oss-user-1", email="invitee@example.com"
    )
    monkeypatch.setattr(
        auth_routes.db_client, "get_user_by_email", _record("get_user_by_email", None)
    )
    monkeypatch.setattr(
        auth_routes.db_client,
        "create_user_with_email",
        _record("create_user_with_email", user),
    )
    monkeypatch.setattr(
        auth_routes.db_client,
        "get_pending_invitations_for_email",
        _record("get_pending_invitations_for_email", invitations),
    )
    monkeypatch.setattr(
        auth_routes.db_client,
        "get_organization_by_id",
        _record("get_organization_by_id", SimpleNamespace(id=99, provider_id="team-9")),
    )
    monkeypatch.setattr(
        auth_routes.db_client,
        "get_or_create_organization_by_provider_id",
        _record(
            "get_or_create_organization_by_provider_id",
            (SimpleNamespace(id=7, provider_id="org_oss-user-1"), True),
        ),
    )
    monkeypatch.setattr(
        auth_routes.db_client, "add_user_to_organization", _record("add_user_to_organization")
    )
    monkeypatch.setattr(
        auth_routes.db_client,
        "update_user_selected_organization",
        _record("update_user_selected_organization"),
    )
    monkeypatch.setattr(
        auth_routes.db_client, "accept_invitation", _record("accept_invitation")
    )


def test_signup_joins_organization_from_pending_invitation(monkeypatch):
    calls = []
    invitation = SimpleNamespace(id=5, organization_id=99)
    _stub_signup_deps(monkeypatch, invitations=[invitation], calls=calls)
    client = TestClient(_make_test_app())

    response = client.post(
        "/auth/signup",
        json={"email": "invitee@example.com", "password": "password123", "name": "U"},
    )

    assert response.status_code == 200
    # Joined the inviting org, not a freshly provisioned one.
    assert response.json()["user"]["organization_id"] == 99
    ran = [name for name, _, _ in calls]
    assert "get_or_create_organization_by_provider_id" not in ran
    assert "accept_invitation" in ran
    add_call = next(c for c in calls if c[0] == "add_user_to_organization")
    assert add_call[1] == (7, 99)


def test_signup_provisions_new_org_without_invitation(monkeypatch):
    calls = []
    _stub_signup_deps(monkeypatch, invitations=[], calls=calls)
    client = TestClient(_make_test_app())

    response = client.post(
        "/auth/signup",
        json={"email": "new@example.com", "password": "password123", "name": "U"},
    )

    assert response.status_code == 200
    assert response.json()["user"]["organization_id"] == 7
    ran = [name for name, _, _ in calls]
    assert "get_or_create_organization_by_provider_id" in ran
    assert "accept_invitation" not in ran
