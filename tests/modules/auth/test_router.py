from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import Response
from httpx import AsyncClient

from app.main import app
from app.modules.auth.router import _clear_refresh_cookie, _set_refresh_cookie
from app.modules.auth.service import AuthService
from app.modules.users.service import UserService
from app.shared.constants import Role, UserStatus


def _get_set_cookie_headers(response) -> list[str]:
    return [value.lower() for value in response.headers.get_list("set-cookie")]


@pytest.mark.asyncio
async def test_login_access_token_sets_refresh_cookie(
    client: AsyncClient, create_user_func
):
    password = "password123"
    user = await create_user_func(password=password)

    response = await client.post(
        "/api/v1/login/access-token",
        data={"email": user.email, "password": password},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["roles"] == [Role.USER]
    refresh_cookie = response.cookies.get("refresh_token")
    assert refresh_cookie


@pytest.mark.asyncio
async def test_login_accepts_username_field_for_swagger(
    client: AsyncClient, create_user_func
):
    password = "password123"
    user = await create_user_func(password=password)

    response = await client.post(
        "/api/v1/login/access-token",
        data={"username": user.email, "password": password},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["roles"] == [Role.USER]


@pytest.mark.asyncio
async def test_login_cookie_sets_auth_cookies_and_returns_profile(
    client: AsyncClient, create_user_func
):
    password = "password123"
    user = await create_user_func(password=password, profile={"name": "Cookie User"})

    response = await client.post(
        "/api/v1/login/cookie",
        data={"email": user.email, "password": password},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == user.email
    assert data["name"] == "Cookie User"
    assert data["roles"] == [Role.USER]
    assert response.cookies.get("access_token")
    assert response.cookies.get("refresh_token")


@pytest.mark.asyncio
async def test_login_access_token_failed(client: AsyncClient):
    response = await client.post(
        "/api/v1/login/access-token",
        data={"email": "wrong@email.com", "password": "wrong"},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Incorrect email or password"


@pytest.mark.asyncio
async def test_refresh_token_uses_cookie_flow(
    client: AsyncClient, create_user_func
):
    password = "password123"
    user = await create_user_func(password=password)
    login_response = await client.post(
        "/api/v1/login/access-token",
        data={"email": user.email, "password": password},
    )
    assert login_response.status_code == 200
    refresh_cookie = login_response.cookies.get("refresh_token")
    assert refresh_cookie

    refresh_response = await client.post("/api/v1/refresh-token")
    assert refresh_response.status_code == 200
    data = refresh_response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    # refresh token is re-set on the response to keep the session alive
    assert refresh_response.cookies.get("refresh_token") == refresh_cookie


@pytest.mark.asyncio
async def test_refresh_token_via_body(client: AsyncClient, create_user_func):
    user = await create_user_func()
    auth_service = AuthService()
    refresh_token = auth_service.create_refresh_token(str(user.id))

    response = await client.post(
        "/api/v1/refresh-token", json={"refreshToken": refresh_token}
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert response.cookies.get("refresh_token") == refresh_token


@pytest.mark.asyncio
async def test_refresh_token_invalid(client: AsyncClient):
    response = await client.post(
        "/api/v1/refresh-token", json={"refreshToken": "invalid_jwt"}
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Invalid refresh token"


@pytest.mark.asyncio
async def test_signup_success(client: AsyncClient):
    payload = {
        "email": "newuser@example.com",
        "password": "strongpassword",
        "roles": ["USER"],
    }
    response = await client.post("/api/v1/signup", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == payload["email"]
    assert data["roles"] == payload["roles"]
    assert data["status"] == "active"
    assert data["emailVerified"] is False
    assert "id" in data
    assert "hashed_password" not in data


@pytest.mark.asyncio
async def test_signup_rejects_admin_role(client: AsyncClient):
    payload = {
        "email": "noadmin@example.com",
        "password": "strongpassword",
        "roles": ["ADMIN"],
    }
    response = await client.post("/api/v1/signup", json=payload)
    assert response.status_code == 422
    assert "Cannot assign ADMIN role during signup" in response.text


@pytest.mark.asyncio
async def test_signup_duplicate_email(client: AsyncClient, create_user_func):
    await create_user_func(email="existing@example.com")

    payload = {"email": "existing@example.com", "password": "password123"}
    response = await client.post("/api/v1/signup", json=payload)
    assert response.status_code == 400
    assert "already exists" in response.json()["detail"]


@pytest.mark.asyncio
async def test_refresh_token_missing_returns_403(client: AsyncClient):
    response = await client.post("/api/v1/refresh-token")
    assert response.status_code == 403
    assert response.json()["detail"] == "Refresh token missing"


@pytest.mark.asyncio
async def test_refresh_cookie_attributes(client: AsyncClient, create_user_func):
    password = "password123"
    user = await create_user_func(password=password)

    login_response = await client.post(
        "/api/v1/login/access-token",
        data={"email": user.email, "password": password},
    )
    assert login_response.status_code == 200
    header = (login_response.headers.get("set-cookie") or "").lower()
    assert "samesite=lax" in header
    assert "httponly" in header
    assert "secure" not in header  # default ENVIRONMENT=local


@pytest.mark.asyncio
async def test_logout_clears_refresh_cookie(client: AsyncClient, create_user_func):
    password = "password123"
    user = await create_user_func(password=password)

    login_response = await client.post(
        "/api/v1/login/access-token",
        data={"email": user.email, "password": password},
    )
    assert login_response.status_code == 200
    assert login_response.cookies.get("refresh_token")

    logout_response = await client.post("/api/v1/logout")
    assert logout_response.status_code == 204
    # httpx CookieJar should drop the cookie; header should indicate deletion
    delete_headers = _get_set_cookie_headers(logout_response)
    assert any("refresh_token=" in h for h in delete_headers)
    assert any("access_token=" in h for h in delete_headers)
    assert any("max-age=0" in h for h in delete_headers)

    # Subsequent refresh call should fail due to missing cookie
    refresh_response = await client.post("/api/v1/refresh-token")
    assert refresh_response.status_code == 403
    assert refresh_response.json()["detail"] == "Refresh token missing"


def test_login_cookie_helpers_set_and_clear_headers():
    response = Response()

    _set_refresh_cookie(response, "token123")
    set_cookie_headers = [
        value.decode().lower()
        for header, value in response.raw_headers
        if header.decode().lower() == "set-cookie"
    ]
    assert any("refresh_token=token123" in h for h in set_cookie_headers)
    assert any("httponly" in h for h in set_cookie_headers)
    assert any("max-age=" in h for h in set_cookie_headers)

    _clear_refresh_cookie(response)
    clear_headers = [
        value.decode().lower()
        for header, value in response.raw_headers
        if header.decode().lower() == "set-cookie"
    ]
    assert any("max-age=0" in h for h in clear_headers)


@pytest.mark.asyncio
async def test_login_refresh_flow_runs_with_cookie(client: AsyncClient, create_user_func):
    password = "password123"
    user = await create_user_func(password=password)

    login_response = await client.post(
        "/api/v1/login/access-token",
        data={"email": user.email, "password": password},
    )
    assert login_response.status_code == 200
    assert login_response.cookies.get("refresh_token")

    refresh_response = await client.post("/api/v1/refresh-token")
    assert refresh_response.status_code == 200
    assert refresh_response.json()["token_type"] == "bearer"
    assert refresh_response.cookies.get("refresh_token")


@pytest.mark.asyncio
async def test_login_logout_flow_clears_cookie(client: AsyncClient, create_user_func):
    password = "password123"
    user = await create_user_func(password=password)

    login_response = await client.post(
        "/api/v1/login/access-token",
        data={"email": user.email, "password": password},
    )
    assert login_response.cookies.get("refresh_token")

    logout_response = await client.post("/api/v1/logout")
    assert logout_response.status_code == 204
    clear_headers = _get_set_cookie_headers(logout_response)
    assert any("refresh_token=" in h for h in clear_headers)
    assert any("access_token=" in h for h in clear_headers)
    assert any("max-age=0" in h for h in clear_headers)


@pytest.mark.asyncio
async def test_login_access_token_with_override_sets_tokens(client: AsyncClient):
    class FakeAuthService:
        def __init__(self) -> None:
            self.created_tokens: list[tuple[str, str]] = []

        async def authenticate(self, email: str, password: str) -> SimpleNamespace:
            return SimpleNamespace(id="user123", roles=[Role.USER])

        def create_access_token(self, sub: str) -> str:
            self.created_tokens.append(("access", sub))
            return f"access-{sub}"

        def create_refresh_token(self, sub: str) -> str:
            self.created_tokens.append(("refresh", sub))
            return f"refresh-{sub}"

    fake_auth = FakeAuthService()
    app.dependency_overrides[AuthService] = lambda: fake_auth
    try:
        response = await client.post(
            "/api/v1/login/access-token",
            data={"email": "u@example.com", "password": "pw"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["access_token"] == "access-user123"
    assert response.json()["roles"] == [Role.USER]
    assert response.cookies.get("refresh_token") == "refresh-user123"
    assert ("access", "user123") in fake_auth.created_tokens
    assert ("refresh", "user123") in fake_auth.created_tokens


@pytest.mark.asyncio
async def test_refresh_token_prefers_body_over_cookie(client: AsyncClient):
    class FakeAuthService:
        def __init__(self) -> None:
            self.last_token = None

        async def get_refresh_token_payload(self, token: str) -> str:
            self.last_token = token
            return "user456"

        def create_access_token(self, sub: str) -> str:
            return f"new-access-{sub}"

    fake_auth = FakeAuthService()
    app.dependency_overrides[AuthService] = lambda: fake_auth
    try:
        client.cookies.set("refresh_token", "cookietoken", domain="test", path="/")
        response = await client.post(
            "/api/v1/refresh-token",
            json={"refreshToken": "bodytoken"},
        )
    finally:
        app.dependency_overrides.clear()
        client.cookies.clear()

    assert response.status_code == 200
    assert response.json()["access_token"] == "new-access-user456"
    assert response.cookies.get("refresh_token") == "bodytoken"
    assert fake_auth.last_token == "bodytoken"


@pytest.mark.asyncio
async def test_signup_success_with_override(client: AsyncClient):
    class FakeUserService:
        def __init__(self) -> None:
            self.created_input = None
            self.queried_email = None

        async def get_by_email(self, email: str) -> None:
            self.queried_email = email
            return None

        async def create(self, user_in):
            self.created_input = user_in
            return SimpleNamespace(
                id="stub-user",
                email=user_in.email,
                roles=user_in.roles,
                status=UserStatus.ACTIVE,
                email_verified=False,
                created_at=datetime.now(timezone.utc),
                last_login_at=None,
                profile=user_in.profile,
            )

    fake_user_service = FakeUserService()
    app.dependency_overrides[UserService] = lambda: fake_user_service
    try:
        response = await client.post(
            "/api/v1/signup",
            json={"email": "override@example.com", "password": "strongpassword"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "override@example.com"
    assert data["roles"] == [Role.USER]
    assert fake_user_service.queried_email == "override@example.com"
    assert fake_user_service.created_input.email == "override@example.com"
