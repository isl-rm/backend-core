# Project Instructions & Architecture Rules

You are an expert Backend Developer working on a FastAPI + MongoDB application.
**Stack:** FastAPI + Python 3.10+ + Pydantic v2 + MongoDB (Beanie ODM) + Structlog + Sentry + UV + Pytest + Ruff + Mypy.

---

## 1. 📂 Folder Structure

```
backend-core/
├── app/
│   ├── api/v1/
│   │   ├── endpoints/      # Route handlers (users.py, auth.py)
│   │   └── api.py          # Router aggregation
│   ├── core/
│   │   ├── config.py       # Pydantic Settings
│   │   ├── security.py     # JWT, password hashing
│   │   ├── db.py           # MongoDB connection
│   │   └── logging.py      # Structlog config
│   ├── models/             # Beanie Documents
│   ├── schemas/            # Pydantic Request/Response models
│   ├── services/           # Business logic layer
│   ├── utils/              # Helper functions
│   └── main.py             # App entry point
├── tests/                  # Mirror app/ structure
├── scripts/                # Utility scripts
└── pyproject.toml
```

**Rules:**
- Keep modules small & focused (single responsibility)
- One class/function group per file
- No `.md` files in `app/`
- Global utilities in `app/utils/` only if used by 2+ modules
- Feature-specific utilities stay in their module

---

## 2. 🗄️ Database & Models (Beanie + Motor)

**Use Beanie ODM** for type-safe, Pydantic-integrated MongoDB operations.

**Model Rules:**
- All models extend `Document` from Beanie
- Use `Field()` from Pydantic for validation
- Define indexes in `Settings` class
- ALWAYS use `async` for database operations
- Use Beanie query methods: `find_one()`, `find().to_list()`, etc.

**When to drop to Motor:**
- Complex aggregation pipelines
- Advanced MongoDB features Beanie doesn't expose
- Use `get_motor_collection(Model)` for hybrid approach

---

## 3. 🔌 API & Routing

**Configuration:**
- Routes: `app/api/v1/endpoints/`
- Main router: `app/api/v1/api.py`
- Dependencies: `app/api/deps.py`

**Routing Rules:**
- Use `APIRouter` for all endpoints
- Group routes by resource
- ALWAYS version APIs: `/api/v1/...`
- Use `Depends()` for dependency injection
- Return Pydantic schemas with `response_model`, not raw Beanie documents
- Use proper HTTP status codes (`status.HTTP_201_CREATED`, etc.)

---

## 4. 📋 Schemas & Validation (Pydantic v2)

**Naming Convention:**
- `[Resource]Create` - POST requests
- `[Resource]Update` - PUT/PATCH requests
- `[Resource]Response` - API responses
- `[Resource]InDB` - Database representation (if needed)

**Validation Rules:**
- Use built-in types: `EmailStr`, `HttpUrl`, etc.
- Use `Field()` for constraints: `min_length`, `max_length`, `ge`, `le`, `regex`
- Use `@field_validator` for custom validation
- NEVER validate in controllers if Pydantic can handle it
- Use `from_attributes = True` in Config (Pydantic v2)

---

## 5. 🧠 Services & Business Logic

**Service Layer Rules:**
- ALL business logic goes in `app/services/`
- Services should NOT depend on `Request` or `Response` objects
- Services are reusable across interfaces (API, CLI, background jobs)
- Use class-based or function-based (be consistent per resource)
- Route handlers only handle HTTP logic, delegate to services

---

## 6. 🔐 Authentication & Security

**Stack:** JWT + argon2id

**Configuration:**
- JWT functions: `app/core/security.py`
- Auth dependencies: `app/api/deps.py`

**Implementation:**
- Use `OAuth2PasswordBearer` for token extraction
- Hash passwords with argon2id via `argon2-cffi`
- JWT tokens via `python-jose`
- Create dependency chains: `get_current_user` → `get_current_active_user` → `get_current_superuser`

---

