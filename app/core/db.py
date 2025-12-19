from beanie import init_beanie
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.core.config import settings
from app.modules.daily_checkin.models import DailyCheckin
from app.modules.users.models import User
from app.modules.vitals.models import Vital

MONGO_CLIENT: AsyncIOMotorClient | None = None


async def init_db() -> AsyncIOMotorClient:
    """
    Create a single Motor client, initialize Beanie, and return the client.

    This should be called exactly once at app startup.
    """
    global MONGO_CLIENT

    client = AsyncIOMotorClient(
        settings.MONGODB_URL,
        uuidRepresentation="standard",
        serverSelectionTimeoutMS=5000,
    )

    db: AsyncIOMotorDatabase = client[settings.MONGODB_DB_NAME]

    await init_beanie(
        database=db,
        document_models=[
            User,
            Vital,
            DailyCheckin,
        ],
    )

    MONGO_CLIENT = client
    return client
