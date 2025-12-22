# Backend Core

This is the backend core project built with FastAPI.

## Setup

### Local development (recommended)

1. Start dependencies (MongoDB + Redis):
   ```bash
   docker compose up -d mongo redis
   ```

2. Install `uv` (one-time):
   ```bash
   brew install uv
   # or see https://docs.astral.sh/uv/ for other installers
   ```

3. Install dependencies:
   ```bash
   uv sync
   # or
   pip install -r requirements.txt
   ```

4. Configure environment:
   - Set `MONGODB_URL` and `REDIS_URL` in `.env` (defaults are fine for local Docker).

5. Run the server:
   ```bash
   uv run uvicorn app.main:app --reload
   # or, if using a shell with the venv activated:
   # uvicorn app.main:app --reload
   ```

See `.agent/rules/instructions.md` for development guidelines.

## Redis cache (optional)

Vitals endpoints (`/api/v1/vitals` and `/api/v1/vitals/series`) can use Redis for a short-TTL cache.

- Docker Compose: set `REDIS_URL=redis://redis:6379/0` and run a Redis service.
- Local (non-Docker): set `REDIS_URL=redis://localhost:6379/0`.
- If Redis is unreachable or the `redis` Python dependency isn’t installed, the app falls back to DB-only reads.

### How to monitor Redis traffic

- Docker Compose:
  ```bash
  docker compose exec redis redis-cli MONITOR
  ```
- Local Redis:
  ```bash
  redis-cli -u redis://localhost:6379/0 MONITOR
  ```

When you call the same vitals endpoint twice with identical query params, you should see `GET`/`SET` activity
for `vitals:*` keys. You will also see `MGET` for `vitals:version:*` keys (used for write invalidation).

### How to turn caching off

- Disable Redis caching entirely by unsetting `REDIS_URL` or setting it to an empty string:
  ```bash
  REDIS_URL= uv run uvicorn app.main:app --reload
  ```

## Updating `uv.lock` after dependency changes

This repo uses `uv.lock` to pin exact dependency versions. Docker builds use `uv sync --frozen`, so when
you change `pyproject.toml` you must regenerate the lockfile:

```bash
uv lock
```

Then rebuild:

```bash
docker compose up --build
```

## Login/Signup coverage run

Auth tests already collect coverage via `pyproject.toml` (`--cov=app --cov-report=term-missing`). To see coverage for just the login and signup flows:

1. Ensure MongoDB is running (matches the default URL in `app/core/config.py`):
   ```bash
   docker compose up -d mongo
   ```

2. Run the targeted tests with coverage:
   ```bash
   uv run pytest tests/modules/auth/test_router.py -k "login or signup" --cov-report=term-missing | tee coverage.txt
   # or: pytest tests/modules/auth/test_router.py -k "login or signup" --cov-report=term-missing
   ```

`coverage.txt` will capture the terminal report; drop `-k "login or signup"` to measure the full suite.

## Vitals data conventions

- Timestamps: clients may send ISO 8601 strings or epoch seconds; the backend normalizes to UTC with second precision on write.
- Blood pressure: prefer sending a structured `bloodPressure` payload (`systolic`, `diastolic`) with a unit (e.g., `mmHg`). It is persisted as a `"systolic/diastolic"` string value to avoid losing either measurement.
- Listing: `/api/v1/vitals` accepts `type`, `limit` (1–1000), `skip` (>=0), and optional `start`/`end` (ISO or epoch) query params for pagination/filtering within a date range.

## Alerts workflow (mock AI)

See `docs/alerts-workflow.md` for the architecture, WebSocket subscriptions, and alert escalation flow.
