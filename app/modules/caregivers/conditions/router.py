from typing import Optional, Set

import structlog
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, status
from jose import JWTError, jwt

from app.core import security
from app.modules.caregivers.conditions.service import (
    CaregiverSubscription,
    caregiver_condition_manager,
)
from app.modules.caregivers.patients.service import CaregiverPatientService
from app.modules.users.models import User
from app.shared.constants import Role, UserStatus

router = APIRouter()
log = structlog.get_logger()

_SEVERITY_OPTIONS = {"moderate", "critical"}


def _parse_comma_list(raw: Optional[str]) -> Set[str]:
    if not raw:
        return set()
    return {item.strip() for item in raw.split(",") if item.strip()}


def _normalize_severities(raw: Optional[str]) -> Set[str]:
    if not raw:
        return set(_SEVERITY_OPTIONS)
    parsed = {value.lower() for value in _parse_comma_list(raw)}
    normalized = {value for value in parsed if value in _SEVERITY_OPTIONS}
    return normalized or set(_SEVERITY_OPTIONS)


async def _authenticate_caregiver_websocket(
    websocket: WebSocket, token: str
) -> Optional[User]:
    try:
        payload = jwt.decode(token, security.SECRET_KEY, algorithms=[security.ALGORITHM])
        token_data = payload.get("sub")
    except (JWTError, ValueError) as exc:
        log.warning("caregiver websocket auth failed", reason="jwt_decode", error=str(exc))
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


@router.websocket("/ws/conditions")
async def websocket_caregiver_conditions(
    websocket: WebSocket,
    token: str,
    patient_ids: Optional[str] = None,
    severity: Optional[str] = None,
    patient_service: CaregiverPatientService = Depends(CaregiverPatientService),
) -> None:
    """
    Placeholder caregiver WebSocket for moderate/critical condition updates.
    """
    user = await _authenticate_caregiver_websocket(websocket, token)
    if not user:
        return

    requested_ids = _parse_comma_list(patient_ids)
    authorized_ids = set(await patient_service.list_patient_ids(user))
    allowed_ids = requested_ids & authorized_ids if requested_ids else authorized_ids
    subscription = CaregiverSubscription(
        patient_ids=allowed_ids,
        severities=_normalize_severities(severity),
    )
    await caregiver_condition_manager.connect(websocket, subscription)
    log.info("caregiver conditions websocket connected", user_id=str(user.id))
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        caregiver_condition_manager.disconnect(websocket)
        log.info("caregiver conditions websocket disconnected", user_id=str(user.id))
