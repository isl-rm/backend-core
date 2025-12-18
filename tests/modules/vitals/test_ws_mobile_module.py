import json
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import WebSocketDisconnect, status
from jose import JWTError

from app.core import security
from app.modules.users.models import User
from app.modules.vitals.models import VitalType
from app.modules.vitals.router import ws_mobile
from app.modules.vitals.schemas import EcgStreamPayload, VitalCreate


def _fake_websocket_with_disconnect() -> SimpleNamespace:
    return SimpleNamespace(receive_text=AsyncMock(side_effect=WebSocketDisconnect()))


@pytest.mark.asyncio
async def test_authenticate_mobile_websocket_success(monkeypatch: pytest.MonkeyPatch) -> None:
    token = security.create_access_token("user-123")
    websocket = SimpleNamespace(closed=False, close_code=None, close=AsyncMock())
    user = SimpleNamespace(id="user-123")
    async def _get(_: object) -> object:
        return user

    monkeypatch.setattr(User, "get", staticmethod(_get), raising=False)

    result = await ws_mobile._authenticate_mobile_websocket(websocket, token)

    assert result is user
    websocket.close.assert_not_awaited()  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_authenticate_mobile_websocket_invalid_token(monkeypatch: pytest.MonkeyPatch) -> None:
    websocket = SimpleNamespace(closed=False, close_code=None, close=AsyncMock())
    monkeypatch.setattr(
        ws_mobile.jwt,
        "decode",
        lambda *args, **kwargs: (_ for _ in ()).throw(JWTError("bad token")),
    )

    result = await ws_mobile._authenticate_mobile_websocket(websocket, "invalid")

    assert result is None
    websocket.close.assert_awaited_once_with(code=status.WS_1008_POLICY_VIOLATION)  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_authenticate_mobile_websocket_missing_user(monkeypatch: pytest.MonkeyPatch) -> None:
    token = security.create_access_token("ghost")
    websocket = SimpleNamespace(closed=False, close_code=None, close=AsyncMock())
    async def _get(_: object) -> None:
        return None

    monkeypatch.setattr(User, "get", staticmethod(_get), raising=False)

    result = await ws_mobile._authenticate_mobile_websocket(websocket, token)

    assert result is None
    websocket.close.assert_awaited_once_with(code=status.WS_1008_POLICY_VIOLATION)  # type: ignore[attr-defined]


def test_is_ecg_payload_accepts_enum_and_string() -> None:
    assert ws_mobile._is_ecg_payload({"type": VitalType.ECG})
    assert ws_mobile._is_ecg_payload({"type": "ecg"})
    assert not ws_mobile._is_ecg_payload({"type": "bpm"})


def test_build_ecg_broadcast_payload_contains_optional_fields() -> None:
    timestamp = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)
    ecg = EcgStreamPayload(bpm=70, samples=[0.1, 0.2], sample_rate=500, timestamp=timestamp)

    payload = json.loads(ws_mobile._build_ecg_broadcast_payload(ecg, bpm_value=70))

    assert payload == {
        "type": VitalType.ECG,
        "sampleRate": 500,
        "bpm": 70,
        "samples": [0.1, 0.2],
        "timestamp": timestamp.isoformat(),
    }


def test_build_ecg_broadcast_payload_omits_bpm_when_missing() -> None:
    ecg = EcgStreamPayload(samples=[1.0], sample_rate=250)

    payload = json.loads(ws_mobile._build_ecg_broadcast_payload(ecg, bpm_value=None))

    assert payload == {"type": VitalType.ECG, "sampleRate": 250, "samples": [1.0]}


@pytest.mark.asyncio
async def test_handle_ecg_payload_uses_bpm_when_present() -> None:
    service = SimpleNamespace(process_vital_stream=AsyncMock())
    user = SimpleNamespace(id="user-321")

    await ws_mobile._handle_ecg_payload({"type": "ecg", "bpm": 64, "unit": "bpm"}, service, user)

    service.process_vital_stream.assert_awaited_once()
    vital_in, _, broadcast = service.process_vital_stream.await_args.args
    assert vital_in.value == 64
    assert json.loads(broadcast)["bpm"] == 64


