from typing import Any

from beanie import init_beanie
from pymongo import AsyncMongoClient
from pymongo.asynchronous.database import AsyncDatabase

from app.core.config import settings
from app.modules.users.models import User
from app.modules.vitals.models import Vital


async def init_db() -> None:
    client: AsyncMongoClient[Any] = AsyncMongoClient(settings.MONGODB_URL)
    db: AsyncDatabase[Any] = client[settings.MONGODB_DB_NAME]
    await init_beanie(
        database=db,
        document_models=[User, Vital],
    )