## 7. 📝 Logging & Observability

**Stack:** Structlog + Sentry

**Logging:**
- Configure structlog in `app/core/logging.py`
- Use structured logging: `logger.info("event", key=value)`
- Use `ConsoleRenderer` in dev, `JSONRenderer` in production
- Log at route level and service level

**Sentry:**
- Initialize in `app/main.py`
- Only if `SENTRY_DSN` is set
- Set `environment` and `traces_sample_rate`

---

## 8. ⚙️ Configuration

**Use `pydantic-settings` for environment variables:**
- Define in `app/core/config.py`
- Use `SettingsConfigDict` with `env_file=".env"`
- Required fields: `MONGODB_URL`, `SECRET_KEY`
- Optional: `SENTRY_DSN`, `ENVIRONMENT`
- Access via singleton: `from app.core.config import settings`

**Never use `os.getenv()` - always use Pydantic Settings**

---

## 9. 🧪 Testing

**Framework:** Pytest + pytest-asyncio

**Testing Rules:**
- ALL route handlers must have tests
- Use `pytest.mark.asyncio` for async tests
- Fixtures in `tests/conftest.py`
- Mock external dependencies
- Test services independently from routes
- Use `AsyncClient` from `httpx` for API tests

---

## 10. 🔧 Code Quality & Tools

**Linting & Formatting:**
- `ruff check .` - Lint
- `ruff check . --fix` - Auto-fix
- `ruff format .` - Format

**Type Checking:**
- `mypy app/` - Strict type checking
- Or use `pyright app/`

**Code Quality Rules:**
- Strict typing: type hints for ALL parameters and returns
- Avoid `Any` - use specific types
- Async first: `async def` for all routes and DB operations
- Explicit over implicit
- Use absolute imports: `from app.services.user_service import UserService`

**Dependency Management:**
- `uv sync` - Install dependencies
- `uv add package-name` - Add package
- `uv remove package-name` - Remove package

**Commit Messages (Conventional Commits):**
- `feat:` - New feature
- `fix:` - Bug fix
- `refactor:` - Code restructuring
- `test:` - Add tests
- `docs:` - Documentation
- `chore:` - Maintenance

---

## 11. 🏗️ Development Workflow

**When implementing a new feature:**

1. **Model** → `app/models/` (Beanie document)
2. **Schema** → `app/schemas/` (Pydantic models)
3. **Service** → `app/services/` (business logic)
4. **Endpoint** → `app/api/v1/endpoints/` (route handler)
5. **Test** → `tests/` (pytest tests)

**Error Handling:**
- Raise `HTTPException` in services for business logic errors
- Use custom exception handlers in `main.py` for global errors
- Return proper status codes and error messages

---

## 12. 🤖 AI Agent Rules

1. **Context Awareness**: Check `app/models/` and `app/schemas/` before creating new ones
2. **Step-by-Step**: Follow workflow: Model → Schema → Service → Endpoint → Test
3. **No Magic**: Explicit is better than implicit. Type everything
4. **Async Everywhere**: Use `async def` for all routes and DB operations
5. **Service Layer First**: Put logic in services, not route handlers
6. **No Emoji in Code**: Only in documentation/comments if needed
7. **Naming**: snake_case for functions/variables, PascalCase for classes

---

## 13. �� Quick Reference

**Common Imports:**
- FastAPI: `FastAPI`, `APIRouter`, `Depends`, `HTTPException`, `status`
- Pydantic: `BaseModel`, `Field`, `EmailStr`, `field_validator`
- Beanie: `Document`, `init_beanie`
- Motor: `AsyncIOMotorClient`

**Database Operations:**
- Find: `await User.find_one(User.email == "test@example.com")`
- Query: `await User.find(User.is_active == True).to_list()`
- Insert: `await user.insert()`
- Update: `await user.update({"$set": {"name": "New"}})`
- Delete: `await user.delete()`

---

**This is the single source of truth for development. Follow strictly for consistency.**
