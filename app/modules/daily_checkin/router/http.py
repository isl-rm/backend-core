from fastapi import APIRouter, Depends, HTTPException

from app.modules.daily_checkin.models import SubstanceUse
from app.modules.daily_checkin.schemas import (
    DailyCheckinHistoryResponse,
    DailyCheckinResponse,
    DailyCheckinUpdate,
    HistoryQuery,
    HistoryResponse,
    HistoryRangeQuery,
    IncrementRequest,
    PlanToggleRequest,
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
    payload: SubstanceUse,
    current_user: User = Depends(deps.get_current_user),
    service: DailyCheckinService = Depends(DailyCheckinService),
) -> DailyCheckinResponse:
    return await service.set_substance_use(current_user, payload)


@router.get("/history", response_model=HistoryResponse, summary="List daily check-in history")
async def list_history(
    params: HistoryQuery = Depends(),
    current_user: User = Depends(deps.get_current_user),
    service: DailyCheckinService = Depends(DailyCheckinService),
) -> HistoryResponse:
    return await service.get_history(current_user, params)


@router.get(
    "/history/range",
    response_model=DailyCheckinHistoryResponse,
    summary="List daily check-ins by date range",
)
async def list_history_range(
    params: HistoryRangeQuery = Depends(),
    current_user: User = Depends(deps.get_current_user),
    service: DailyCheckinService = Depends(DailyCheckinService),
) -> DailyCheckinHistoryResponse:
    try:
        return await service.get_history_range(current_user, params)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/history/{id}", response_model=DailyCheckinResponse, summary="Update a specific check-in")
async def update_checkin(
    id: str,
    payload: DailyCheckinUpdate,
    current_user: User = Depends(deps.get_current_user),
    service: DailyCheckinService = Depends(DailyCheckinService),
) -> DailyCheckinResponse:
    try:
        return await service.update_history_checkin(id, payload, current_user)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
