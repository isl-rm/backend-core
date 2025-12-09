from typing import Any, List

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from pydantic import ValidationError

from app.core import security
from app.core.config import settings
from app.modules.users.models import User
from app.shared.constants import Role, UserStatus

reusable_oauth2 = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/login/access-token"
)


async def get_current_user(token: str = Depends(reusable_oauth2)) -> User:
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
    def __init__(self, allowed_roles: List[Role]) -> None:
        self.allowed_roles = allowed_roles

    def __call__(self, user: User = Depends(get_current_user)) -> User:
        if Role.ADMIN in user.roles:
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
