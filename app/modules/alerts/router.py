"""WebSocket endpoint for alert consumers and acknowledgments."""

import json
from typing import Optional

import structlog
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status
from jose import JWTError, jwt

from app.core import security
from app.modules.alerts.service import alert_manager, alert_service
from app.modules.users.models import User
from app.shared.constants import Role, UserStatus

router = APIRouter()
log = structlog.get_logger()


ROLE_PERMISSIONS: dict[str, list[Role]] = {
    "caregiver": [Role.CAREGIVER],
    "dispatcher": [Role.DISPATCHER],
    "doctor": [Role.DOCTOR],
    "nurse": [Role.NURSE],
    "first_responder": [Role.FIRST_RESPONDER],
    "admin": [Role.ADMIN],
    "hospital": [Role.DOCTOR, Role.ADMIN],
}


async def _authenticate_alert_websocket(
    websocket: WebSocket, token: str, role: str, patient_id: Optional[str]
) -> Optional[tuple[User, str, str]]:
    try:
        payload = jwt.decode(token, security.SECRET_KEY, algorithms=[security.ALGORITHM])
        token_data = payload.get("sub")
    except (JWTError, ValueError) as exc:
        log.warning("alerts websocket auth failed", reason="jwt_decode", error=str(exc))
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return None

    if not token_data:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return None

    user = await User.get(token_data)
    if not user or user.status != UserStatus.ACTIVE:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return None

    role_key = role.strip().lower()
    if role_key == "patient":
        return user, role_key, str(user.id)

    allowed_roles = ROLE_PERMISSIONS.get(role_key)
    if not allowed_roles:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return None
    if not any(user_role in allowed_roles for user_role in user.roles):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return None

    if not patient_id:
        if role_key == "admin":
            return user, role_key, "*"
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return None

    normalized = patient_id.strip()
    if normalized.lower() in {"*", "all"}:
        if role_key == "admin":
            return user, role_key, "*"
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return None

    return user, role_key, normalized


async def _process_alert_message(
    raw_message: str, role: str, patient_id: str | None
) -> None:
    try:
        data = json.loads(raw_message)
    except json.JSONDecodeError:
        return
    if not isinstance(data, dict):
        return

    event = data.get("event") or data.get("type")
    if event != "ack":
        return

    alert_id = data.get("alertId") or data.get("alert_id")
    patient_value = data.get("patientId") or data.get("patient_id") or patient_id
    status = data.get("status")
    note = data.get("note")
    if not alert_id or not patient_value:
        return

    await alert_service.acknowledge(
        alert_id=alert_id,
        patient_id=patient_value,
        recipient_role=role,
        status=status,
        note=note,
    )


@router.websocket("/ws")
async def websocket_alerts(
    websocket: WebSocket, role: str, token: str, patient_id: str | None = None
) -> None:
    auth_result = await _authenticate_alert_websocket(
        websocket=websocket, token=token, role=role, patient_id=patient_id
    )
    if not auth_result:
        return

    _, role_key, patient_key = auth_result
    await alert_manager.connect(websocket, role=role_key, patient_id=patient_key)
    log.info("alerts websocket connected", role=role_key, patient_id=patient_key)
    try:
        while True:
            raw_message = await websocket.receive_text()
            await _process_alert_message(raw_message, role=role_key, patient_id=patient_key)
    except WebSocketDisconnect:
        alert_manager.disconnect(websocket)
        log.info("alerts websocket disconnected", role=role_key, patient_id=patient_key)
