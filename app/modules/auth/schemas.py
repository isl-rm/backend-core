from typing import Optional

from fastapi import Form
from pydantic import BaseModel


class AccessTokenResponse(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    email: Optional[str] = None


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
