"""Fixtures for alerts module tests."""

from typing import Any

import pytest

from app.core import security
from app.modules.users.models import User
from app.shared.constants import Role


def auth_headers(user_id: str) -> dict[str, str]:
    """Create authorization headers for a user."""
    token = security.create_access_token(subject=user_id)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def test_user(create_user_func: Any) -> User:
    """Create a test user with USER role."""
    return await create_user_func(roles=[Role.USER])


@pytest.fixture
async def test_patient(create_user_func: Any) -> User:
    """Create a test patient user."""
    return await create_user_func(roles=[Role.USER])


@pytest.fixture
async def test_admin(create_user_func: Any) -> User:
    """Create a test admin user."""
    return await create_user_func(roles=[Role.ADMIN])
