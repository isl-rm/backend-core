from datetime import datetime, timezone

import pytest
from bson import ObjectId
from httpx import AsyncClient

from app.core import security
from app.modules.daily_checkin.models import (
    DailyCheckin,
    Hydration,
    SubstanceStatus,
    SubstanceUse,
)
from app.modules.daily_checkin.service import DailyCheckinService


def _auth_headers(user_id: str) -> dict[str, str]:
    token = security.create_access_token(subject=user_id)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_today_endpoint_creates_defaults(client: AsyncClient, create_user_func) -> None:
    user = await create_user_func()
    headers = _auth_headers(str(user.id))

    resp = await client.get("/api/v1/daily-checkin/today", headers=headers)

    assert resp.status_code == 200
    data = resp.json()
    assert data["hydration"]["goal"] == DailyCheckinService.DEFAULT_HYDRATION_GOAL
    assert len(data["dailyPlan"]) == len(DailyCheckinService.DEFAULT_PLAN)


@pytest.mark.asyncio
async def test_upsert_and_increment_routes(client: AsyncClient, create_user_func) -> None:
    user = await create_user_func()
    headers = _auth_headers(str(user.id))

    # Upsert mood and note
    update_payload = {"mood": 4, "note": "Feeling strong", "cravingScore": 3}
    save_resp = await client.put("/api/v1/daily-checkin/today", json=update_payload, headers=headers)
    assert save_resp.status_code == 200

    # Increment kicks and hydration
    kick_resp = await client.patch(
        "/api/v1/daily-checkin/today/kicks", json={"delta": 2}, headers=headers
    )
    water_resp = await client.patch(
        "/api/v1/daily-checkin/today/hydration", json={"delta": 1}, headers=headers
    )

    assert kick_resp.status_code == 200
    assert water_resp.status_code == 200

    final = await client.get("/api/v1/daily-checkin/today", headers=headers)
    data = final.json()
    assert data["kickCount"] == 2
    assert data["hydration"]["count"] == 1
    assert data["mood"] == 4
    assert data["note"] == "Feeling strong"


@pytest.mark.asyncio
async def test_plan_item_add_and_edit(client: AsyncClient, create_user_func) -> None:
    user = await create_user_func()
    headers = _auth_headers(str(user.id))

    today = await client.get("/api/v1/daily-checkin/today", headers=headers)
    assert today.status_code == 200
    data = today.json()
    initial_count = len(data["dailyPlan"])

    add_payload = {"title": "Walk 10 min", "category": "exercise"}
    add_resp = await client.post(
        "/api/v1/daily-checkin/today/plan", json=add_payload, headers=headers
    )
    assert add_resp.status_code == 200
    add_data = add_resp.json()
    assert len(add_data["dailyPlan"]) == initial_count + 1
    new_item = next(item for item in add_data["dailyPlan"] if item["title"] == "Walk 10 min")
    assert new_item["category"] == "exercise"
    assert new_item["completed"] is False
    assert new_item["order"] == initial_count + 1

    update_payload = {"title": "Walk 15 min", "completed": True, "order": 10}
    update_resp = await client.patch(
        f"/api/v1/daily-checkin/today/plan/{new_item['id']}",
        json=update_payload,
        headers=headers,
    )
    assert update_resp.status_code == 200
    update_data = update_resp.json()
    updated_item = next(
        item for item in update_data["dailyPlan"] if item["id"] == new_item["id"]
    )
    assert updated_item["title"] == "Walk 15 min"
    assert updated_item["completed"] is True
    assert updated_item["order"] == 10


