from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock

import pytest

from app.modules.vitals.models import Vital, VitalType
from app.modules.vitals.schemas import (
    BloodPressureReading,
    DashboardVitals,
    VitalBulkCreate,
    VitalCreate,
    VitalSeriesResponse,
)
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
async def test_get_multi_filters_by_date_range(create_user_func) -> None:
    service = VitalService()
    user = await create_user_func()

    base = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)
    before = base - timedelta(days=1)
    inside = base + timedelta(hours=1)
    after = base + timedelta(days=1)

    await service.create(VitalCreate(type=VitalType.BPM, value=60, unit="bpm", timestamp=before), user)
    await service.create(VitalCreate(type=VitalType.BPM, value=70, unit="bpm", timestamp=inside), user)
    await service.create(VitalCreate(type=VitalType.BPM, value=80, unit="bpm", timestamp=after), user)

    vitals = await service.get_multi(
        user=user,
        type=VitalType.BPM,
        start=base,
        end=base + timedelta(hours=2),
    )

    assert [v.value for v in vitals] == [70]


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
        VitalCreate(
            type=VitalType.BLOOD_PRESSURE,
            blood_pressure=BloodPressureReading(systolic=110, diastolic=70),
            unit="mmHg",
            timestamp=older,
        ),
        user,
    )

    summary = await service.get_dashboard_summary(user)

    assert summary.last_updated == newest
    assert summary.vitals.ecg == "1.23"
    assert summary.vitals.blood_pressure == "110/70 mmHg"


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


@pytest.mark.asyncio
async def test_create_bulk_reuses_normalized_now_for_missing_timestamps(create_user_func) -> None:
    service = VitalService()
    user = await create_user_func()

    explicit = datetime(2023, 1, 1, 12, 0, tzinfo=timezone.utc)
    bulk = VitalBulkCreate(
        vitals=[
            VitalCreate(type=VitalType.BPM, value=70, unit="bpm"),
            VitalCreate(type=VitalType.SPO2, value=98, unit="%"),
            VitalCreate(type=VitalType.BPM, value=65, unit="bpm", timestamp=explicit),
        ]
    )

    vitals = await service.create_bulk(bulk, user)

    assert vitals[0].timestamp == vitals[1].timestamp  # both used shared normalized now
    assert vitals[0].timestamp.tzinfo == timezone.utc
    assert vitals[0].timestamp.microsecond == 0
    assert vitals[-1].timestamp == explicit
    assert vitals[-1].value == 65


@pytest.mark.asyncio
async def test_first_available_respects_priority_over_recency(create_user_func) -> None:
    service = VitalService()
    user = await create_user_func()

    older = datetime(2024, 1, 1, tzinfo=timezone.utc)
    newer = older + timedelta(days=1)

    await service.create(
        VitalCreate(type=VitalType.BPM, value=72, unit="bpm", timestamp=newer), user
    )
    await service.create(
        VitalCreate(type=VitalType.HEART_RATE, value=65, unit="bpm", timestamp=older),
        user,
    )

    # Heart rate is chosen even though BPM is newer because it comes first in priority
    chosen = await service._first_available(user=user, types=[VitalType.HEART_RATE, VitalType.BPM])
    assert chosen.type == VitalType.HEART_RATE

    fallback = await service._first_available(user=user, types=[VitalType.TEMPERATURE, VitalType.BPM])
    assert fallback.type == VitalType.BPM


@pytest.mark.asyncio
async def test_create_bumps_cache_versions(
    monkeypatch: pytest.MonkeyPatch, create_user_func
) -> None:
    service = VitalService()
    user = await create_user_func()

    bump_mock = AsyncMock()
    monkeypatch.setattr("app.modules.vitals.service.cache.bump_versions", bump_mock)

    vital_in = VitalCreate(type=VitalType.BPM, value=70, unit="bpm")
    await service.create(vital_in, user)

    bump_mock.assert_awaited_once_with(str(user.id), "bpm")


