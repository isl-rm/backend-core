"""WebSocket endpoint for frontend vital consumption."""

import structlog
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.modules.vitals.service import vital_manager

router = APIRouter()
log = structlog.get_logger()


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
