from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Set

from fastapi import WebSocket


@dataclass(frozen=True)
class CaregiverVitalSubscription:
    patient_ids: Set[str]


class CaregiverVitalsManager:
    def __init__(self) -> None:
        self._subscriptions: Dict[WebSocket, CaregiverVitalSubscription] = {}

    async def accept(self, websocket: WebSocket) -> None:
        await websocket.accept()

    def subscribe(self, websocket: WebSocket, subscription: CaregiverVitalSubscription) -> None:
        self._subscriptions[websocket] = subscription

    def unsubscribe(self, websocket: WebSocket) -> None:
        self._subscriptions.pop(websocket, None)

    async def broadcast(self, payload: str, patient_id: str) -> None:
        for connection, subscription in list(self._subscriptions.items()):
            if subscription.patient_ids and patient_id not in subscription.patient_ids:
                continue
            try:
                await connection.send_text(payload)
            except Exception:
                self.unsubscribe(connection)


caregiver_vitals_manager = CaregiverVitalsManager()
