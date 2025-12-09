from typing import Optional

from beanie import Document, Indexed
from pydantic import EmailStr


class User(Document):
    email: Indexed(EmailStr, unique=True)  # type: ignore
    hashed_password: str
    full_name: Optional[str] = None
    is_active: bool = True
    is_superuser: bool = False

    class Settings:
        name = "users"
