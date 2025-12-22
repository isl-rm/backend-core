from typing import List, Optional

import structlog
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, status
from jose import JWTError, jwt

from app.core import security
from app.modules.caregivers.messages.schemas import MessageThreadPreview
from app.modules.caregivers.messages.service import caregiver_message_manager
from app.modules.users.models import User
from app.shared import deps
from app.shared.constants import Role, UserStatus

router = APIRouter()
log = structlog.get_logger()


async def _authenticate_caregiver_websocket(
    websocket: WebSocket, token: str
) -> Optional[User]:
    try:
        payload = jwt.decode(token, security.SECRET_KEY, algorithms=[security.ALGORITHM])
        token_data = payload.get("sub")
    except (JWTError, ValueError) as exc:
        log.warning("caregiver messages websocket auth failed", reason="jwt_decode", error=str(exc))
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


@router.get(
    "/messages",
    response_model=List[MessageThreadPreview],
    summary="List caregiver message threads",
)
async def list_message_threads(
    current_user: User = Depends(deps.RoleChecker([Role.CAREGIVER])),
) -> List[MessageThreadPreview]:
    return []


@router.websocket("/ws/messages")
async def websocket_caregiver_messages(websocket: WebSocket, token: str) -> None:
    """
    Placeholder caregiver messaging WebSocket.
    Broadcasts inbound messages to connected caregivers.
    """
    user = await _authenticate_caregiver_websocket(websocket, token)
    if not user:
        return

    await caregiver_message_manager.connect(websocket)
    log.info("caregiver messages websocket connected", user_id=str(user.id))
    try:
        while True:
            data = await websocket.receive_text()
            await caregiver_message_manager.broadcast(data)
    except WebSocketDisconnect:
        caregiver_message_manager.disconnect(websocket)
        log.info("caregiver messages websocket disconnected", user_id=str(user.id))