@pytest.mark.asyncio
async def test_handle_ecg_payload_samples_only_broadcasts(monkeypatch: pytest.MonkeyPatch) -> None:
    service = SimpleNamespace(process_vital_stream=AsyncMock())
    user = SimpleNamespace(id="user-123")
    broadcast = AsyncMock()
    monkeypatch.setattr(ws_mobile.vital_manager, "broadcast_vital", broadcast)

    await ws_mobile._handle_ecg_payload(
        {"type": "ecg", "samples": [0.1, 0.2], "sampleRate": 300},
        service,
        user,
    )

    service.process_vital_stream.assert_not_awaited()
    broadcast.assert_awaited_once()


@pytest.mark.asyncio
async def test_handle_generic_vital_payload_forwards_raw_message() -> None:
    service = SimpleNamespace(process_vital_stream=AsyncMock())
    user = SimpleNamespace(id="user-456")
    raw = '{"type":"bpm","value":85,"unit":"bpm"}'
    data = {"type": "bpm", "value": 85, "unit": "bpm"}

    await ws_mobile._handle_generic_vital_payload(data, raw, service, user)

    service.process_vital_stream.assert_awaited_once()
    vital_in, passed_user, raw_payload = service.process_vital_stream.await_args.args
    assert isinstance(vital_in, VitalCreate)
    assert passed_user == user
    assert raw_payload == raw


@pytest.mark.asyncio
async def test_process_mobile_message_routes_ecg_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    service = SimpleNamespace(process_vital_stream=AsyncMock())
    user = SimpleNamespace(id="user-789")
    raw = '{"type":"ecg","bpm":72,"unit":"bpm"}'
    handle_ecg = AsyncMock()
    monkeypatch.setattr(ws_mobile, "_handle_ecg_payload", handle_ecg)

    await ws_mobile._process_mobile_message(raw, service, user)

    handle_ecg.assert_awaited_once()


@pytest.mark.asyncio
async def test_process_mobile_message_routes_generic_payload() -> None:
    service = SimpleNamespace(process_vital_stream=AsyncMock())
    user = SimpleNamespace(id="user-222")
    raw = '{"type":"bpm","value":85,"unit":"bpm"}'

    await ws_mobile._process_mobile_message(raw, service, user)

    service.process_vital_stream.assert_awaited_once()


@pytest.mark.asyncio
async def test_process_mobile_message_ignores_invalid_json() -> None:
    service = SimpleNamespace(process_vital_stream=AsyncMock())
    user = SimpleNamespace(id="user-000")

    await ws_mobile._process_mobile_message("not-json", service, user)

    service.process_vital_stream.assert_not_awaited()


@pytest.mark.asyncio
async def test_websocket_mobile_returns_when_not_authenticated(monkeypatch: pytest.MonkeyPatch) -> None:
    websocket = _fake_websocket_with_disconnect()
    monkeypatch.setattr(ws_mobile, "_authenticate_mobile_websocket", AsyncMock(return_value=None))
    connect_mobile = AsyncMock()
    disconnect_mobile = AsyncMock()
    monkeypatch.setattr(ws_mobile.vital_manager, "connect_mobile", connect_mobile)
    monkeypatch.setattr(ws_mobile.vital_manager, "disconnect_mobile", disconnect_mobile)

    await ws_mobile.websocket_mobile(websocket=websocket, token="bad-token", service=SimpleNamespace())

    connect_mobile.assert_not_awaited()
    disconnect_mobile.assert_not_awaited()


@pytest.mark.asyncio
async def test_websocket_mobile_processes_messages_and_disconnects(monkeypatch: pytest.MonkeyPatch) -> None:
    websocket = SimpleNamespace()
    websocket.receive_text = AsyncMock(side_effect=["{}", WebSocketDisconnect()])
    user = SimpleNamespace(id="user-111")
    service = SimpleNamespace()

    monkeypatch.setattr(ws_mobile, "_authenticate_mobile_websocket", AsyncMock(return_value=user))
    connect_mobile = AsyncMock()
    disconnect_mobile_called = []

    def _disconnect_mobile(ws: object) -> None:
        disconnect_mobile_called.append(ws)

    disconnect_mobile = _disconnect_mobile
    monkeypatch.setattr(ws_mobile.vital_manager, "connect_mobile", connect_mobile)
    monkeypatch.setattr(ws_mobile.vital_manager, "disconnect_mobile", disconnect_mobile)
    process_mobile = AsyncMock()
    monkeypatch.setattr(ws_mobile, "_process_mobile_message", process_mobile)

    await ws_mobile.websocket_mobile(websocket=websocket, token="valid", service=service)

    connect_mobile.assert_awaited_once_with(websocket)
    process_mobile.assert_awaited_once_with("{}", service, user)
    assert disconnect_mobile_called == [websocket]
