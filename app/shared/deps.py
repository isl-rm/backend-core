from typing import Any, List

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from pydantic import ValidationError

from app.core import security
from app.core.config import settings
from app.modules.auth.constants import ACCESS_TOKEN_COOKIE_NAME
from app.modules.users.models import User
from app.shared.constants import Role, UserStatus

reusable_oauth2 = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/login/access-token",
    auto_error=False,
)


async def get_current_user(
    request: Request,
    token: str | None = Depends(reusable_oauth2),
) -> User:
    if not token:
        token = request.cookies.get(ACCESS_TOKEN_COOKIE_NAME)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = jwt.decode(
            token, security.SECRET_KEY, algorithms=[security.ALGORITHM]
        )
        token_data = payload.get("sub")
    except (JWTError, ValidationError):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Could not validate credentials",
        ) from None

    user: User | None = await User.get(token_data)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.status != UserStatus.ACTIVE:
        raise HTTPException(status_code=400, detail="Inactive user")
    return user


class RoleChecker:
    def __init__(self, allowed_roles: List[Role], allow_admin: bool = True) -> None:
        self.allowed_roles = allowed_roles
        self.allow_admin = allow_admin

    def __call__(self, user: User = Depends(get_current_user)) -> User:
        if self.allow_admin and Role.ADMIN in user.roles:
            return user

        if set(user.roles).intersection(self.allowed_roles):
            return user

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions",
        )


def check_resource_ownership(
    resource: Any, user: User, owner_field: str = "user_id"
) -> None:
    """
    ABAC helper.
    Ensures user owns the resource or is ADMIN.
    """
    if Role.ADMIN in user.roles:
        return

    owner_id = getattr(resource, owner_field, None)

    if str(owner_id) != str(user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to access this resource",
        )
