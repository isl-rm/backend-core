import json
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import status
from jose import JWTError

from app.core import security
from app.modules.users.models import User
from app.modules.vitals import router
from app.modules.vitals.models import VitalType
from app.modules.vitals.schemas import EcgStreamPayload


def test_is_ecg_payload_accepts_enum_and_string() -> None:
    assert router._is_ecg_payload({"type": VitalType.ECG})
    assert router._is_ecg_payload({"type": "ecg"})
    assert not router._is_ecg_payload({"type": "bpm"})


def test_build_ecg_broadcast_payload_includes_optional_fields() -> None:
    timestamp = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)
    ecg = EcgStreamPayload(bpm=70, samples=[0.1, 0.2], sample_rate=500, timestamp=timestamp)

    payload = json.loads(router._build_ecg_broadcast_payload(ecg, bpm_value=ecg.bpm))

    assert payload["type"] == VitalType.ECG
    assert payload["bpm"] == 70
    assert payload["samples"] == [0.1, 0.2]
    assert payload["sampleRate"] == 500
    assert payload["timestamp"] == timestamp.isoformat()


def test_build_ecg_broadcast_payload_omits_bpm_when_missing() -> None:
    ecg = EcgStreamPayload(samples=[1.0], sample_rate=250)

    payload = json.loads(router._build_ecg_broadcast_payload(ecg, bpm_value=None))

    assert payload["type"] == VitalType.ECG
    assert payload["sampleRate"] == 250
    assert "bpm" not in payload


@pytest.mark.asyncio
async def test_authenticate_mobile_websocket_valid(monkeypatch: pytest.MonkeyPatch) -> None:
    token = security.create_access_token("user-123")
    websocket = SimpleNamespace(closed=False, close_code=None)

    async def _close(code: int) -> None:
        websocket.closed = True
        websocket.close_code = code

    websocket.close = _close  # type: ignore[attr-defined]

    user = SimpleNamespace(id="user-123")

    async def _get(_: object) -> object:
        return user

    monkeypatch.setattr(User, "get", staticmethod(_get), raising=False)

    result = await router._authenticate_mobile_websocket(websocket, token)

    assert result is user
    assert websocket.closed is False


@pytest.mark.asyncio
async def test_authenticate_mobile_websocket_invalid_token(monkeypatch: pytest.MonkeyPatch) -> None:
    websocket = SimpleNamespace(closed=False, close_code=None)

    async def _close(code: int) -> None:
        websocket.closed = True
        websocket.close_code = code

    websocket.close = _close  # type: ignore[attr-defined]
    # Force decode failure
    monkeypatch.setattr(router.jwt, "decode", lambda *args, **kwargs: (_ for _ in ()).throw(JWTError("bad token")))

    result = await router._authenticate_mobile_websocket(websocket, "invalid")

    assert result is None
    assert websocket.closed is True
    assert websocket.close_code == status.WS_1008_POLICY_VIOLATION


@pytest.mark.asyncio
async def test_authenticate_mobile_websocket_missing_user(monkeypatch: pytest.MonkeyPatch) -> None:
    token = security.create_access_token("ghost")
    websocket = SimpleNamespace(closed=False, close_code=None)

    async def _close(code: int) -> None:
        websocket.closed = True
        websocket.close_code = code

    websocket.close = _close  # type: ignore[attr-defined]
    async def _get(_: object) -> None:
        return None

    monkeypatch.setattr(User, "get", staticmethod(_get), raising=False)

    result = await router._authenticate_mobile_websocket(websocket, token)

    assert result is None
    assert websocket.closed is True
    assert websocket.close_code == status.WS_1008_POLICY_VIOLATION


@pytest.mark.asyncio
async def test_handle_ecg_payload_uses_value_when_bpm_absent() -> None:
    service = SimpleNamespace(process_vital_stream=AsyncMock())
    user = SimpleNamespace(id="user-123")

    await router._handle_ecg_payload({"type": "ecg", "value": 64, "unit": "bpm"}, service, user)

    service.process_vital_stream.assert_awaited_once()
    call_args = service.process_vital_stream.await_args
    vital_in = call_args.args[0]
    broadcast_data = call_args.args[2]
    assert vital_in.type == VitalType.ECG
    assert vital_in.value == 64
    assert json.loads(broadcast_data)["bpm"] == 64


@pytest.mark.asyncio
async def test_handle_ecg_payload_samples_only_broadcasts(monkeypatch: pytest.MonkeyPatch) -> None:
    service = SimpleNamespace(process_vital_stream=AsyncMock())
    user = SimpleNamespace(id="user-123")
    broadcast = AsyncMock()
    monkeypatch.setattr(router.vital_manager, "broadcast_vital", broadcast)

    await router._handle_ecg_payload(
        {"type": "ecg", "samples": [0.1, 0.2], "sampleRate": 300},
        service,
        user,
    )

    service.process_vital_stream.assert_not_awaited()
    broadcast.assert_awaited_once()


@pytest.mark.asyncio
async def test_process_mobile_message_routes_generic_payload() -> None:
    service = SimpleNamespace(process_vital_stream=AsyncMock())
    user = SimpleNamespace(id="user-456")
    raw = '{"type":"bpm","value":85,"unit":"bpm"}'

    await router._process_mobile_message(raw, service, user)

    service.process_vital_stream.assert_awaited_once()
    call_args = service.process_vital_stream.await_args
    vital_in, passed_user, raw_payload = call_args.args
    assert vital_in.type == VitalType.BPM
    assert vital_in.value == 85
    assert passed_user == user
    assert raw_payload == raw


@pytest.mark.asyncio
async def test_process_mobile_message_ignores_invalid_json() -> None:
    service = SimpleNamespace(process_vital_stream=AsyncMock())
    user = SimpleNamespace(id="user-789")

    await router._process_mobile_message("not-json", service, user)

    service.process_vital_stream.assert_not_awaited()
