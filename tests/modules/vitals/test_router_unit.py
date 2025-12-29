from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.main import app
from app.modules.users.models import User
from app.modules.vitals import router
from app.modules.vitals.models import VitalType
from app.modules.vitals.schemas import (
    DashboardSummary,
    VitalBulkCreate,
    VitalCreate,
    VitalsQueryParams,
)


def _fake_user() -> SimpleNamespace:
    return SimpleNamespace(id="user-1", email="unit@example.com")


def _vital_from_create(vital_in: VitalCreate, user: SimpleNamespace) -> SimpleNamespace:
    return SimpleNamespace(
        type=vital_in.type,
        value=vital_in.value,
        unit=vital_in.unit,
        user=user,
        timestamp=datetime.now(timezone.utc),
    )


@pytest.mark.asyncio
async def test_create_vital_delegates_to_service() -> None:
    user = _fake_user()
    vital_in = VitalCreate(type=VitalType.BPM, value=70, unit="bpm")

    class FakeService:
        def __init__(self) -> None:
            self.called_with: tuple[VitalCreate, User] | None = None

        async def create(self, vital_in: VitalCreate, user: User):
            self.called_with = (vital_in, user)
            return _vital_from_create(vital_in, user)

    service = FakeService()
    # Exercise: route should delegate persistence to service
    result = await router.create_vital(vital_in=vital_in, current_user=user, service=service)

    assert service.called_with == (vital_in, user)
    assert result.value == 70


@pytest.mark.asyncio
async def test_create_vitals_bulk_delegates_to_service() -> None:
    user = _fake_user()
    bulk = VitalBulkCreate(
        vitals=[
            VitalCreate(type=VitalType.BPM, value=80, unit="bpm"),
            VitalCreate(type=VitalType.SPO2, value=98, unit="%"),
        ]
    )

    class FakeService:
        def __init__(self) -> None:
            self.called_with: tuple[VitalBulkCreate, User] | None = None

        async def create_bulk(self, bulk_in: VitalBulkCreate, user: User):
            self.called_with = (bulk_in, user)
            return [_vital_from_create(v, user) for v in bulk_in.vitals]

    service = FakeService()
    # Exercise: route should pass bulk payload and user through untouched
    result = await router.create_vitals_bulk(bulk_in=bulk, current_user=user, service=service)

    assert service.called_with == (bulk, user)
    assert [v.type for v in result] == [VitalType.BPM, VitalType.SPO2]


@pytest.mark.asyncio
async def test_read_vitals_forwards_filters() -> None:
    user = _fake_user()

    class FakeService:
        def __init__(self) -> None:
            self.seen: dict[str, object] | None = None

        async def get_multi(
            self,
            user: User,
            type: VitalType | None,
            limit: int,
            skip: int,
            start: datetime | None = None,
            end: datetime | None = None,
        ):
            self.seen = {
                "user": user,
                "type": type,
                "limit": limit,
                "skip": skip,
                "start": start,
                "end": end,
            }
            return [
                _vital_from_create(
                    VitalCreate(type=VitalType.BPM, value=60, unit="bpm"), user
                )
            ]

    service = FakeService()
    # Exercise: ensure filters flow to the service call
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    end = datetime(2024, 1, 2, tzinfo=timezone.utc)
    params = VitalsQueryParams(type=VitalType.BPM, limit=5, skip=1, start=start, end=end)
    result = await router.read_vitals(
        params=params, current_user=user, service=service
    )

    assert service.seen == {
        "user": user,
        "type": VitalType.BPM,
        "limit": 5,
        "skip": 1,
        "start": start,
        "end": end,
    }
    assert result[0].value == 60


@pytest.mark.asyncio
async def test_read_latest_vital_raises_when_missing() -> None:
    user = _fake_user()

    class FakeService:
        async def get_latest(self, user: User, type: VitalType | None):
            return None

    with pytest.raises(HTTPException) as exc:
        await router.read_latest_vital(type=None, current_user=user, service=FakeService())

    assert exc.value.status_code == 404
    assert exc.value.detail == "No vitals found"


@pytest.mark.asyncio
async def test_read_dashboard_summary_returns_service_value() -> None:
    user = _fake_user()
    expected = DashboardSummary(status="ok", status_note="ready")

    class FakeService:
        async def get_dashboard_summary(self, user: User):
            return expected

    result = await router.read_dashboard_summary(current_user=user, service=FakeService())
    assert result is expected


def test_openapi_exposes_date_range_filters() -> None:
    schema = app.openapi()
    path = schema["paths"]["/api/v1/vitals/history"]["get"]
    param_names = {param["name"] for param in path["parameters"]}
    assert {"start", "end", "limit", "skip"}.issubset(param_names)
