"""HTTP endpoints for recording and retrieving vitals."""

from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.modules.users.models import User
from app.modules.vitals.models import Vital, VitalType
from app.modules.vitals.schemas import (
    DashboardSummary,
    VitalBulkCreate,
    VitalCreate,
    VitalSeriesResponse,
    VitalsQueryParams,
)
from app.modules.vitals.service import VitalService
from app.shared import deps

router = APIRouter()


async def get_vitals_query_params(
    type: VitalType | None = Query(None, description="Filter by vital type"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum items to return"),
    skip: int = Query(0, ge=0, description="Items to skip for pagination"),
    start: datetime | None = Query(
        None,
        description="Start of date range (ISO 8601 or epoch seconds). Defaults to 24h ago.",
    ),
    end: datetime | None = Query(
        None,
        description="End of date range (ISO 8601 or epoch seconds). Defaults to now.",
    ),
) -> VitalsQueryParams:
    """Expose query params explicitly so Swagger shows them, defaulting to the last 24 hours."""
    end = end or datetime.now(timezone.utc)
    start = start or (end - timedelta(days=1))
    return VitalsQueryParams(type=type, limit=limit, skip=skip, start=start, end=end)


@router.post("/", response_model=Vital, summary="Record a new vital sign", status_code=201)
async def create_vital(
    vital_in: VitalCreate,
    current_user: User = Depends(deps.get_current_user),
    service: VitalService = Depends(VitalService),
) -> Vital:
    """Record a new vital sign measurement for the authenticated user."""
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
    """Record multiple vital sign measurements for the authenticated user in one request."""
    return await service.create_bulk(bulk_in, current_user)


@router.get("/history", response_model=List[Vital], summary="Get vital signs history")
async def read_vitals(
    params: VitalsQueryParams = Depends(get_vitals_query_params),
    current_user: User = Depends(deps.get_current_user),
    service: VitalService = Depends(VitalService),
) -> List[Vital]:
    """Get a user's vital history with optional type filter and pagination (defaults to last 24 hours)."""
    return await service.get_multi(
        user=current_user,
        type=params.type,
        limit=params.limit,
        skip=params.skip,
        start=params.start,
        end=params.end,
    )


@router.get(
    "/series",
    response_model=VitalSeriesResponse,
    summary="Get vitals time series (raw or daily average)",
)
async def read_vital_series(
    type: VitalType = Query(..., description="Vital type to retrieve"),
    start: datetime | None = Query(
        None,
        description="Start of date range (ISO 8601 or epoch seconds). Defaults to 24h ago.",
    ),
    end: datetime | None = Query(
        None,
        description="End of date range (ISO 8601 or epoch seconds). Defaults to now.",
    ),
    limit: int = Query(
        100,
        ge=1,
        le=1000,
        description="Maximum items to return (raw points or daily buckets)",
    ),
    skip: int = Query(0, ge=0, description="Items to skip for pagination"),
    current_user: User = Depends(deps.get_current_user),
    service: VitalService = Depends(VitalService),
) -> VitalSeriesResponse:
    """
    Return raw data when the range is <=3 days; otherwise return daily averages.
    Defaults to the last 24 hours and supports pagination.
    """
    try:
        end = end or datetime.now(timezone.utc)
        start = start or (end - timedelta(days=1))
        return await service.get_series(
            user=current_user, type=type, start=start, end=end, limit=limit, skip=skip
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get(
    "/latest",
    response_model=Vital,
    summary="Get most recent vital sign",
)
async def read_latest_vital(
    type: Optional[VitalType] = None,
    current_user: User = Depends(deps.get_current_user),
    service: VitalService = Depends(VitalService),
) -> Vital:
    """Fetch the newest vital for the authenticated user, optionally by type."""
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
    """Return the latest vitals mapped to the dashboard contract."""
    return await service.get_dashboard_summary(user=current_user)
