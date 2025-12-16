from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock

import pytest

from app.modules.vitals.models import Vital, VitalType
from app.modules.vitals.schemas import VitalCreate
from app.modules.vitals.service import VitalConnectionManager, VitalService


class _FakeWebSocket:
    def __init__(self, should_fail: bool = False) -> None:
        self.accepted = False
        self.sent: list[str] = []
        self.should_fail = should_fail

    async def accept(self) -> None:
        self.accepted = True

    async def send_text(self, data: str) -> None:
        if self.should_fail:
            raise RuntimeError("send failed")
        self.sent.append(data)


@pytest.mark.asyncio
async def test_process_vital_stream_persists_and_broadcasts(monkeypatch: pytest.MonkeyPatch, create_user_func) -> None:
    service = VitalService()
    user = await create_user_func()
    vital_in = VitalCreate(type=VitalType.BPM, value=70, unit="bpm")

    # Step 1: Stub persistence and broadcast to observe calls
    create_mock = AsyncMock()
    monkeypatch.setattr(service, "create", create_mock)
    broadcast_mock = AsyncMock()
    monkeypatch.setattr("app.modules.vitals.service.vital_manager.broadcast_vital", broadcast_mock)

    # Step 2: Invoke streaming handler with payload to trigger both actions
    await service.process_vital_stream(vital_in, user, raw_data='{"type":"bpm"}')

    # Step 3: Verify both persistence and broadcast were executed
    create_mock.assert_awaited_once_with(vital_in, user)
    broadcast_mock.assert_awaited_once_with('{"type":"bpm"}')


@pytest.mark.asyncio
async def test_get_multi_filters_by_type(create_user_func) -> None:
    service = VitalService()
    user = await create_user_func()

    base = datetime(2024, 1, 1, tzinfo=timezone.utc)
    # Seed varied vitals to exercise type filter and ordering
    await service.create(
        VitalCreate(type=VitalType.BPM, value=60, unit="bpm", timestamp=base),
        user,
    )
    await service.create(
        VitalCreate(type=VitalType.SPO2, value=99, unit="%", timestamp=base + timedelta(minutes=1)),
        user,
    )
    await service.create(
        VitalCreate(type=VitalType.BPM, value=80, unit="bpm", timestamp=base + timedelta(minutes=2)),
        user,
    )

    vitals = await service.get_multi(user=user, type=VitalType.BPM, limit=10)

    assert [v.value for v in vitals] == [80, 60]
    assert all(v.type == VitalType.BPM for v in vitals)


@pytest.mark.asyncio
async def test_dashboard_summary_retains_latest_timestamp_when_older_values_present(create_user_func) -> None:
    service = VitalService()
    user = await create_user_func()

    newest = datetime(2024, 2, 1, 12, 0, tzinfo=timezone.utc)
    older = newest - timedelta(days=1)

    # Seed a newer ECG and older blood pressure to ensure newest timestamp wins
    await service.create(
        VitalCreate(type=VitalType.ECG, value=1.23, unit="mv", timestamp=newest),
        user,
    )
    await service.create(
        VitalCreate(type=VitalType.BLOOD_PRESSURE, value=110, unit="mmHg", timestamp=older),
        user,
    )

    summary = await service.get_dashboard_summary(user)

    assert summary.lastUpdated == newest
    assert summary.vitals.ecg == "1.23"
    assert summary.vitals.bloodPressure == "110.0 mmHg"


@pytest.mark.asyncio
async def test_format_dashboard_value_ecg_stringifies(create_user_func) -> None:
    service = VitalService()
    user = await create_user_func()
    vital = Vital(
        type=VitalType.ECG,
        value=3.14,
        unit="mv",
        user=user,
        timestamp=datetime.now(timezone.utc),
    )

    assert service._format_dashboard_value("ecg", vital) == "3.14"


@pytest.mark.asyncio
async def test_connection_manager_handles_connections_and_failed_broadcast() -> None:
    manager = VitalConnectionManager()
    mobile_ws = _FakeWebSocket()
    # Track mobile lifecycle
    await manager.connect_mobile(mobile_ws)
    assert mobile_ws.accepted
    assert mobile_ws in manager.mobile_connections
    manager.disconnect_mobile(mobile_ws)
    assert mobile_ws not in manager.mobile_connections

    # Broadcast should deliver to healthy frontends and drop broken ones
    good = _FakeWebSocket()
    bad = _FakeWebSocket(should_fail=True)
    await manager.connect_frontend(good)
    await manager.connect_frontend(bad)

    await manager.broadcast_vital("payload")
    assert good.sent == ["payload"]
    assert bad not in manager.frontend_connections

    manager.disconnect_frontend(good)
    assert not manager.frontend_connections
