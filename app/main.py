from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.db import init_db
from app.api import chat

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield

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

app.include_router(chat.router, prefix=settings.API_V1_STR)

from app.api import auth
app.include_router(auth.router, prefix=settings.API_V1_STR, tags=["auth"])

from app.api import vitals
app.include_router(vitals.router, prefix=f"{settings.API_V1_STR}/vitals", tags=["vitals"])

@app.get("/health")
def health_check():
    return {"status": "ok"}
    