@pytest.mark.asyncio
async def test_history_range_endpoint_filters_by_date(
    client: AsyncClient, create_user_func
) -> None:
    user = await create_user_func()
    headers = _auth_headers(str(user.id))

    checkins = [
        DailyCheckin(
            user=user,
            date=datetime(2024, 1, 1, tzinfo=timezone.utc),
            hydration=Hydration(goal=8, count=2),
            substance_use=SubstanceUse(),
        ),
        DailyCheckin(
            user=user,
            date=datetime(2024, 1, 2, tzinfo=timezone.utc),
            hydration=Hydration(goal=8, count=5),
            substance_use=SubstanceUse(),
        ),
        DailyCheckin(
            user=user,
            date=datetime(2024, 1, 5, tzinfo=timezone.utc),
            hydration=Hydration(goal=8, count=1),
            substance_use=SubstanceUse(),
        ),
    ]
    for checkin in checkins:
        await checkin.insert()

    resp = await client.get(
        "/api/v1/daily-checkin/history/range",
        params={
            "start": "2024-01-01T00:00:00Z",
            "end": "2024-01-02T00:00:00Z",
        },
        headers=headers,
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2
    assert data["items"][0]["date"].startswith("2024-01-02")
    assert data["items"][1]["date"].startswith("2024-01-01")


@pytest.mark.asyncio
async def test_substance_use_endpoint_updates_status(
    client: AsyncClient, create_user_func
) -> None:
    user = await create_user_func()
    headers = _auth_headers(str(user.id))

    payload = {
        "status": "used",
        "usedAt": "2024-02-01T10:00:00Z",
        "substances": ["alcohol"],
    }
    resp = await client.patch(
        "/api/v1/daily-checkin/today/substance", json=payload, headers=headers
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["substanceUse"]["status"] == "used"
    assert data["substanceUse"]["usedAt"].startswith("2024-02-01T10:00:00")
    assert data["substanceUse"]["substances"] == ["alcohol"]


@pytest.mark.asyncio
async def test_history_endpoint_lists_items(
    client: AsyncClient, create_user_func
) -> None:
    user = await create_user_func()
    headers = _auth_headers(str(user.id))

    checkins = [
        DailyCheckin(
            user=user,
            date=datetime(2024, 1, 1, tzinfo=timezone.utc),
            hydration=Hydration(goal=8, count=4),
            kick_count=1,
            mood=2,
            substance_use=SubstanceUse(status=SubstanceStatus.NOT_USED),
        ),
        DailyCheckin(
            user=user,
            date=datetime(2024, 1, 2, tzinfo=timezone.utc),
            hydration=Hydration(goal=8, count=1),
            kick_count=3,
            mood=5,
            substance_use=SubstanceUse(status=SubstanceStatus.NOT_USED),
        ),
    ]
    for checkin in checkins:
        await checkin.insert()

    resp = await client.get(
        "/api/v1/daily-checkin/history",
        params={"start": "2024-01-01T00:00:00Z", "end": "2024-01-03T00:00:00Z"},
        headers=headers,
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2
    assert data["items"][0]["date"].startswith("2024-01-02")
    assert data["items"][0]["hydrationCount"] == 1
    assert data["items"][0]["kickCount"] == 3
    assert data["items"][1]["date"].startswith("2024-01-01")
    assert data["items"][1]["hydrationCount"] == 4
    assert data["items"][1]["kickCount"] == 1


@pytest.mark.asyncio
async def test_update_history_checkin_endpoint(
    client: AsyncClient, create_user_func
) -> None:
    user = await create_user_func()
    headers = _auth_headers(str(user.id))

    checkin_id = ObjectId()
    checkin = DailyCheckin(
        id=checkin_id,
        user=user,
        date=datetime(2024, 3, 1, tzinfo=timezone.utc),
        hydration=Hydration(goal=8, count=2),
        mood=2,
        substance_use=SubstanceUse(status=SubstanceStatus.NOT_USED),
    )
    await checkin.insert()

    update_payload = {"mood": 4, "note": "Updated note"}
    resp = await client.put(
        f"/api/v1/daily-checkin/history/{checkin_id}",
        json=update_payload,
        headers=headers,
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["mood"] == 4
    assert data["note"] == "Updated note"
