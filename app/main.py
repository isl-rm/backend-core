from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.cache import close_cache, init_cache
from app.core.config import settings
from app.core.db import init_db
from app.core.logging import setup_logging
from app.core.middleware import StructlogMiddleware
from app.modules.auth import router as auth_router
from app.modules.chat import router as chat_router
from app.modules.users import router as users_router
from app.modules.vitals import router as vitals_router

setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # Startup
    mongo_client = await init_db()
    # Redis cache is optional; init_cache() returns None when disabled/unavailable.
    cache_client = await init_cache()
    app.state.mongo_client = mongo_client
    app.state.cache_client = cache_client

    yield

    # Shutdown
    mongo_client.close()
    await close_cache()


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="""
    ## Backend Core API

    This API provides:
    * **Authentication**: User registration, login, and profile management
    * **Vitals Monitoring**: Record and retrieve vital signs (ECG, BPM, Gyroscope, Heart Rate)
    * **Real-time Chat**: WebSocket-based chat functionality

    ### Authentication
    Most endpoints require authentication using Bearer tokens.
    1. Register a new user via `/api/v1/signup`
    2. Login via `/api/v1/login/access-token` to get your token
    3. Use the "Authorize" button above to set your token
    """,
    version="0.1.0",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan,
)

# Set all CORS enabled origins
if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin) for origin in settings.BACKEND_CORS_ORIGINS],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.add_middleware(StructlogMiddleware)

app.include_router(chat_router.router, prefix=settings.API_V1_STR)
app.include_router(auth_router.router, prefix=settings.API_V1_STR, tags=["auth"])
app.include_router(
    users_router.router, prefix=f"{settings.API_V1_STR}/users", tags=["users"]
)
app.include_router(
    vitals_router.router, prefix=f"{settings.API_V1_STR}/vitals", tags=["vitals"]
)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}
