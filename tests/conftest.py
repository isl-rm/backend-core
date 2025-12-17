from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any, AsyncGenerator
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.main import app
from app.modules.users.models import User
from app.modules.vitals.models import Vital


class _FieldProxy:
    """Minimal stand-in for Beanie field proxies used in query expressions."""

    def __init__(self, name: str) -> None:
        self.name = name

    def __eq__(self, other: object) -> tuple[str, str, object]:  # type: ignore[override]
        return ("eq", self.name, other)

    def __ge__(self, other: object) -> tuple[str, str, object]:  # type: ignore[override]
        return ("ge", self.name, other)

    def __le__(self, other: object) -> tuple[str, str, object]:  # type: ignore[override]
        return ("le", self.name, other)

    def __gt__(self, other: object) -> tuple[str, str, object]:  # type: ignore[override]
        return ("gt", self.name, other)

    def __lt__(self, other: object) -> tuple[str, str, object]:  # type: ignore[override]
        return ("lt", self.name, other)


def _install_field_proxies() -> None:
    # These proxies prevent AttributeErrors when code builds expressions like User.email == email
    User.email = _FieldProxy("email")  # type: ignore[attr-defined]
    Vital.type = _FieldProxy("type")  # type: ignore[attr-defined]
    Vital.timestamp = _FieldProxy("timestamp")  # type: ignore[attr-defined]
    Vital.user = SimpleNamespace(id=_FieldProxy("user_id"))  # type: ignore[attr-defined]
    _dummy_settings = SimpleNamespace(pymongo_collection=None, use_state_management=False)
    # Prevent Beanie from requiring real collection initialization
    if getattr(User, "_document_settings", None) is None:
        User._document_settings = _dummy_settings  # type: ignore[attr-defined]
    if getattr(Vital, "_document_settings", None) is None:
        Vital._document_settings = _dummy_settings  # type: ignore[attr-defined]


def _extract_filters(expr: object) -> list[tuple[str, str, object]]:
    if isinstance(expr, tuple) and len(expr) == 3:
        op, field, value = expr
        if op in {"eq", "ge", "le", "gt", "lt"}:
            return [(op, field, value)]
    return []


def _patch_user_model(monkeypatch: pytest.MonkeyPatch, store: dict[str, Any]) -> None:
    def _ensure_id(user: User) -> None:
        if getattr(user, "id", None) is None:
            user.id = str(uuid.uuid4())

    async def _insert(self: User) -> User:
        _ensure_id(self)
        store["users"][str(self.id)] = self
        return self

    async def _save(self: User) -> User:
        _ensure_id(self)
        store["users"][str(self.id)] = self
        return self

    async def _get(user_id: object) -> User | None:
        return store["users"].get(str(user_id))

    async def _find_one(expr: object = None) -> User | None:
        email = None
        filt_items = _extract_filters(expr)
        filt = {field: value for op, field, value in filt_items if op == "eq"}
        if "email" in filt:
            email = filt["email"]
        for user in store["users"].values():
            if email is None or user.email == email:
                return user
        return None

    monkeypatch.setattr(User, "insert", _insert, raising=False)
    monkeypatch.setattr(User, "save", _save, raising=False)
    monkeypatch.setattr(User, "get", staticmethod(_get), raising=False)
    monkeypatch.setattr(User, "find_one", staticmethod(_find_one), raising=False)


