from typing import Any

from fastapi import APIRouter, Depends

from app.modules.users.models import User
from app.modules.users.schemas import UserBase
from app.shared import deps

router = APIRouter()


@router.get("/me", response_model=UserBase, summary="Get current user info")
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
