"""HTTP endpoints for recording and retrieving vitals."""

from datetime import datetime, timedelta, timezone
from typing import List, Optional
import logging
from fastapi import APIRouter, Depends, HTTPException, Query

from app.modules.users.models import User
from app.modules.vitals.models import Vital, VitalType
from app.modules.vitals.schemas import (
    DashboardSummary,
    VitalBulkCreate,
    VitalCreate,
    VitalSeriesResponse,
    VitalsQueryParams,
    VitalsSeriesQuery,
)
from app.modules.vitals.service import VitalService
from app.shared import deps

router = APIRouter()


async def get_vitals_query_params(
    params: VitalsQueryParams = Depends(),
) -> VitalsQueryParams:
    """Expose query params explicitly so Swagger shows them, defaulting to the last 24 hours."""
    resolved_end = params.end or datetime.now(timezone.utc)
    resolved_start = params.start or (resolved_end - timedelta(days=1))
    if resolved_start != params.start or resolved_end != params.end:
        return params.model_copy(
            update={"start": resolved_start, "end": resolved_end}
        )
    return params


async def get_vital_series_query_params(
    params: VitalsSeriesQuery = Depends(),
) -> VitalsSeriesQuery:
    logging.getLogger("series query").info("params: %s", params)
    """Normalize date defaults for vitals series queries."""
    resolved_end = params.end or datetime.now(timezone.utc)
    resolved_start = params.start or (resolved_end - timedelta(days=1))
    if resolved_start != params.start or resolved_end != params.end:
        return params.model_copy(
            update={"start": resolved_start, "end": resolved_end}
        )
    return params


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
    logging.getLogger("history").info("params: %s", params)
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
    params: VitalsSeriesQuery = Depends(get_vital_series_query_params),
    current_user: User = Depends(deps.get_current_user),
    service: VitalService = Depends(VitalService),
) -> VitalSeriesResponse:
    logging.getLogger("series").info("params: %s", params)
    """
    Return raw data when the range is <=3 days; otherwise return daily averages.
    Defaults to the last 24 hours and supports pagination.
    """
    try:
        return await service.get_series(
            user=current_user,
            type=type,
            start=params.start,
            end=params.end,
            limit=params.limit,
            skip=params.skip,
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
