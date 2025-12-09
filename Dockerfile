FROM python:3.12-slim-bookworm AS builder

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set env vars to opt-out of color output and interactive elements
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

WORKDIR /app

# Install dependencies
# We bind mount uv.lock and pyproject.toml to avoid copying them into the layer
# and cache the uv directory to speed up future builds
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project --no-dev

# Copy the rest of the application
COPY . .

# Install the project itself
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# Final stage
FROM python:3.12-slim-bookworm

WORKDIR /app

# Copy the venv from the builder stage
COPY --from=builder /app /app

# Place venv in PATH
ENV PATH="/app/.venv/bin:$PATH"

# Run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
