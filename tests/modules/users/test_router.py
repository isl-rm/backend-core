import pytest
from httpx import AsyncClient

from app.core import security


def _auth_headers(user_id: str) -> dict[str, str]:
    token = security.create_access_token(subject=user_id)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_read_users_me_returns_current_user(
    client: AsyncClient, create_user_func
) -> None:
    user = await create_user_func()
    headers = _auth_headers(str(user.id))

    resp = await client.get("/api/v1/users/me", headers=headers)

    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == user.email
    assert data["status"] == "active"
    assert data["roles"] == ["USER"]
    assert "hashedPassword" not in data
