from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from app.modules.auth.schemas import Token
from app.modules.auth.service import AuthService
from app.modules.users.schemas import UserCreate, UserResponse
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

    # Check if locked (handled in authenticate, but double check return)
    # The service returns None if locked/inactive/bad-pass.

    # Generate tokens
    access_token = auth_service.create_access_token(user.id)
    refresh_token = auth_service.create_refresh_token(user.id)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }


@router.post("/refresh-token", response_model=Token, summary="Refresh access token")
async def refresh_token(
    refresh_token: str = Body(..., embed=True),
    auth_service: AuthService = Depends(AuthService),
) -> Any:
    """
    Get a new access token using a refresh token.
    """
    sub = await auth_service.get_refresh_token_payload(refresh_token)
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid refresh token",
        )

    # We could also verify user status here if we want strict security
    # user = await auth_service.user_service.get(sub)
    # if not user or not user.is_active...

    new_access_token = auth_service.create_access_token(sub)
    # We return the same refresh token (rotation not implemented yet)
    return {
        "access_token": new_access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }


@router.post(
    "/signup",
    response_model=UserResponse,
    summary="Register a new user",
    status_code=201,
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
