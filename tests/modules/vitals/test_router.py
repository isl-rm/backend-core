from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient

from app.core import security
from app.modules.vitals.models import Vital, VitalType
from app.modules.vitals.schemas import BloodPressureReading, VitalCreate
from app.modules.vitals.service import VitalService


def _auth_headers(user_id: str) -> dict[str, str]:
    token = security.create_access_token(subject=user_id)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_create_and_list_vitals(client: AsyncClient, create_user_func) -> None:
    user = await create_user_func()
    headers = _auth_headers(str(user.id))

    payload = {
        "type": "bpm",
        "value": 72.5,
        "unit": "bpm",
        "timestamp": 1_700_000_000.987,  # epoch seconds to exercise validator
    }

    # Step 1: Create a vital and ensure the endpoint accepts it
    create_resp = await client.post("/api/v1/vitals/", json=payload, headers=headers)
    assert create_resp.status_code == 201

    # Step 2: Verify it persisted with timestamp normalized to second precision
    saved = await Vital.find_one(Vital.user.id == user.id)
    assert saved is not None
    assert saved.type == VitalType.BPM
    assert saved.timestamp.microsecond == 0

    # Step 3: List vitals and confirm the created record is returned
    list_resp = await client.get(
        "/api/v1/vitals/?type=bpm&limit=5&start=1600000000&end=1800000000",
        headers=headers,
    )
    assert list_resp.status_code == 200
    items = list_resp.json()
    assert len(items) == 1
    assert items[0]["value"] == pytest.approx(payload["value"])


@pytest.mark.asyncio
async def test_list_vitals_respects_date_range(
    client: AsyncClient, create_user_func
) -> None:
    user = await create_user_func()
    headers = _auth_headers(str(user.id))
    service = VitalService()

    base = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)
    await service.create(
        VitalCreate(type=VitalType.BPM, value=60, unit="bpm", timestamp=base - timedelta(days=1)),
        user,
    )
    target_ts = base + timedelta(hours=1)
    await service.create(
        VitalCreate(type=VitalType.BPM, value=70, unit="bpm", timestamp=target_ts),
        user,
    )
    await service.create(
        VitalCreate(type=VitalType.BPM, value=80, unit="bpm", timestamp=base + timedelta(days=1)),
        user,
    )

    start = base.isoformat()
    end = (base + timedelta(hours=2)).isoformat()
    resp = await client.get(
        "/api/v1/vitals/",
        params={"type": "bpm", "start": start, "end": end},
        headers=headers,
    )

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["value"] == 70


