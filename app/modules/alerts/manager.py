import json
from typing import Any, Iterable

from fastapi import WebSocket


class AlertConnectionManager:
    """Manage alert WebSocket connections keyed by patient and role."""

    def __init__(self) -> None:
        self._connections: dict[str, dict[str, list[WebSocket]]] = {}

    async def connect(self, websocket: WebSocket, role: str, patient_id: str | None) -> None:
        await websocket.accept()
        role_key = self._normalize_role(role)
        patient_key = self._normalize_patient_id(patient_id)
        self._connections.setdefault(patient_key, {}).setdefault(role_key, []).append(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        for patient_key, role_map in list(self._connections.items()):
            for role_key, sockets in list(role_map.items()):
                if websocket in sockets:
                    sockets.remove(websocket)
                if not sockets:
                    role_map.pop(role_key, None)
            if not role_map:
                self._connections.pop(patient_key, None)

    async def send_to_roles(
        self, patient_id: str, roles: Iterable[str], payload: dict[str, Any]
    ) -> None:
        message = json.dumps(payload)
        sent_to: set[int] = set()
        for role in roles:
            for socket in self._iter_sockets(patient_id, role):
                socket_id = id(socket)
                if socket_id in sent_to:
                    continue
                try:
                    await socket.send_text(message)
                    sent_to.add(socket_id)
                except Exception:
                    self.disconnect(socket)

    def _iter_sockets(self, patient_id: str, role: str) -> Iterable[WebSocket]:
        role_key = self._normalize_role(role)
        patient_key = self._normalize_patient_id(patient_id)
        for key in {patient_key, "*"}:
            for socket in self._connections.get(key, {}).get(role_key, []):
                yield socket

    @staticmethod
    def _normalize_role(role: str) -> str:
        return role.strip().lower()

    @staticmethod
    def _normalize_patient_id(patient_id: str | None) -> str:
        if not patient_id or patient_id.strip().lower() in {"*", "all"}:
            return "*"
        return patient_id.strip()
