from datetime import datetime, timedelta, timezone
from typing import Any, Union

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from jose import jwt

from app.core.config import settings

# Use argon2id directly to avoid stdlib crypt() deprecation warnings.
password_hasher = PasswordHasher()

ALGORITHM = "HS256"
# We should add SECRET_KEY to settings, but for now we'll use a default if not present
# In production, this MUST be loaded from env
SECRET_KEY = getattr(
    settings,
    "SECRET_KEY",
    "09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7",
)


def create_access_token(
    subject: Union[str, Any], expires_delta: Union[timedelta, None] = None
) -> str:
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)

    to_encode = {"exp": expire, "sub": str(subject)}
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify passwords hashed with argon2id.
    """
    try:
        return password_hasher.verify(hashed_password, plain_password)
    except VerifyMismatchError:
        return False
    except Exception:
        return False


def get_password_hash(password: str) -> str:
    return password_hasher.hash(password)
