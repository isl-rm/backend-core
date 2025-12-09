import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_login_access_token(client: AsyncClient, create_user_func):
    password = "password123"
    user = await create_user_func(password=password)

    response = await client.post(
        "/api/v1/login/access-token",
        data={"username": user.email, "password": password},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_access_token_failed(client: AsyncClient):
    response = await client.post(
        "/api/v1/login/access-token",
        data={"username": "wrong@email.com", "password": "wrong"},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Incorrect email or password"


@pytest.mark.asyncio
async def test_refresh_token(client: AsyncClient, create_user_func):
    # Need a valid refresh token. We can use the one from login or generate one.
    from app.modules.auth.service import AuthService

    auth_service = AuthService()
    refresh_token = auth_service.create_refresh_token("valid_sub")

    response = await client.post(
        "/api/v1/refresh-token", json={"refresh_token": refresh_token}
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["refresh_token"] == refresh_token  # Router echoes it back for now


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
        "roles": ["USER"],  # Optional
    }
    response = await client.post("/api/v1/signup", json=payload)
    if response.status_code != 201:
        print(f"DEBUG: {response.text}")
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == payload["email"]
    assert "id" in data
    assert "hashed_password" not in data


@pytest.mark.asyncio
async def test_signup_duplicate_email(client: AsyncClient, create_user_func):
    await create_user_func(email="existing@example.com")

    payload = {"email": "existing@example.com", "password": "password"}
    response = await client.post("/api/v1/signup", json=payload)
    assert response.status_code == 400
    assert "already exists" in response.json()["detail"]
