from datetime import datetime
from typing import Annotated, Any, List, Optional

from pydantic import BaseModel, BeforeValidator, EmailStr, Field, field_validator

from app.shared.constants import Role, UserStatus


def stringify(v: Any) -> str:
    return str(v)


PyObjectId = Annotated[str, BeforeValidator(stringify)]


class ProfileBase(BaseModel):
    name: Optional[str] = None
    avatar_url: Optional[str] = None


class UserBase(BaseModel):
    email: EmailStr
    status: UserStatus = UserStatus.ACTIVE
    roles: List[Role] = [Role.USER]
    profile: ProfileBase = Field(default_factory=ProfileBase)


class UserCreate(UserBase):
    password: str

    @field_validator("roles")
    @classmethod
    def validate_roles(cls, v: List[Role]) -> List[Role]:
        if Role.ADMIN in v:
            raise ValueError("Cannot assign ADMIN role during signup")
        return v


class UserUpdate(BaseModel):
    password: Optional[str] = None
    profile: Optional[ProfileBase] = None
    roles: Optional[List[Role]] = None
    status: Optional[UserStatus] = None


class UserResponse(UserBase):
    id: PyObjectId
    email_verified: bool
    created_at: datetime
    last_login_at: Optional[datetime] = None
