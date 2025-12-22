from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException, Response

from app.modules.auth.router import (
    create_user,
    login_access_token,
    login_cookie,
    logout,
    refresh_token,
)
from app.modules.auth.schemas import EmailPasswordForm, RefreshTokenBody
from app.modules.users.schemas import UserCreate
from app.shared.constants import Role, UserStatus


@pytest.mark.asyncio
async def test_login_access_token_unit():
    class FakeAuthService:
        async def authenticate(self, email: str, password: str):
            return SimpleNamespace(id="user123", roles=[Role.USER])

        def create_access_token(self, sub: str) -> str:
            return f"access-{sub}"

        def create_refresh_token(self, sub: str) -> str:
            return f"refresh-{sub}"

    response = Response()
    form = EmailPasswordForm(email="u@example.com", password="pw")
    result = await login_access_token(
        response, form_data=form, auth_service=FakeAuthService()
    )

    assert result["access_token"] == "access-user123"
    assert result["roles"] == [Role.USER]
    assert "refresh_token=refresh-user123" in (
        response.headers.get("set-cookie") or ""
    ).lower()


@pytest.mark.asyncio
async def test_refresh_token_body_and_cookie_paths():
    class FakeAuthService:
        def __init__(self) -> None:
            self.seen_tokens: list[str] = []

        async def get_refresh_token_payload(self, token: str) -> str | None:
            self.seen_tokens.append(token)
            return "user456"

        def create_access_token(self, sub: str) -> str:
            return f"new-access-{sub}"

    # Body should win over cookie
    response = Response()
    auth = FakeAuthService()
    result = await refresh_token(
        response,
        refresh_token_body=RefreshTokenBody(refresh_token="body-token"),
        refresh_token_cookie="cookie-token",
        auth_service=auth,
    )
    assert result["access_token"] == "new-access-user456"
    assert auth.seen_tokens == ["body-token"]
    headers = [
        value.decode().lower()
        for header, value in response.raw_headers
        if header.decode().lower() == "set-cookie"
    ]
    assert any("refresh_token=body-token" in h for h in headers)
    assert any("access_token=new-access-user456" in h for h in headers)

    # Cookie fallback
    response2 = Response()
    auth2 = FakeAuthService()
    result2 = await refresh_token(
        response2,
        refresh_token_body=None,
        refresh_token_cookie="cookie-only",
        auth_service=auth2,
    )
    assert result2["access_token"] == "new-access-user456"
    assert auth2.seen_tokens == ["cookie-only"]
    headers2 = [
        value.decode().lower()
        for header, value in response2.raw_headers
        if header.decode().lower() == "set-cookie"
    ]
    assert any("refresh_token=cookie-only" in h for h in headers2)
    assert any("access_token=new-access-user456" in h for h in headers2)


@pytest.mark.asyncio
async def test_refresh_token_missing_and_invalid():
    class FakeAuthService:
        async def get_refresh_token_payload(self, token: str) -> str | None:
            return None

        def create_access_token(self, sub: str) -> str:
            return f"new-access-{sub}"

    with pytest.raises(HTTPException) as missing_exc:
        await refresh_token(
            Response(),
            refresh_token_body=None,
            refresh_token_cookie=None,
            auth_service=FakeAuthService(),
        )
    assert missing_exc.value.status_code == 403
    assert missing_exc.value.detail == "Refresh token missing"

    with pytest.raises(HTTPException) as invalid_exc:
        await refresh_token(
            Response(),
            refresh_token_body=RefreshTokenBody(refresh_token="badtoken"),
            refresh_token_cookie=None,
            auth_service=FakeAuthService(),
        )
    assert invalid_exc.value.status_code == 403
    assert invalid_exc.value.detail == "Invalid refresh token"


def test_logout_unit_sets_deletion_cookie():
    response = Response()
    logout(response)
    headers = [
        value.decode().lower()
        for header, value in response.raw_headers
        if header.decode().lower() == "set-cookie"
    ]
    assert any("refresh_token=" in h for h in headers)
    assert any("access_token=" in h for h in headers)
    assert any("max-age=0" in h for h in headers)


@pytest.mark.asyncio
async def test_login_cookie_sets_access_and_refresh_cookies():
    class FakeAuthService:
        async def authenticate(self, email: str, password: str):
            return SimpleNamespace(
                id="user123",
                email="u@example.com",
                roles=[Role.DOCTOR],
                profile=SimpleNamespace(name="Dr. U"),
            )

        def create_access_token(self, sub: str) -> str:
            return f"access-{sub}"

        def create_refresh_token(self, sub: str) -> str:
            return f"refresh-{sub}"

    response = Response()
    form = EmailPasswordForm(email="u@example.com", password="pw")
    result = await login_cookie(
        response, form_data=form, auth_service=FakeAuthService()
    )

    assert result["email"] == "u@example.com"
    assert result["name"] == "Dr. U"
    assert result["roles"] == [Role.DOCTOR]
    headers = [
        value.decode().lower()
        for header, value in response.raw_headers
        if header.decode().lower() == "set-cookie"
    ]
    assert any("access_token=access-user123" in h for h in headers)
    assert any("refresh_token=refresh-user123" in h for h in headers)


@pytest.mark.asyncio
async def test_create_user_happy_and_duplicate_paths():
    class FakeUserService:
        def __init__(self, existing=None) -> None:
            self.existing = existing
            self.created = None
            self.queried = None

        async def get_by_email(self, email: str):
            self.queried = email
            return self.existing

        async def create(self, user_in):
            self.created = user_in
            return SimpleNamespace(
                id="user-abc",
                email=user_in.email,
                roles=user_in.roles,
                status=UserStatus.ACTIVE,
                email_verified=False,
                created_at=datetime.now(timezone.utc),
                last_login_at=None,
                profile=user_in.profile,
            )

    user_in = UserCreate(email="new@example.com", password="password123")
    happy_service = FakeUserService()
    result = await create_user(user_in=user_in, user_service=happy_service)
    assert result.email == "new@example.com"
    assert happy_service.queried == "new@example.com"
    assert happy_service.created.email == "new@example.com"
    assert result.roles == [Role.USER]

    duplicate_service = FakeUserService(existing=SimpleNamespace(email="dup@example.com"))
    with pytest.raises(HTTPException) as dup_exc:
        await create_user(user_in=user_in, user_service=duplicate_service)
    assert dup_exc.value.status_code == 400
    assert "already exists" in dup_exc.value.detail