@pytest.mark.asyncio
async def test_create_bulk_bumps_cache_versions_for_each_type(
    monkeypatch: pytest.MonkeyPatch, create_user_func
) -> None:
    service = VitalService()
    user = await create_user_func()

    bump_mock = AsyncMock()
    monkeypatch.setattr("app.modules.vitals.service.cache.bump_versions", bump_mock)

    bulk = VitalBulkCreate(
        vitals=[
            VitalCreate(type=VitalType.BPM, value=70, unit="bpm"),
            VitalCreate(type=VitalType.SPO2, value=98, unit="%"),
            VitalCreate(type=VitalType.BPM, value=65, unit="bpm"),
        ]
    )

    await service.create_bulk(bulk, user)

    # Called once per unique type in the batch.
    assert bump_mock.await_count == 2
    bump_mock.assert_any_await(str(user.id), "bpm")
    bump_mock.assert_any_await(str(user.id), "spo2")


def test_normalize_and_ensure_utc_helpers() -> None:
    service = VitalService()

    naive = datetime(2024, 1, 1, 12, 0, 0, 123456)
    normalized = service._normalize_timestamp(naive)
    assert normalized.tzinfo == timezone.utc
    assert normalized.microsecond == 0

    offset_dt = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone(timedelta(hours=-5)))
    normalized_offset = service._normalize_timestamp(offset_dt)
    assert normalized_offset.tzinfo == timezone.utc
    assert normalized_offset.hour == 17

    ensured = service._ensure_utc(datetime(2024, 1, 1, 1, 2, 3))
    assert ensured.tzinfo == timezone.utc
    offset_aware = service._ensure_utc(
        datetime(2024, 1, 1, 12, 0, tzinfo=timezone(timedelta(hours=3)))
    )
    assert offset_aware.hour == 9
    assert offset_aware.tzinfo == timezone.utc


@pytest.mark.asyncio
async def test_dashboard_summary_empty_when_no_vitals(create_user_func) -> None:
    service = VitalService()
    user = await create_user_func()

    summary = await service.get_dashboard_summary(user)

    assert summary.status == "empty"
    assert summary.status_note == "No vitals found"
    assert summary.last_updated is None
    assert summary.vitals == DashboardVitals()


@pytest.mark.asyncio
async def test_get_series_switches_between_raw_and_daily_average(create_user_func) -> None:
    service = VitalService()
    user = await create_user_func()
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)

    await service.create(VitalCreate(type=VitalType.BPM, value=60, unit="bpm", timestamp=start), user)
    await service.create(
        VitalCreate(type=VitalType.BPM, value=70, unit="bpm", timestamp=start + timedelta(days=1)),
        user,
    )

    raw = await service.get_series(
        user=user,
        type=VitalType.BPM,
        start=start,
        end=start + timedelta(days=2),
    )
    assert isinstance(raw, VitalSeriesResponse)
    assert raw.mode == "raw"
    assert len(raw.data) == 2
    paged_raw = await service.get_series(
        user=user,
        type=VitalType.BPM,
        start=start,
        end=start + timedelta(days=2),
        limit=1,
        skip=1,
    )
    assert paged_raw.mode == "raw"
    assert len(paged_raw.data) == 1
    assert paged_raw.data[0].value == 60

    averaged = await service.get_series(
        user=user,
        type=VitalType.BPM,
        start=start,
        end=start + timedelta(days=4),
        limit=1,
        skip=1,
    )
    assert averaged.mode == "daily_average"
    assert len(averaged.data) == 1  # paginated slice of day buckets
    assert averaged.data[0].average == pytest.approx(70.0)


@pytest.mark.asyncio
async def test_get_series_rejects_non_numeric_values(create_user_func) -> None:
    service = VitalService()
    user = await create_user_func()
    ts = datetime(2024, 1, 1, tzinfo=timezone.utc)

    await service.create(
        VitalCreate(
            type=VitalType.BLOOD_PRESSURE,
            blood_pressure=BloodPressureReading(systolic=120, diastolic=80),
            unit="mmHg",
            timestamp=ts,
        ),
        user,
    )

    with pytest.raises(ValueError):
        await service.get_series(
            user=user,
            type=VitalType.BLOOD_PRESSURE,
            start=ts,
            end=ts + timedelta(days=7),
        )
