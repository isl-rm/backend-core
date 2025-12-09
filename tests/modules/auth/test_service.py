from datetime import datetime, timedelta, timezone

import pytest

from app.core import security
from app.core.config import settings
from app.modules.auth.service import AuthService
from app.modules.users.models import User
from app.shared.constants import UserStatus


@pytest.mark.asyncio
async def test_authenticate_success(create_user_func):
    auth_service = AuthService()
    password = "securepassword"
    user = await create_user_func(password=password)

    authenticated_user = await auth_service.authenticate(user.email, password)
    assert authenticated_user is not None
    assert authenticated_user.id == user.id
    assert authenticated_user.login_failed_attempts == 0
    # last_login_at should be recent
    assert authenticated_user.last_login_at is not None


@pytest.mark.asyncio
async def test_authenticate_not_found(db):
    auth_service = AuthService()
    authenticated_user = await auth_service.authenticate(
        "nonexistent@example.com", "password"
    )
    assert authenticated_user is None


@pytest.mark.asyncio
async def test_authenticate_wrong_password(create_user_func):
    auth_service = AuthService()
    user = await create_user_func(password="correct")

    authenticated_user = await auth_service.authenticate(user.email, "wrong")
    assert authenticated_user is None

    # Reload user to check failure count
    user_db = await User.get(user.id)
    assert user_db.login_failed_attempts == 1


@pytest.mark.asyncio
async def test_authenticate_inactive(create_user_func):
    auth_service = AuthService()
    user = await create_user_func(status=UserStatus.DISABLED)

    authenticated_user = await auth_service.authenticate(user.email, "password123")
    assert authenticated_user is None


@pytest.mark.asyncio
async def test_authenticate_lockout_logic(create_user_func):
    auth_service = AuthService()
    user = await create_user_func(password="correct")

    # Fail MAX_LOGIN_ATTEMPTS times
    max_attempts = settings.MAX_LOGIN_ATTEMPTS

    for _ in range(max_attempts):
        res = await auth_service.authenticate(user.email, "wrong")
        assert res is None

    user_db = await User.get(user.id)
    assert user_db.locked_until is not None

    locked = user_db.locked_until
    if locked.tzinfo is None:
        locked = locked.replace(tzinfo=timezone.utc)
    assert locked > datetime.now(timezone.utc)

    # Try one more time while locked
    res = await auth_service.authenticate(user.email, "correct")  # Correct password!
    assert res is None  # Should be blocked


@pytest.mark.asyncio
async def test_authenticate_lock_expired(create_user_func):
    auth_service = AuthService()
    # Create user locked in the past
    past = datetime.now(timezone.utc) - timedelta(minutes=1)
    user = await create_user_func(locked_until=past, login_failed_attempts=5)

    # Authenticate with correct password
    res = await auth_service.authenticate(user.email, "password123")
    assert res is not None
    assert res.locked_until is None
    assert res.login_failed_attempts == 0


def test_create_tokens():
    auth_service = AuthService()
    access = auth_service.create_access_token("test_sub")
    refresh = auth_service.create_refresh_token("test_sub")

    assert access
    assert refresh

    # Verify structure
    from jose import jwt

    payload = jwt.decode(access, security.SECRET_KEY, algorithms=[security.ALGORITHM])
    assert payload["sub"] == "test_sub"


@pytest.mark.asyncio
async def test_get_refresh_token_payload():
    auth_service = AuthService()
    token = auth_service.create_refresh_token("valid_sub")

    sub = await auth_service.get_refresh_token_payload(token)
    assert sub == "valid_sub"

    bad_sub = await auth_service.get_refresh_token_payload("invalid_token_string")
    assert bad_sub is None
