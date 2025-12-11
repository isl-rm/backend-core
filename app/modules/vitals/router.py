from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException

from app.modules.users.models import User
from app.modules.vitals.models import Vital, VitalType
from app.modules.vitals.schemas import DashboardSummary, VitalBulkCreate, VitalCreate
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


@router.post(
    "/bulk",
    response_model=List[Vital],
    summary="Record multiple vital signs",
    status_code=201,
)
async def create_vitals_bulk(
    bulk_in: VitalBulkCreate,
    current_user: User = Depends(deps.get_current_user),
    service: VitalService = Depends(VitalService),
) -> List[Vital]:
    """
    Record multiple vital sign measurements for the authenticated user in one request.
    """
    return await service.create_bulk(bulk_in, current_user)


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


@router.post(
    "/latest",
    response_model=Vital,
    summary="Get most recent vital sign",
)
async def read_latest_vital(
    type: Optional[VitalType] = None,
    current_user: User = Depends(deps.get_current_user),
    service: VitalService = Depends(VitalService),
) -> Vital:
    """
    Get the latest vital sign for the authenticated user.
    """
    vital = await service.get_latest(user=current_user, type=type)
    if not vital:
        raise HTTPException(status_code=404, detail="No vitals found")
    return vital


@router.get(
    "/dashboard",
    response_model=DashboardSummary,
    summary="Get vitals dashboard summary",
)
async def read_dashboard_summary(
    current_user: User = Depends(deps.get_current_user),
    service: VitalService = Depends(VitalService),
) -> DashboardSummary:
    """
    Return the latest vitals mapped to the dashboard contract.
    """
    return await service.get_dashboard_summary(user=current_user)
