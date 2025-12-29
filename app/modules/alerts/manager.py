import asyncio
import json
from typing import Any, Iterable

from fastapi import WebSocket


class AlertConnectionManager:
    """Manage alert connections (WebSocket + SSE) keyed by patient and role."""

    def __init__(self) -> None:
        # WebSocket connections (legacy)
        self._connections: dict[str, dict[str, list[WebSocket]]] = {}
        # SSE connections (new): queue-based message delivery
        self._sse_queues: dict[str, dict[str, list[asyncio.Queue[dict[str, Any]]]]] = {}

    # ========== WebSocket Methods (Existing) ==========

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

    # ========== SSE Methods (New) ==========

    async def subscribe_sse(
        self, queue: asyncio.Queue[dict[str, Any]], role: str, patient_id: str | None
    ) -> None:
        """Register an SSE client queue for alert delivery."""
        role_key = self._normalize_role(role)
        patient_key = self._normalize_patient_id(patient_id)
        self._sse_queues.setdefault(patient_key, {}).setdefault(role_key, []).append(queue)

    def unsubscribe_sse(self, queue: asyncio.Queue[dict[str, Any]]) -> None:
        """Remove an SSE client queue from all subscriptions."""
        for patient_key, role_map in list(self._sse_queues.items()):
            for role_key, queues in list(role_map.items()):
                if queue in queues:
                    queues.remove(queue)
                if not queues:
                    role_map.pop(role_key, None)
            if not role_map:
                self._sse_queues.pop(patient_key, None)

    # ========== Unified Broadcast (Both Transports) ==========

    async def send_to_roles(
        self, patient_id: str, roles: Iterable[str], payload: dict[str, Any]
    ) -> None:
        """Send alert to both WebSocket and SSE clients matching the role criteria."""
        # WebSocket delivery
        message = json.dumps(payload)
        sent_to_ws: set[int] = set()
        for role in roles:
            for socket in self._iter_sockets(patient_id, role):
                socket_id = id(socket)
                if socket_id in sent_to_ws:
                    continue
                try:
                    await socket.send_text(message)
                    sent_to_ws.add(socket_id)
                except Exception:
                    self.disconnect(socket)

        # SSE delivery (queue-based)
        sent_to_sse: set[int] = set()
        for role in roles:
            for queue in self._iter_sse_queues(patient_id, role):
                queue_id = id(queue)
                if queue_id in sent_to_sse:
                    continue
                try:
                    # Non-blocking put; if queue is full, skip (client is slow)
                    queue.put_nowait(payload)
                    sent_to_sse.add(queue_id)
                except asyncio.QueueFull:
                    # Client can't keep up; consider disconnecting or logging
                    pass

    # ========== Internal Iterators ==========

    def _iter_sockets(self, patient_id: str, role: str) -> Iterable[WebSocket]:
        role_key = self._normalize_role(role)
        patient_key = self._normalize_patient_id(patient_id)
        for key in {patient_key, "*"}:
            for socket in self._connections.get(key, {}).get(role_key, []):
                yield socket

    def _iter_sse_queues(
        self, patient_id: str, role: str
    ) -> Iterable[asyncio.Queue[dict[str, Any]]]:
        role_key = self._normalize_role(role)
        patient_key = self._normalize_patient_id(patient_id)
        for key in {patient_key, "*"}:
            for queue in self._sse_queues.get(key, {}).get(role_key, []):
                yield queue

    # ========== Helpers ==========

    @staticmethod
    def _normalize_role(role: str) -> str:
        return role.strip().lower()

    @staticmethod
    def _normalize_patient_id(patient_id: str | None) -> str:
        if not patient_id or patient_id.strip().lower() in {"*", "all"}:
            return "*"
        return patient_id.strip()
