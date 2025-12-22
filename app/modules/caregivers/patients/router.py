from typing import List

from fastapi import APIRouter, Depends

from app.modules.users.models import User
from app.modules.users.schemas import UserResponse
from app.shared import deps
from app.shared.constants import Role

router = APIRouter()


@router.get(
    "/patients",
    response_model=List[UserResponse],
    summary="List patients for caregiver",
)
async def list_caregiver_patients(
    current_user: User = Depends(deps.RoleChecker([Role.CAREGIVER])),
) -> List[UserResponse]:
    return []


@router.get(
    "/patients/moderate",
    response_model=List[UserResponse],
    summary="List moderate-condition patients for caregiver",
)
async def list_caregiver_patients_moderate(
    current_user: User = Depends(deps.RoleChecker([Role.CAREGIVER])),
) -> List[UserResponse]:
    return []


@router.get(
    "/patients/critical",
    response_model=List[UserResponse],
    summary="List critical-condition patients for caregiver",
)
async def list_caregiver_patients_critical(
    current_user: User = Depends(deps.RoleChecker([Role.CAREGIVER])),
) -> List[UserResponse]:
    return []
