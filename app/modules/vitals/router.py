from typing import List, Optional

from fastapi import APIRouter, Depends

from app.modules.users.models import User
from app.modules.vitals.models import Vital, VitalType
from app.modules.vitals.schemas import VitalCreate
from app.modules.vitals.service import VitalService
from app.shared import deps

router = APIRouter()


@router.post(
    "/", response_model=Vital, summary="Record a new vital sign", status_code=201
)
async def create_vital(
    vital_in: VitalCreate,
    current_user: User = Depends(deps.get_current_user),
    service: VitalService = Depends(VitalService),
) -> Vital:
    """
    Record a new vital sign measurement for the authenticated user.
    """
    return await service.create(vital_in, current_user)


@router.get("/", response_model=List[Vital], summary="Get vital signs history")
async def read_vitals(
    type: Optional[VitalType] = None,
    limit: int = 100,
    skip: int = 0,
    current_user: User = Depends(deps.get_current_user),
    service: VitalService = Depends(VitalService),
) -> List[Vital]:
    """
    Get vital signs history for the authenticated user.
    """
    return await service.get_multi(user=current_user, type=type, limit=limit, skip=skip)
