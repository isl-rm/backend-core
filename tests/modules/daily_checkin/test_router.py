import pytest
from httpx import AsyncClient

from app.core import security
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
