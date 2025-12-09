from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import structlog
from jose import JWTError, jwt

from app.core import security
from app.core.config import settings
from app.modules.users.models import User
from app.modules.users.service import UserService
from app.shared.constants import UserStatus

log = structlog.get_logger()


class AuthService:
    def __init__(self) -> None:
        self.user_service = UserService()

    async def authenticate(self, email: str, password: str) -> Optional[User]:
        user = await self.user_service.get_by_email(email)

        if not user:
            log.warning("auth.login_failed", email=email, reason="user_not_found")
            return None

        # Check Global Status
        if user.status != UserStatus.ACTIVE:
            log.warning(
                "auth.login_failed", email=email, reason="inactive", status=user.status
            )
            return None

        # Check Lockout
        if user.locked_until:
            locked_until = user.locked_until
            if locked_until.tzinfo is None:
                locked_until = locked_until.replace(tzinfo=timezone.utc)

            if locked_until > datetime.now(timezone.utc):
                log.warning(
                    "auth.login_locked", email=email, locked_until=user.locked_until
                )
                return None
            else:
                # Lock expired, reset
                user.locked_until = None
                user.login_failed_attempts = 0
                await user.save()

        # Verify Password
        if not security.verify_password(password, user.hashed_password):
            user.login_failed_attempts += 1
            log.warning(
                "auth.login_failed", email=email, attempt=user.login_failed_attempts
            )

            if user.login_failed_attempts >= settings.MAX_LOGIN_ATTEMPTS:
                user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=15)
                log.warning(
                    "auth.account_locked", email=email, locked_until=user.locked_until
                )

            await user.save()
            return None

        # Success - Reset failure counters
        user.login_failed_attempts = 0
        user.last_login_at = datetime.now(timezone.utc)
        await user.save()
        log.info("auth.login_success", email=email, user_id=str(user.id))
        return user

    def create_access_token(self, subject: str | Any) -> str:
        return security.create_access_token(
            subject,
            expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        )

    def create_refresh_token(self, subject: str | Any) -> str:
        return security.create_access_token(
            subject, expires_delta=timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        )

    async def get_refresh_token_payload(self, refresh_token: str) -> str | None:
        try:
            payload = jwt.decode(
                refresh_token, security.SECRET_KEY, algorithms=[security.ALGORITHM]
            )
            return str(payload.get("sub"))
        except JWTError:
            return None
