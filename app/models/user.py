from typing import Optional
from beanie import Document
from pydantic import EmailStr, Field

class User(Document):
    email: EmailStr = Field(unique=True)
    hashed_password: str
    full_name: Optional[str] = None
    is_active: bool = True
    is_superuser: bool = False

    class Settings:
        name = "users"
