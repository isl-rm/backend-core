import pytest
from httpx import AsyncClient

from app.modules.auth.service import AuthService


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
    refresh_cookie = response.cookies.get("refresh_token")
    assert refresh_cookie


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
        "/api/v1/refresh-token", json={"refresh_token": refresh_token}
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert response.cookies.get("refresh_token") == refresh_token


@pytest.mark.asyncio
async def test_refresh_token_invalid(client: AsyncClient):
    response = await client.post(
        "/api/v1/refresh-token", json={"refresh_token": "invalid_jwt"}
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
    assert data["email_verified"] is False
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
    delete_header = (logout_response.headers.get("set-cookie") or "").lower()
    assert "refresh_token=" in delete_header
    assert "max-age=0" in delete_header

    # Subsequent refresh call should fail due to missing cookie
    refresh_response = await client.post("/api/v1/refresh-token")
    assert refresh_response.status_code == 403
    assert refresh_response.json()["detail"] == "Refresh token missing"
