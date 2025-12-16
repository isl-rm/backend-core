import json
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status
from jose import JWTError, jwt
from pydantic import ValidationError

from app.core import security
from app.core.config import settings

from app.modules.users.models import User
from app.modules.vitals.models import Vital, VitalType
from app.modules.vitals.schemas import DashboardSummary, VitalBulkCreate, VitalCreate
from app.modules.vitals.service import VitalService, vital_manager
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


@router.websocket("/ws/mobile")
async def websocket_mobile(
    websocket: WebSocket,
    token: str,
    service: VitalService = Depends(VitalService),
) -> None:
    """
    WebSocket endpoint for mobile app (producer).
    Receives vital data, saves it to DB, and broadcasts it to connected frontends.
    Requires 'token' query parameter for authentication.
    """
    try:
        payload = jwt.decode(
            token, security.SECRET_KEY, algorithms=[security.ALGORITHM]
        )
        token_data = payload.get("sub")
    except (JWTError, ValidationError):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    user = await User.get(token_data)
    if not user:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await vital_manager.connect_mobile(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            try:
                # Parse and validate incoming data
                json_data = json.loads(data)
                vital_in = VitalCreate(**json_data)

                # Delegate processing (Save + Broadcast) to service
                await service.process_vital_stream(vital_in, user, data)

            except (json.JSONDecodeError, ValidationError):
                # Ignore invalid data
                pass

    except WebSocketDisconnect:
        vital_manager.disconnect_mobile(websocket)


@router.websocket("/ws/frontend")
async def websocket_frontend(websocket: WebSocket) -> None:
    """
    WebSocket endpoint for frontend (consumer).
    Receives broadcasted vital data.
    """
    await vital_manager.connect_frontend(websocket)
    try:
        while True:
            # Frontend just listens, but we need to keep connection open
            # We can perform a heartbeat wait here
            await websocket.receive_text()
    except WebSocketDisconnect:
        vital_manager.disconnect_frontend(websocket)
