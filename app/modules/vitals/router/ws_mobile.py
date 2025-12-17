"""WebSocket endpoint and handlers for mobile vitals streaming."""

import json
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, status
from jose import JWTError, jwt
from pydantic import ValidationError

from app.core import security
from app.modules.users.models import User
from app.modules.vitals.models import VitalType
from app.modules.vitals.schemas import EcgStreamPayload, VitalCreate
from app.modules.vitals.service import VitalService, vital_manager

router = APIRouter()
log = structlog.get_logger()


async def _authenticate_mobile_websocket(websocket: WebSocket, token: str) -> Optional[User]:
    """Validate the JWT and return the associated user or close the socket."""
    try:
        payload = jwt.decode(token, security.SECRET_KEY, algorithms=[security.ALGORITHM])
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


async def _handle_ecg_payload(data: dict, service: VitalService, user: User) -> None:
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


async def _handle_generic_vital_payload(data: dict, raw_message: str, service: VitalService, user: User) -> None:
    # Parse into VitalCreate and hand off to service for storage + broadcast
    vital_in = VitalCreate(**data)
    await service.process_vital_stream(vital_in, user, raw_message)


async def _process_mobile_message(raw_message: str, service: VitalService, user: User) -> None:
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
