from datetime import timedelta
from typing import Any, Optional

from app.core import security
from app.modules.users.models import User
from app.modules.users.service import UserService


class AuthService:
    def __init__(self) -> None:
        self.user_service = UserService()

    async def authenticate(self, email: str, password: str) -> Optional[User]:
        user = await self.user_service.get_by_email(email)
        if not user:
            return None
        if not security.verify_password(password, user.hashed_password):
            return None
        return user

    def create_access_token(self, subject: str | Any, expires_delta: timedelta) -> str:
        return security.create_access_token(subject, expires_delta=expires_delta)
