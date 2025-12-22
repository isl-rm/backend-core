from typing import Any

from fastapi import (
    APIRouter,
    Body,
    Cookie,
    Depends,
    HTTPException,
    Response,
    status,
)

from app.modules.auth.constants import (
    ACCESS_TOKEN_COOKIE_NAME,
    ACCESS_TOKEN_MAX_AGE,
    ACCESS_TOKEN_SAMESITE,
    ACCESS_TOKEN_SECURE,
    REFRESH_TOKEN_COOKIE_NAME,
    REFRESH_TOKEN_MAX_AGE,
    REFRESH_TOKEN_SECURE,
    REFRESH_TOKEN_SAMESITE,
)
from app.modules.auth.schemas import (
    AccessTokenResponse,
    AccessTokenWithRolesResponse,
    CookieLoginResponse,
    EmailPasswordForm,
    RefreshTokenBody,
)
from app.modules.auth.service import AuthService
from app.modules.users.schemas import UserCreate, UserResponse
from app.modules.users.service import UserService

router = APIRouter()


def _set_access_cookie(response: Response, access_token: str) -> None:
    response.set_cookie(
        key=ACCESS_TOKEN_COOKIE_NAME,
        value=access_token,
        httponly=True,
        secure=ACCESS_TOKEN_SECURE,
        samesite=ACCESS_TOKEN_SAMESITE,
        max_age=ACCESS_TOKEN_MAX_AGE,
        path="/",
    )


def _set_refresh_cookie(response: Response, refresh_token: str) -> None:
    response.set_cookie(
        key=REFRESH_TOKEN_COOKIE_NAME,
        value=refresh_token,
        httponly=True,
        secure=REFRESH_TOKEN_SECURE,
        samesite=REFRESH_TOKEN_SAMESITE,
        max_age=REFRESH_TOKEN_MAX_AGE,
        path="/",
    )


def _clear_access_cookie(response: Response) -> None:
    response.delete_cookie(
        key=ACCESS_TOKEN_COOKIE_NAME,
        httponly=True,
        secure=ACCESS_TOKEN_SECURE,
        samesite=ACCESS_TOKEN_SAMESITE,
        path="/",
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=REFRESH_TOKEN_COOKIE_NAME,
        httponly=True,
        secure=REFRESH_TOKEN_SECURE,
        samesite=REFRESH_TOKEN_SAMESITE,
        path="/",
    )


@router.post(
    "/login/access-token",
    response_model=AccessTokenWithRolesResponse,
    summary="Login to get access token",
)
async def login_access_token(
    response: Response,
    form_data: EmailPasswordForm = Depends(),
    auth_service: AuthService = Depends(AuthService),
) -> Any:
    """
    OAuth2 compatible token login, get an access token for future requests.
    When authorizing via Swagger UI, put your email in the `username` field.
    """
    if not form_data.email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email or username is required",
        )

    user = await auth_service.authenticate(form_data.email, form_data.password)
    if not user:
        raise HTTPException(status_code=400, detail="Incorrect email or password")

    # Generate tokens
    access_token = auth_service.create_access_token(user.id)
    refresh_token = auth_service.create_refresh_token(user.id)
    _set_refresh_cookie(response, refresh_token)

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "roles": user.roles,
    }


@router.post(
    "/login/cookie",
    response_model=CookieLoginResponse,
    summary="Login to set auth cookies",
)
async def login_cookie(
    response: Response,
    form_data: EmailPasswordForm = Depends(),
    auth_service: AuthService = Depends(AuthService),
) -> Any:
    """
    Login using email/password and set access + refresh cookies for web clients.
    """
    if not form_data.email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email or username is required",
        )

    user = await auth_service.authenticate(form_data.email, form_data.password)
    if not user:
        raise HTTPException(status_code=400, detail="Incorrect email or password")

    access_token = auth_service.create_access_token(user.id)
    refresh_token = auth_service.create_refresh_token(user.id)
    _set_access_cookie(response, access_token)
    _set_refresh_cookie(response, refresh_token)

    return {"email": user.email, "name": user.profile.name, "roles": user.roles}


@router.post(
    "/refresh-token",
    response_model=AccessTokenResponse,
    summary="Refresh access token",
)
async def refresh_token(
    response: Response,
    refresh_token_body: RefreshTokenBody | None = Body(None),
    refresh_token_cookie: str | None = Cookie(
        None, alias=REFRESH_TOKEN_COOKIE_NAME
    ),
    auth_service: AuthService = Depends(AuthService),
) -> Any:
    """
    Get a new access token using a refresh token.
    """
    refresh_token_value = (
        refresh_token_body.refresh_token if refresh_token_body else None
    ) or refresh_token_cookie
    if not refresh_token_value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Refresh token missing",
        )

    sub = await auth_service.get_refresh_token_payload(refresh_token_value)
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
    _set_refresh_cookie(response, refresh_token_value)
    _set_access_cookie(response, new_access_token)
    return {"access_token": new_access_token, "token_type": "bearer"}


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Logout and clear auth cookies",
)
def logout(response: Response) -> None:
    """
    Clear auth cookies. If refresh tokens are stored server-side, revoke them here as
    well.
    """
    _clear_access_cookie(response)
    _clear_refresh_cookie(response)


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
            detail="The user with this email already exists in the system",
        )

    user = await user_service.create(user_in)
    return user
