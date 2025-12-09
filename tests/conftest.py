from typing import Any, AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.core.db import init_db
from app.main import app


@pytest.fixture(autouse=True)
def mock_security(monkeypatch: pytest.MonkeyPatch) -> None:
    def mock_hash(password: str) -> str:
        return f"hashed_{password}"

    def mock_verify(plain: str, hashed: str) -> bool:
        return hashed == f"hashed_{plain}"

    monkeypatch.setattr("app.core.security.get_password_hash", mock_hash)
    monkeypatch.setattr("app.core.security.verify_password", mock_verify)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def db() -> AsyncGenerator[None, None]:
    settings.MONGODB_DB_NAME = "test_backend_core_db"
    mongo_client = await init_db()
    await mongo_client.drop_database(settings.MONGODB_DB_NAME)
    try:
        yield
    finally:
        await mongo_client.drop_database(settings.MONGODB_DB_NAME)
        mongo_client.close()


@pytest.fixture
async def client(db: None) -> AsyncGenerator[AsyncClient, None]:
    # Use a separate database for testing
    settings.MONGODB_DB_NAME = "test_backend_core_db"

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
async def create_user_func(db: None) -> Any:
    import uuid

    from app.core import security
    from app.modules.users.models import User
    from app.shared.constants import Role, UserStatus

    async def _create_user(password: str = "password123", **kwargs: Any) -> User:
        user_data = {
            "email": f"test_{uuid.uuid4()}@example.com",
            "hashed_password": security.get_password_hash(password),
            "status": UserStatus.ACTIVE,
            "roles": [Role.USER],
            "email_verified": True,
        }
        user_data.update(kwargs)  # allow override

        user = User(**user_data)
        await user.insert()
        return user

    return _create_user
