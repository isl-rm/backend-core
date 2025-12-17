import json
"""HTTP and WebSocket endpoints for recording and streaming vitals."""

from datetime import datetime
from typing import List, Optional

import structlog
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from jose import JWTError, jwt
from pydantic import ValidationError

from app.core import security
from app.core.config import settings

from app.modules.users.models import User
from app.modules.vitals.models import Vital, VitalType
from app.modules.vitals.schemas import (
    DashboardSummary,
    EcgStreamPayload,
    VitalBulkCreate,
    VitalCreate,
    VitalsQueryParams,
)
from app.modules.vitals.service import VitalService, vital_manager
from app.shared import deps

router = APIRouter()
log = structlog.get_logger()


async def get_vitals_query_params(
    type: VitalType | None = Query(None, description="Filter by vital type"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum items to return"),
    skip: int = Query(0, ge=0, description="Items to skip for pagination"),
    start: datetime | None = Query(
        None, description="Start of date range (ISO 8601 or epoch seconds)"
    ),
    end: datetime | None = Query(
        None, description="End of date range (ISO 8601 or epoch seconds)"
    ),
) -> VitalsQueryParams:
    """Expose query params explicitly so Swagger shows them."""
    return VitalsQueryParams(type=type, limit=limit, skip=skip, start=start, end=end)


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
    params: VitalsQueryParams = Depends(get_vitals_query_params),
    current_user: User = Depends(deps.get_current_user),
    service: VitalService = Depends(VitalService),
) -> List[Vital]:
    """Get a user's vital history with optional type filter and pagination."""
    return await service.get_multi(
        user=current_user,
        type=params.type,
        limit=params.limit,
        skip=params.skip,
        start=params.start,
        end=params.end,
    )


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


async def _authenticate_mobile_websocket(
    websocket: WebSocket, token: str
) -> Optional[User]:
    """Validate the JWT and return the associated user or close the socket."""
    try:
        payload = jwt.decode(
            token, security.SECRET_KEY, algorithms=[security.ALGORITHM]
        )
        token_data = payload.get("sub")
    except (JWTError, ValidationError) as exc:
        log.warning("mobile websocket auth failed", reason="jwt_decode", error=str(exc))
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return None

    user = await User.get(token_data)
    if not user:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return None

    return user


def _is_ecg_payload(data: dict) -> bool:
    msg_type = data.get("type")
    return msg_type == VitalType.ECG or msg_type == VitalType.ECG.value


def _build_ecg_broadcast_payload(ecg: EcgStreamPayload, bpm_value: Optional[float]) -> str:
    payload = {
        "type": VitalType.ECG,
        "sampleRate": ecg.sample_rate,
    }
    if ecg.samples is not None:
        payload["samples"] = ecg.samples
    if bpm_value is not None:
        payload["bpm"] = bpm_value
    if ecg.timestamp:
        payload["timestamp"] = ecg.timestamp.isoformat()
    return json.dumps(payload)


async def _handle_ecg_payload(
    data: dict, service: VitalService, user: User
) -> None:
    ecg = EcgStreamPayload.model_validate(data)
    bpm_value = ecg.bpm if ecg.bpm is not None else ecg.value
    broadcast_data = _build_ecg_broadcast_payload(ecg, bpm_value)

    if bpm_value is not None:
        vital_in = VitalCreate(
            type=VitalType.ECG,
            value=bpm_value,
            unit=ecg.unit or "bpm",
            timestamp=ecg.timestamp,
        )
        # Store BPM-derived ECG and broadcast downstream
        await service.process_vital_stream(vital_in, user, broadcast_data)
    else:
        # Stream-only ECG samples (no persisted BPM)
        await vital_manager.broadcast_vital(broadcast_data)


async def _handle_generic_vital_payload(
    data: dict, raw_message: str, service: VitalService, user: User
) -> None:
    # Parse into VitalCreate and hand off to service for storage + broadcast
    vital_in = VitalCreate(**data)
    await service.process_vital_stream(vital_in, user, raw_message)


async def _process_mobile_message(
    raw_message: str, service: VitalService, user: User
) -> None:
    """Route inbound mobile messages to ECG-specific or generic handlers."""
    try:
        data = json.loads(raw_message)
        if _is_ecg_payload(data):
            await _handle_ecg_payload(data, service, user)
        else:
            await _handle_generic_vital_payload(data, raw_message, service, user)
    except (json.JSONDecodeError, ValidationError):
        # Ignore invalid data rather than tearing down the socket
        return


@router.websocket("/ws/mobile")
async def websocket_mobile(
    websocket: WebSocket,
    token: str,
    service: VitalService = Depends(VitalService),
) -> None:
    """
    WebSocket endpoint for mobile app (producer).
    Auth via `token` query param, then stream inbound vitals to persistence + broadcast.
    """
    user = await _authenticate_mobile_websocket(websocket, token)
    if not user:
        return

    # Maintain connection registry for fan-out to frontend sockets
    await vital_manager.connect_mobile(websocket)
    log.info("mobile websocket connected", user_id=str(user.id))
    try:

        while True:
            raw_message = await websocket.receive_text()
            await _process_mobile_message(raw_message, service, user)
    except WebSocketDisconnect:
        # Cleanly drop from registry on disconnect
        vital_manager.disconnect_mobile(websocket)
        log.info("mobile websocket disconnected", user_id=str(user.id))


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
        log.info("frontend websocket disconnected")
