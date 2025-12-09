from datetime import datetime, timezone
from typing import List, Optional

from beanie import Document, Indexed, Insert, Replace, Save, Update, before_event
from pydantic import BaseModel, EmailStr, Field

from app.shared.constants import Role, UserStatus


class Profile(BaseModel):
    name: Optional[str] = None
    avatar_url: Optional[str] = None


class User(Document):
    email: Indexed(EmailStr, unique=True)  # type: ignore
    hashed_password: str
    email_verified: bool = False
    status: UserStatus = UserStatus.ACTIVE
    roles: List[Role] = [Role.USER]
    profile: Profile = Field(default_factory=Profile)

    # Security & Audit
    last_login_at: Optional[datetime] = None
    login_failed_attempts: int = 0
    locked_until: Optional[datetime] = None

    # Timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @before_event(Insert, Replace, Save, Update)
    def update_updated_at(self) -> None:
        self.updated_at = datetime.now(timezone.utc)

    class Settings:
        name = "users"