def _patch_vital_model(monkeypatch: pytest.MonkeyPatch, store: dict[str, Any]) -> None:
    def _ensure_id(vital: Vital) -> None:
        if getattr(vital, "id", None) is None:
            vital.id = str(uuid.uuid4())

    async def _insert(self: Vital) -> Vital:
        _ensure_id(self)
        if getattr(self, "timestamp", None) is None:
            self.timestamp = datetime.now(timezone.utc)
        store["vitals"].append(self)
        return self

    async def _insert_many(vitals: list[Vital]) -> None:
        for v in vitals:
            await _insert(v)

    class _FakeQuery:
        def __init__(self, filters: list[tuple[str, str, object]] | None = None) -> None:
            self.filters = filters or []
            self._sort_field: str | None = None
            self._descending = False
            self._skip = 0
            self._limit: int | None = None

        def find(self, expr: object) -> "_FakeQuery":
            merged = [*self.filters, *_extract_filters(expr)]
            return _FakeQuery(merged)

        def sort(self, sort_spec: str) -> "_FakeQuery":
            self._descending = sort_spec.startswith("-")
            self._sort_field = sort_spec[1:] if self._descending else sort_spec
            return self

        def skip(self, count: int) -> "_FakeQuery":
            self._skip = count
            return self

        def limit(self, count: int) -> "_FakeQuery":
            self._limit = count
            return self

        def _matches(self, vital: Vital) -> bool:
            for op, field, value in self.filters:
                attr = None
                if field == "user_id":
                    attr = getattr(vital.user, "id", None)
                    if op == "eq" and str(attr) != str(value):
                        return False
                    continue
                attr = getattr(vital, field, None)
                if op == "eq" and attr != value:
                    return False
                if attr is None:
                    return False
                if op == "ge" and not (attr >= value):
                    return False
                if op == "le" and not (attr <= value):
                    return False
                if op == "gt" and not (attr > value):
                    return False
                if op == "lt" and not (attr < value):
                    return False
            return True

        async def to_list(self) -> list[Vital]:
            items = [v for v in store["vitals"] if self._matches(v)]
            if self._sort_field:
                items.sort(
                    key=lambda v: getattr(v, self._sort_field),
                    reverse=self._descending,
                )
            if self._skip:
                items = items[self._skip :]
            if self._limit is not None:
                items = items[: self._limit]
            return items

        async def first_or_none(self) -> Vital | None:
            items = await self.sort("-timestamp").limit(1).to_list()
            return items[0] if items else None

    def _find(expr: object = None) -> _FakeQuery:
        return _FakeQuery(_extract_filters(expr))

    async def _find_one(expr: object = None) -> Vital | None:
        return await _find(expr).first_or_none()

    monkeypatch.setattr(Vital, "insert", _insert, raising=False)
    monkeypatch.setattr(Vital, "insert_many", staticmethod(_insert_many), raising=False)
    monkeypatch.setattr(Vital, "find", staticmethod(_find), raising=False)
    monkeypatch.setattr(Vital, "find_one", staticmethod(_find_one), raising=False)


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
async def db(monkeypatch: pytest.MonkeyPatch) -> AsyncGenerator[dict[str, Any], None]:
    """
    Provide an in-memory stand-in for Mongo to keep tests hermetic without a running DB.
    """
    settings.MONGODB_DB_NAME = "test_backend_core_db"
    store: dict[str, Any] = {"users": {}, "vitals": []}

    _install_field_proxies()
    _patch_user_model(monkeypatch, store)
    _patch_vital_model(monkeypatch, store)

    # Stub init_db to avoid real connection attempts if invoked elsewhere
    async def _init_db_stub() -> object:
        return SimpleNamespace(close=lambda: None)

    monkeypatch.setattr("app.core.db.init_db", _init_db_stub, raising=False)

    yield store

    store["users"].clear()
    store["vitals"].clear()


@pytest.fixture
async def client(db: dict[str, Any]) -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
async def create_user_func(db: dict[str, Any]) -> Any:
    from app.core import security
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


@pytest.fixture(autouse=True)
def reset_vital_manager() -> None:
    """
    Ensure WebSocket connection registries start empty for each test.
    """
    from app.modules.vitals.service import vital_manager

    vital_manager.mobile_connections.clear()
    vital_manager.frontend_connections.clear()
    yield
    vital_manager.mobile_connections.clear()
    vital_manager.frontend_connections.clear()
