from datetime import datetime, timedelta, timezone

import pytest

from app.modules.daily_checkin.models import SubstanceStatus, SubstanceUse
from app.modules.daily_checkin.schemas import DailyCheckinUpdate
from app.modules.daily_checkin.service import DailyCheckinService


@pytest.mark.asyncio
async def test_get_or_create_today_populates_defaults(create_user_func) -> None:
    service = DailyCheckinService()
    user = await create_user_func()

    checkin = await service.get_or_create_today(user)

    assert checkin.hydration.goal == service.DEFAULT_HYDRATION_GOAL
    assert len(checkin.daily_plan) == len(service.DEFAULT_PLAN)
    # Repeated call should not duplicate a new record
    same = await service.get_or_create_today(user)
    assert str(checkin.id) == str(same.id)


@pytest.mark.asyncio
async def test_upsert_today_updates_fields(create_user_func) -> None:
    service = DailyCheckinService()
    user = await create_user_func()

    await service.upsert_today(DailyCheckinUpdate(mood=3, craving_score=5), user)
    response = await service.get_today(user)

    assert response.mood == 3
    assert response.craving_score == 5


@pytest.mark.asyncio
async def test_sober_streak_counts_consecutive_safe_days(create_user_func) -> None:
    service = DailyCheckinService()
    user = await create_user_func()

    today = datetime.now(timezone.utc)
    yesterday = today - timedelta(days=1)
    two_days_ago = today - timedelta(days=2)

    # Create three days, with the oldest marked as "used" to break the streak
    await service.upsert_today(
        DailyCheckinUpdate(date=two_days_ago, substance_use={"status": "used"}), user
    )
    await service.upsert_today(DailyCheckinUpdate(date=yesterday), user)
    await service.upsert_today(DailyCheckinUpdate(date=today), user)

    shaped = await service.get_today(user)
    assert shaped.sober_streak_days == 2  # today + yesterday; used day ends the streak


@pytest.mark.asyncio
async def test_increment_helpers_are_non_negative(create_user_func) -> None:
    service = DailyCheckinService()
    user = await create_user_func()

    resp = await service.increment_kicks(user, 2)
    assert resp.kick_count == 2

    resp = await service.increment_hydration(user, -1)  # clamp at zero
    assert resp.hydration.count == 0
