"""WebSocket and SSE endpoints for alert consumers and acknowledgments."""

import asyncio
import json
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect, status
from fastapi.responses import StreamingResponse
from jose import JWTError, jwt

from app.core import security
from app.modules.alerts.schemas import AlertAcknowledgmentRequest
from app.modules.alerts.service import alert_manager, alert_service
from app.modules.users.models import User
from app.shared import deps
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


# ========== WebSocket Endpoint (Legacy - Backward Compatibility) ==========


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
    """
    WebSocket endpoint for alert notifications (legacy).
    Kept for backward compatibility during SSE migration.
    """
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


# ========== SSE Endpoint (New - Recommended) ==========


def _validate_role_access(user: User, role: str, patient_id: str | None) -> tuple[str, str]:
    """Validate user has permission for the requested role and patient scope."""
    role_key = role.strip().lower()

    # Patient role: can only subscribe to their own alerts
    if role_key == "patient":
        return role_key, str(user.id)

    # Check if role is valid and user has permission
    allowed_roles = ROLE_PERMISSIONS.get(role_key)
    if not allowed_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Invalid role: {role}",
        )

    if not any(user_role in allowed_roles for user_role in user.roles):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"User does not have {role} role",
        )

    # Admin can subscribe to all patients
    if not patient_id:
        if role_key == "admin":
            return role_key, "*"
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="patient_id required for non-admin roles",
        )

    normalized = patient_id.strip()
    if normalized.lower() in {"*", "all"}:
        if role_key == "admin":
            return role_key, "*"
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can subscribe to all patients",
        )

    return role_key, normalized


@router.get("/stream")
async def stream_alerts(
    request: Request,
    role: str,
    patient_id: str | None = None,
    current_user: User = Depends(deps.get_current_user),
) -> StreamingResponse:
    """
    Server-Sent Events (SSE) endpoint for real-time alert notifications.
    
    Query Parameters:
    - role: User role (caregiver, doctor, nurse, dispatcher, admin, etc.)
    - patient_id: Patient ID to monitor (optional for admin, required for others)
    
    Returns a stream of alert events in SSE format.
    Auto-reconnects on disconnect.
    """
    role_key, patient_key = _validate_role_access(current_user, role, patient_id)

    async def event_generator():
        queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        await alert_manager.subscribe_sse(queue, role=role_key, patient_id=patient_key)
        log.info("sse alert stream connected", role=role_key, patient_id=patient_key, user_id=str(current_user.id))

        try:
            while True:
                # Check if client disconnected
                if await request.is_disconnected():
                    log.info("sse client disconnected", role=role_key, patient_id=patient_key)
                    break

                try:
                    # Wait for next alert with timeout to check disconnect status
                    alert = await asyncio.wait_for(queue.get(), timeout=30.0)
                    # Format as SSE event
                    yield f"data: {json.dumps(alert)}\n\n"
                except asyncio.TimeoutError:
                    # Send keepalive comment to prevent connection timeout
                    yield ": keepalive\n\n"

        except Exception as exc:
            log.error("sse stream error", error=str(exc), role=role_key, patient_id=patient_key)
        finally:
            alert_manager.unsubscribe_sse(queue)
            log.info("sse alert stream closed", role=role_key, patient_id=patient_key)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )


# ========== HTTP Acknowledgment Endpoint (For SSE Clients) ==========


@router.post("/alerts/{alert_id}/acknowledge", status_code=status.HTTP_200_OK)
async def acknowledge_alert(
    alert_id: str,
    patient_id: str,
    ack: AlertAcknowledgmentRequest,
    current_user: User = Depends(deps.get_current_user),
) -> dict[str, str]:
    """
    Acknowledge an alert via HTTP POST (for SSE clients).
    
    Path Parameters:
    - alert_id: The alert ID to acknowledge
    
    Query Parameters:
    - patient_id: The patient ID associated with the alert
    
    Body:
    - status: Optional acknowledgment status
    - note: Optional note from the acknowledging user
    """
    # Determine the user's role for acknowledgment
    # For now, we'll use "patient" if the user is the patient, otherwise use their primary role
    if str(current_user.id) == patient_id:
        recipient_role = "patient"
    elif current_user.roles:
        # Use the first role (could be enhanced to select appropriate role)
        recipient_role = current_user.roles[0].value.lower()
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User has no valid role for acknowledgment",
        )

    success = await alert_service.acknowledge(
        alert_id=alert_id,
        patient_id=patient_id,
        recipient_role=recipient_role,
        status=ack.status,
        note=ack.note,
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert not found or already acknowledged",
        )

    return {"message": "Alert acknowledged successfully", "alert_id": alert_id}

