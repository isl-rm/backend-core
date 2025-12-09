from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm

from app.modules.auth.schemas import Token
from app.modules.auth.service import AuthService
from app.modules.users.schemas import UserBase, UserCreate
from app.modules.users.service import UserService

router = APIRouter()


@router.post(
    "/login/access-token", response_model=Token, summary="Login to get access token"
)
async def login_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    auth_service: AuthService = Depends(AuthService),
) -> Any:
    """
    OAuth2 compatible token login, get an access token for future requests.
    """
    user = await auth_service.authenticate(form_data.username, form_data.password)
    if not user:
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    elif not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")

    access_token_expires = timedelta(minutes=60 * 24 * 8)  # 8 days
    return {
        "access_token": auth_service.create_access_token(
            user.id, expires_delta=access_token_expires
        ),
        "token_type": "bearer",
    }


@router.post(
    "/signup", response_model=UserBase, summary="Register a new user", status_code=201
)
async def create_user(
    user_in: UserCreate,
    user_service: UserService = Depends(UserService),
) -> Any:
    """
    Create a new user account without authentication.
    """
    user = await user_service.get_by_email(user_in.email)
    if user:
        raise HTTPException(
            status_code=400,
            detail="The user with this username already exists in the system",
        )

    user = await user_service.create(user_in)
    return user
