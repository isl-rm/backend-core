import time
import uuid
from typing import Awaitable, Callable

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings


class StructlogMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        # 1. Generate or Retrieve Request ID
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        correlation_id = request.headers.get("X-Correlation-ID") or request_id

        # 2. Bind ContextVars (Clear previous context first if needed,
        # but structlog.contextvars handles local context)
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            correlation_id=correlation_id,
            method=request.method,
            path=request.url.path,
            client_ip=request.client.host if request.client else None,
        )

        # 3. Log Request Start
        logger = structlog.get_logger()
        # Only log start in local/dev to reduce noise in prod, or keep it debug
        if settings.ENVIRONMENT in ["local", "dev"]:
            logger.info("request_started")

        start_time = time.perf_counter()

        try:
            # 4. Process Request
            response = await call_next(request)

            # 5. Log Request Success
            process_time = time.perf_counter() - start_time
            logger.info(
                "request_finished",
                status_code=response.status_code,
                duration=process_time,
            )

            # 6. Append Header
            response.headers["X-Request-ID"] = request_id
            return response

        except Exception:
            # 5b. Log Request Failure (Exception)
            # Exception will be caught here, logged, and re-raised for the exception handler
            process_time = time.perf_counter() - start_time
            logger.exception(
                "request_failed",
                duration=process_time,
            )
            raise