@pytest.mark.asyncio
async def test_list_vitals_defaults_to_last_day_window(
    client: AsyncClient, create_user_func
) -> None:
    user = await create_user_func()
    headers = _auth_headers(str(user.id))
    service = VitalService()

    now = datetime.now(timezone.utc)
    within_window = now - timedelta(hours=12)
    outside_window = now - timedelta(days=4)

    await service.create(
        VitalCreate(type=VitalType.BPM, value=60, unit="bpm", timestamp=within_window),
        user,
    )
    await service.create(
        VitalCreate(type=VitalType.BPM, value=80, unit="bpm", timestamp=outside_window),
        user,
    )

    resp = await client.get("/api/v1/vitals/", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["value"] == 60


@pytest.mark.asyncio
async def test_bulk_create_and_latest_endpoint(
    client: AsyncClient, create_user_func
) -> None:
    user = await create_user_func()
    headers = _auth_headers(str(user.id))

    bulk_payload = {
        "vitals": [
            {
                "type": "bpm",
                "value": 95,
                "unit": "bpm",
                "timestamp": 1_700_000_500,
            },
            {
                "type": "bpm",
                "value": 101,
                "unit": "bpm",
                "timestamp": 1_700_001_000,
            },
        ]
    }

    # Step 1: Bulk insert and confirm ordering (newest first)
    bulk_resp = await client.post(
        "/api/v1/vitals/bulk", json=bulk_payload, headers=headers
    )
    assert bulk_resp.status_code == 201
    data = bulk_resp.json()
    # Sorted newest first
    assert [item["value"] for item in data] == [101, 95]

    # Step 2: The latest endpoint should surface the newest bulk value
    latest_resp = await client.post("/api/v1/vitals/latest?type=bpm", headers=headers)
    assert latest_resp.status_code == 200
    assert latest_resp.json()["value"] == 101


@pytest.mark.asyncio
async def test_latest_vital_returns_404_when_empty(
    client: AsyncClient, create_user_func
) -> None:
    user = await create_user_func()
    headers = _auth_headers(str(user.id))

    resp = await client.post("/api/v1/vitals/latest", headers=headers)
    assert resp.status_code == 404
    assert resp.json()["detail"] == "No vitals found"


@pytest.mark.asyncio
async def test_dashboard_summary_maps_latest_values(
    client: AsyncClient, create_user_func
) -> None:
    user = await create_user_func()
    headers = _auth_headers(str(user.id))
    service = VitalService()

    base = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    # Seed multiple vitals to ensure the dashboard picks latest per category
    await service.create(
        VitalCreate(
            type=VitalType.BLOOD_PRESSURE,
            blood_pressure=BloodPressureReading(systolic=120, diastolic=80),
            unit="mmHg",
            timestamp=base,
        ),
        user,
    )
    await service.create(
        VitalCreate(
            type=VitalType.BPM,
            value=77,
            unit="bpm",
            timestamp=base + timedelta(minutes=2),
        ),
        user,
    )
    expected_latest = base + timedelta(minutes=5)
    await service.create(
        VitalCreate(
            type=VitalType.TEMPERATURE,
            value=37.2,
            unit="C",
            timestamp=expected_latest,
        ),
        user,
    )

    # Exercise: fetch dashboard summary and validate mapped values/timestamps
    summary_resp = await client.get("/api/v1/vitals/dashboard", headers=headers)
    assert summary_resp.status_code == 200
    summary = summary_resp.json()

    assert summary["status"] == "ok"
    assert summary["statusNote"] == "Latest vitals available"
    assert summary["vitals"]["bloodPressure"] == "120/80 mmHg"
    assert summary["vitals"]["heartRate"] == pytest.approx(77.0)
    assert summary["vitals"]["temperatureC"] == pytest.approx(37.2)

    last_updated_raw = summary["lastUpdated"]
    last_updated = datetime.fromisoformat(last_updated_raw.replace("Z", "+00:00"))
    if last_updated.tzinfo is None:
        last_updated = last_updated.replace(tzinfo=timezone.utc)
    assert last_updated == expected_latest


@pytest.mark.asyncio
async def test_series_returns_raw_within_three_days(
    client: AsyncClient, create_user_func
) -> None:
    user = await create_user_func()
    headers = _auth_headers(str(user.id))
    service = VitalService()

    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    await service.create(VitalCreate(type=VitalType.BPM, value=60, unit="bpm", timestamp=start), user)
    await service.create(
        VitalCreate(type=VitalType.BPM, value=75, unit="bpm", timestamp=start + timedelta(days=2)),
        user,
    )

    resp = await client.get(
        "/api/v1/vitals/series",
        params={
            "type": "bpm",
            "start": start.isoformat(),
            "end": (start + timedelta(days=2, hours=12)).isoformat(),
            "limit": 1,
        },
        headers=headers,
    )

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["mode"] == "raw"
    assert len(payload["data"]) == 1
    assert payload["data"][0]["value"] == 75


@pytest.mark.asyncio
async def test_series_returns_daily_averages_over_three_days(
    client: AsyncClient, create_user_func
) -> None:
    user = await create_user_func()
    headers = _auth_headers(str(user.id))
    service = VitalService()

    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    await service.create(VitalCreate(type=VitalType.BPM, value=60, unit="bpm", timestamp=start), user)
    await service.create(
        VitalCreate(type=VitalType.BPM, value=80, unit="bpm", timestamp=start + timedelta(days=1, hours=2)),
        user,
    )
    await service.create(
        VitalCreate(type=VitalType.BPM, value=70, unit="bpm", timestamp=start + timedelta(days=1, hours=3)),
        user,
    )
    await service.create(
        VitalCreate(type=VitalType.BPM, value=90, unit="bpm", timestamp=start + timedelta(days=4, hours=1)),
        user,
    )

    resp = await client.get(
        "/api/v1/vitals/series",
        params={
            "type": "bpm",
            "start": start.isoformat(),
            "end": (start + timedelta(days=4, hours=12)).isoformat(),
            "limit": 2,
        },
        headers=headers,
    )

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["mode"] == "daily_average"
    averages = payload["data"]
    # Sorted ascending by date buckets, limited to 2 buckets
    assert [item["count"] for item in averages] == [1, 2]
    assert [round(item["average"], 2) for item in averages] == [60.0, 75.0]
