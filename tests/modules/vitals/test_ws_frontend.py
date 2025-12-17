from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import WebSocketDisconnect

from app.modules.vitals.router import ws_frontend


@pytest.mark.asyncio
async def test_websocket_frontend_connects_and_disconnects(monkeypatch: pytest.MonkeyPatch) -> None:
    connect_frontend = AsyncMock()
    disconnect_calls = []

    def _disconnect_frontend(ws: object) -> None:
        disconnect_calls.append(ws)

    monkeypatch.setattr(ws_frontend.vital_manager, "connect_frontend", connect_frontend)
    monkeypatch.setattr(ws_frontend.vital_manager, "disconnect_frontend", _disconnect_frontend)

    websocket = SimpleNamespace(receive_text=AsyncMock(side_effect=WebSocketDisconnect()))

    await ws_frontend.websocket_frontend(websocket)

    connect_frontend.assert_awaited_once_with(websocket)
    assert disconnect_calls == [websocket]
