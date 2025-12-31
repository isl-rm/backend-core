"""SSE alert streaming router for caregivers."""

import asyncio
import json

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse

from app.modules.alerts.service import alert_manager
from app.modules.caregivers.patients.service import CaregiverPatientService
from app.modules.users.models import User
from app.shared import deps
from app.shared.constants import Role

router = APIRouter()
log = structlog.get_logger()


@router.get("/alerts/stream")
async def stream_caregiver_alerts(
    request: Request,
    current_user: User = Depends(deps.get_current_user),
) -> StreamingResponse:
    """
    Server-Sent Events (SSE) endpoint for caregivers to receive alerts from all their subscribed patients.
    
    This endpoint automatically subscribes the caregiver to alerts from all patients they have access to.
    No need to specify individual patient IDs - the system handles this automatically.
    
    Returns a stream of alert events in SSE format from all subscribed patients.
    Auto-reconnects on disconnect.
    """
    # Verify user has caregiver role
    if Role.CAREGIVER not in current_user.roles and Role.ADMIN not in current_user.roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User must have caregiver role to access this endpoint",
        )
    
    # Get all patients this caregiver has access to
    patient_service = CaregiverPatientService()
    patient_ids = await patient_service.list_patient_ids(current_user)
    
    if not patient_ids:
        # No patients yet - still allow connection but won't receive alerts until patients are added
        log.info("caregiver sse stream connected with no patients", user_id=str(current_user.id))
    
    async def event_generator():
        queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        
        # Subscribe to alerts for all patients as a caregiver
        await alert_manager.subscribe_sse_for_patients(
            queue=queue,
            role="caregiver",
            patient_ids=patient_ids,
            caregiver_id=str(current_user.id)
        )
        
        log.info(
            "caregiver sse alert stream connected",
            user_id=str(current_user.id),
            patient_count=len(patient_ids)
        )

        try:
            while True:
                # Check if client disconnected
                if await request.is_disconnected():
                    log.info("caregiver sse client disconnected", user_id=str(current_user.id))
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
            log.error("caregiver sse stream error", error=str(exc), user_id=str(current_user.id))
        finally:
            alert_manager.unsubscribe_sse(queue)
            log.info("caregiver sse alert stream closed", user_id=str(current_user.id))

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )
