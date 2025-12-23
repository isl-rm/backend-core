from typing import Optional

from fastapi import Form
from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.shared.constants import Role


class AccessTokenResponse(BaseModel):
    access_token: str
    token_type: str


class AccessTokenWithRolesResponse(AccessTokenResponse):
    roles: list[Role]


class CookieLoginResponse(BaseModel):
    email: EmailStr
    name: str | None = None
    roles: list[Role]


class TokenData(BaseModel):
    email: Optional[str] = None


class RefreshTokenBody(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    refresh_token: str | None = Field(
        default=None,
        alias="refreshToken",
    )


# Dependency form for login that accepts either `email` or the OAuth-standard
# `username` field used by Swagger's "Authorize" flow. Both map to the user's email.
class EmailPasswordForm:
    def __init__(
        self,
        email: str | None = Form(None),
        username: str | None = Form(None),
        password: str = Form(...),
    ) -> None:
        self.email = email or username
        self.username = self.email
        self.password = password
