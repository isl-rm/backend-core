from typing import Optional

from fastapi import Form
from pydantic import BaseModel


class AccessTokenResponse(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    email: Optional[str] = None


# Dependency form for login that uses email instead of username.
class EmailPasswordForm:
    def __init__(self, email: str = Form(...), password: str = Form(...)) -> None:
        self.email = email
        self.password = password
