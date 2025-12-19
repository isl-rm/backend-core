from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query

from app.modules.daily_checkin.models import SubstanceUse
from app.modules.daily_checkin.schemas import (
    DailyCheckinResponse,
    DailyCheckinUpdate,
    HistoryQuery,
    HistoryResponse,
    IncrementRequest,
    PlanToggleRequest,
    SubstanceUseIn,
)
from app.modules.daily_checkin.service import DailyCheckinService
from app.modules.users.models import User
from app.shared import deps

router = APIRouter(prefix="/daily-checkin", tags=["daily-checkin"])


@router.get("/today", response_model=DailyCheckinResponse, summary="Get today's check-in")
async def get_today_checkin(
    current_user: User = Depends(deps.get_current_user),
    service: DailyCheckinService = Depends(DailyCheckinService),
) -> DailyCheckinResponse:
    return await service.get_today(current_user)


@router.put("/today", response_model=DailyCheckinResponse, summary="Save today's check-in")
async def save_today_checkin(
    payload: DailyCheckinUpdate,
    current_user: User = Depends(deps.get_current_user),
    service: DailyCheckinService = Depends(DailyCheckinService),
) -> DailyCheckinResponse:
    try:
        return await service.upsert_today(payload, current_user)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.patch(
    "/today/kicks",
    response_model=DailyCheckinResponse,
    summary="Increment kick counter",
)
async def increment_kicks(
    payload: IncrementRequest,
    current_user: User = Depends(deps.get_current_user),
    service: DailyCheckinService = Depends(DailyCheckinService),
) -> DailyCheckinResponse:
    return await service.increment_kicks(current_user, payload.delta)


@router.patch(
    "/today/hydration",
    response_model=DailyCheckinResponse,
    summary="Increment hydration counter",
)
async def increment_hydration(
    payload: IncrementRequest,
    current_user: User = Depends(deps.get_current_user),
    service: DailyCheckinService = Depends(DailyCheckinService),
) -> DailyCheckinResponse:
    return await service.increment_hydration(current_user, payload.delta)


@router.patch(
    "/today/plan/{item_id}",
    response_model=DailyCheckinResponse,
    summary="Toggle a plan item completion",
)
async def toggle_plan_item(
    item_id: str,
    payload: PlanToggleRequest,
    current_user: User = Depends(deps.get_current_user),
    service: DailyCheckinService = Depends(DailyCheckinService),
) -> DailyCheckinResponse:
    try:
        return await service.toggle_plan_item(current_user, item_id, payload.completed)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.patch(
    "/today/substance",
    response_model=DailyCheckinResponse,
    summary="Update substance use status for today",
)
async def update_substance_use(
    payload: SubstanceUseIn,
    current_user: User = Depends(deps.get_current_user),
    service: DailyCheckinService = Depends(DailyCheckinService),
) -> DailyCheckinResponse:
    substance_use = SubstanceUse(**payload.model_dump(by_alias=True))
    return await service.set_substance_use(current_user, substance_use)


@router.get("/history", response_model=HistoryResponse, summary="List daily check-in history")
async def list_history(
    start: datetime | None = Query(
        None, description="Start date (ISO 8601 or epoch seconds)", example="2025-11-18T00:00:00Z"
    ),
    end: datetime | None = Query(
        None, description="End date (ISO 8601 or epoch seconds)", example="2025-12-18T00:00:00Z"
    ),
    limit: int = Query(30, ge=1, le=200),
    skip: int = Query(0, ge=0),
    current_user: User = Depends(deps.get_current_user),
    service: DailyCheckinService = Depends(DailyCheckinService),
) -> HistoryResponse:
    params = HistoryQuery(start=start, end=end, limit=limit, skip=skip)
    return await service.get_history(current_user, params)
