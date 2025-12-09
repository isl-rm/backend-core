import logging
import logging.config
import sys
from typing import Any, Dict, List

import sentry_sdk
import structlog

# from sentry_sdk.integrations.structlog import StructlogIntegration, StructlogProcessor # Not available in installed version
from app.core.config import settings


def setup_logging() -> None:
    """
    Configure structured logging for the application.
    - Local: Pretty console logging.
    - Production: JSON logging.
    - Sentry included if DSN is set.
    """
    shared_processors: List[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    # Sentry Integration
    if settings.SENTRY_DSN:
        # shared_processors.append(StructlogProcessor(event_level=logging.ERROR)) # Not available
        sentry_sdk.init(
            dsn=settings.SENTRY_DSN,
            environment=settings.ENVIRONMENT,
            integrations=[
                # StructlogIntegration(), # Not available
            ],
            traces_sample_rate=1.0 if settings.ENVIRONMENT == "local" else 0.1,
        )

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Deciding renderer based on environment
    renderer_processor = (
        structlog.dev.ConsoleRenderer()
        if settings.ENVIRONMENT in ["local", "dev"]
        else structlog.processors.JSONRenderer()
    )

    # Standard Library Logging Interception (Uvicorn / FastAPI)
    logging_config: Dict[str, Any] = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "()": structlog.stdlib.ProcessorFormatter,
                "processor": renderer_processor,
                "foreign_pre_chain": shared_processors,
            },
        },
        "handlers": {
            "default": {
                "level": settings.LOG_LEVEL,
                "class": "logging.StreamHandler",
                "stream": sys.stdout,
                "formatter": "default",
            },
        },
        "loggers": {
            "": {  # Root logger
                "handlers": ["default"],
                "level": settings.LOG_LEVEL,
                "propagate": True,
            },
            "uvicorn": {
                "handlers": ["default"],
                "level": "INFO",
                "propagate": False,
            },
            "uvicorn.error": {
                "handlers": ["default"],
                "level": "INFO",
                "propagate": False,
            },
            "uvicorn.access": {
                "handlers": ["default"],
                "level": "INFO",
                "propagate": False,
            },
        },
    }

    logging.config.dictConfig(logging_config)
