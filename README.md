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
