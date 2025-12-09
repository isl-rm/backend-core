from datetime import timedelta
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from app.core import security
from app.core.config import settings
from app.api import deps
from app.models.user import User
from app.schemas.user import UserCreate, UserBase, Token

router = APIRouter()

@router.post("/login/access-token", response_model=Token, summary="Login to get access token")
async def login_access_token(
    form_data: OAuth2PasswordRequestForm = Depends()
) -> Any:
    """
    OAuth2 compatible token login, get an access token for future requests.
    
    **Parameters:**
    - **username**: User email address
    - **password**: User password
    
    **Returns:**
    - **access_token**: JWT token to use in Authorization header
    - **token_type**: Always "bearer"
    """
    user = await User.find_one(User.email == form_data.username)
    if not user or not security.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    elif not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    
    access_token_expires = timedelta(minutes=60 * 24 * 8) # 8 days
    return {
        "access_token": security.create_access_token(
            user.id, expires_delta=access_token_expires
        ),
        "token_type": "bearer",
    }

@router.post("/signup", response_model=UserBase, summary="Register a new user", status_code=201)
async def create_user(
    user_in: UserCreate,
) -> Any:
    """
    Create a new user account without authentication.
    
    **Parameters:**
    - **email**: Valid email address (unique)
    - **password**: User password (will be hashed)
    - **full_name**: Optional full name
    - **is_active**: Whether the user is active (default: true)
    
    **Returns:**
    - User details (without password)
    """
    user = await User.find_one(User.email == user_in.email)
    if user:
        raise HTTPException(
            status_code=400,
            detail="The user with this username already exists in the system",
        )
    
    user = User(
        email=user_in.email,
        hashed_password=security.get_password_hash(user_in.password),
        full_name=user_in.full_name,
        is_active=user_in.is_active,
    )
    await user.insert()
    return user

@router.get("/users/me", response_model=UserBase, summary="Get current user info")
async def read_users_me(
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Get the currently authenticated user's information.
    
    **Requires authentication:** Yes (Bearer token)
    
    **Returns:**
    - Current user details
    """
    return current_user
