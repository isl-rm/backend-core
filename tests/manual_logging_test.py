import logging
import os
import sys

import structlog

sys.path.append(os.getcwd())
from app.core.config import settings
from app.core.logging import setup_logging

# Force local environment for potential pretty printing
settings.ENVIRONMENT = "local"
settings.LOG_LEVEL = "INFO"


def main() -> None:
    print("--- Setting up logging ---")
    setup_logging()

    logger = structlog.get_logger()

    print("\n--- Testing Structlog ---")
    logger.info("This is an info message", key="value", another_key=123)
    logger.warning("This is a warning", dangerous=True)

    try:
        _ = 1 / 0
    except ZeroDivisionError:
        logger.exception("caught_exception", context="testing exception logging")

    print("\n--- Testing Stdlib Logging (Should be intercepted) ---")
    logging.getLogger("uvicorn").info("Uvicorn startup message simulation")
    logging.getLogger("uvicorn.error").error("Uvicorn error message simulation")


if __name__ == "__main__":
    main()
