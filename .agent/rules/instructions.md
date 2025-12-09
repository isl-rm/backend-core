---
trigger: always_on
---

# FastAPI + MongoDB (Beanie) Expert Context

## Tech Stack
- **Core:** Python 3.12+, FastAPI, Pydantic v2 (Strict).
- **DB:** MongoDB, Motor (Async driver), Beanie ODM.
- **Ops:** UV (Package manager), Structlog, Sentry, Docker.
- **Testing:** Pytest, pytest-asyncio, httpx.AsyncClient.
- **Linting:** Ruff, Mypy (Strict), Black.

## 1. Project Structure
```text
backend-core/
├── app/
│   ├── core/                   # Global Singletons (Config, DB, Logging)
│   ├── modules/                # Feature Modules (Domain Logic)
│   │   ├── auth/               # Example Module
│   │   │   ├── router.py       # Endpoints
│   │   │   ├── service.py      # Business Logic
│   │   │   ├── models.py       # DB Models
│   │   │   └── schemas.py      # Pydantic Schemas
│   │   └── billing/
│   ├── shared/                 # Utilities shared by MULTIPLE modules
│   └── main.py                 # Router aggregation
├── tests/
│   ├── modules/                # Mirrors app/modules/ structure
│   └── conftest.py             # Global fixtures (DB session, AsyncClient)
├── scripts/                    # Maintenance & Data Patch scripts
├── Dockerfile                  # Multi-stage build
├── docker-compose.yml          # Local dev setup (App + Mongo)
├── pyproject.toml
└── uv.lock
````

## 2\. Coding Standards (CRITICAL)

  - **Async First:** `async def` for ALL routes and DB calls. Use `await` explicitly.
  - **Pydantic V2:** Use `model_validate` (not `from_orm`) and `Field` constraints.
  - **Config:** Use `pydantic-settings`. Access via singleton `app.core.config.settings`.
  - **Imports:** Absolute imports only (`from app.services.user import UserService`).

## 3\. Strict Linter Compliance (Ruff + Mypy + Black)

You must act as if `ruff --fix` and `mypy --strict` are running on your output.

**Mypy (Type Safety):**

  - **No `Any`:** Never use `Any`. Use generics (`List[str]`), `TypeVar`, or custom Pydantic models.
  - **Explicit Returns:** Every function must have a return type hint (`-> None`, `-> UserResponse`).
  - **Optional Handling:** Do not treat `Optional[T]` as `T`. Check for `None` explicitly.

**Ruff & Black (Formatting):**

  - **Unused Imports:** Rigorous check. Do not import dependencies if not used.
  - **Import Sorting:** Standard library → Third party → Local app imports.
  - **F-Strings:** Always use f-strings over `+` or `.format()`.
  - **Trailing Commas:** Use trailing commas in multi-line lists/dicts (mimics Black).

## 4\. Architecture Rules
  - **Folder Naming:**
      - Use `app/modules/[feature_name]` (e.g., `app/modules/users`)
  - **Module Isolation:**
      - Each module contains its own Routes, Services, Models, and Schemas.
      - Do not scatter feature logic across global folders.
  - **Cross-Module Communication:**
      - Import Services to talk between modules (`from app.modules.auth.service import ...`).
      - NEVER import another module's Model (DB) directly.
      - Avoid circular imports; move shared logic to `app/shared/` if necessary.
  - **Service Pattern:**
      - Logic goes in `modules/[name]/service.py`, NEVER in routes.
      - Services return Pydantic models or plain data, not `Response` objects.
      - Dependency inject services into routes using `Depends`.
  - **Database (Beanie):**
      - All models inherit `Beanie.Document`.
      - Use `Settings` inner class for collections/indexes.
      - Drop to `Motor` only for complex aggregation.
  - **API:**
      - Use `APIRouter`. Prefix `/api/v1`.
      - Return Pydantic schemas (`response_model`), not DB Documents.
      - Status Codes: Explicit usage (`status.HTTP_201_CREATED`).

## 5\. Naming Conventions

  - **Files:** `snake_case` (e.g., `user_service.py`).
  - **Classes:** `PascalCase`.
  - **Variables/Functions:** `snake_case`.
  - **Schemas:**
      - `[Entity]Create` (POST input)
      - `[Entity]Update` (PATCH input)
      - `[Entity]Response` (Output)

## 6\. Testing & DevOps

  - Use `pytest-asyncio`.
  - Mock external calls(S3, Stripe, etc.), but not the database
  - Test Services in isolation; Test Routes using `httpx.AsyncClient`.
  - Place one-off data migration/patch scripts in `scripts/`
  - Use multi-stage builds to keep images small (under 200MB if possible).

## 7\. Error Handling

  - Raise `HTTPException` in routes.
  - Use custom exceptions in Services; catch and convert to HTTP in Routes or Middleware.
  - Log errors via `structlog` before raising.
