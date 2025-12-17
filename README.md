# Backend Core

This is the backend core project built with FastAPI.

## Setup

1. Install dependencies:
   ```bash
   uv sync
   # or
   pip install -r requirements.txt
   ```

2. Run the server:
   ```bash
   uvicorn app.main:app --reload
   ```

See `.agent/rules/instructions.md` for development guidelines.

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
