import json
from typing import Optional, Set

import structlog
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status
from jose import JWTError, jwt

from app.core import security
from app.modules.caregivers.vitals.service import (
    CaregiverVitalSubscription,
    caregiver_vitals_manager,
)
from app.modules.users.models import User
from app.shared.constants import Role, UserStatus

router = APIRouter()
log = structlog.get_logger()


def _parse_comma_list(raw: Optional[str]) -> Set[str]:
    if not raw:
        return set()
    return {item.strip() for item in raw.split(",") if item.strip()}


def _parse_patient_ids(value: object) -> Set[str]:
    if isinstance(value, str):
        return _parse_comma_list(value)
    if isinstance(value, list):
        return {str(item) for item in value if str(item).strip()}
    return set()


def _extract_event(raw_message: str) -> tuple[Optional[str], Set[str]]:
    try:
        payload = json.loads(raw_message)
    except json.JSONDecodeError:
        return raw_message.strip().lower(), set()

    if not isinstance(payload, dict):
        return None, set()

    event = payload.get("event") or payload.get("action") or payload.get("type")
    patient_ids = _parse_patient_ids(
        payload.get("patientIds") or payload.get("patient_ids")
    )
    return str(event).lower() if event else None, patient_ids


async def _authenticate_caregiver_websocket(
    websocket: WebSocket, token: str
) -> Optional[User]:
    try:
        payload = jwt.decode(token, security.SECRET_KEY, algorithms=[security.ALGORITHM])
        token_data = payload.get("sub")
    except (JWTError, ValueError) as exc:
        log.warning("caregiver vitals websocket auth failed", reason="jwt_decode", error=str(exc))
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return None

    if not token_data:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return None

    user = await User.get(token_data)
    if not user or user.status != UserStatus.ACTIVE:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return None

    if Role.ADMIN not in user.roles and Role.CAREGIVER not in user.roles:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return None

    return user


@router.websocket("/ws/vitals")
async def websocket_caregiver_vitals(
    websocket: WebSocket,
    token: str,
) -> None:
    """
    Placeholder caregiver WebSocket for patient vital updates.
    Send "start" (or JSON {"event": "start"}) to subscribe.
    Send "stop" to disconnect.
    """
    user = await _authenticate_caregiver_websocket(websocket, token)
    if not user:
        return

    await caregiver_vitals_manager.accept(websocket)
    log.info("caregiver vitals websocket connected", user_id=str(user.id))
    try:
        while True:
            raw_message = await websocket.receive_text()
            event, patient_ids = _extract_event(raw_message)
            if event in {"start", "subscribe"}:
                caregiver_vitals_manager.subscribe(
                    websocket,
                    CaregiverVitalSubscription(patient_ids=patient_ids),
                )
                await websocket.send_text("subscribed")
            elif event in {"stop", "unsubscribe"}:
                await websocket.close(code=status.WS_1000_NORMAL_CLOSURE)
                break
    except WebSocketDisconnect:
        pass
    finally:
        caregiver_vitals_manager.unsubscribe(websocket)
        log.info("caregiver vitals websocket disconnected", user_id=str(user.id))
