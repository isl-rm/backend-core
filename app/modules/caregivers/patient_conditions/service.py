from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Set

from fastapi import WebSocket


@dataclass(frozen=True)
class CaregiverSubscription:
    patient_ids: Set[str]
    severities: Set[str]


class CaregiverConditionManager:
    def __init__(self) -> None:
        self._connections: Dict[WebSocket, CaregiverSubscription] = {}

    async def connect(self, websocket: WebSocket, subscription: CaregiverSubscription) -> None:
        await websocket.accept()
        self._connections[websocket] = subscription

    def disconnect(self, websocket: WebSocket) -> None:
        self._connections.pop(websocket, None)

    async def broadcast(self, payload: str, patient_id: str, severity: str) -> None:
        for connection, subscription in list(self._connections.items()):
            if subscription.patient_ids and patient_id not in subscription.patient_ids:
                continue
            if subscription.severities and severity not in subscription.severities:
                continue
            try:
                await connection.send_text(payload)
            except Exception:
                self.disconnect(connection)


caregiver_condition_manager = CaregiverConditionManager()
