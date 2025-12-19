from datetime import datetime, timedelta, timezone
from typing import List, Optional

from app.modules.daily_checkin.models import (
    DailyCheckin,
    DailyPlanItem,
    Hydration,
    SubstanceStatus,
    SubstanceUse,
    Symptom,
)
from app.modules.daily_checkin.schemas import (
    DailyCheckinResponse,
    DailyCheckinUpdate,
    HistoryItem,
    HistoryQuery,
    HistoryResponse,
)
from app.modules.users.models import User


class DailyCheckinService:
    """Persistence and business logic for daily check-ins."""

    DEFAULT_PLAN = [
        DailyPlanItem(title="Take Prenatal Vitamin", category="meds", order=1),
        DailyPlanItem(
            title="5 min Deep Breathing (Urge Surfing)", category="recovery", order=2
        ),
        DailyPlanItem(title="Eat a protein-rich snack", category="nutrition", order=3),
        DailyPlanItem(title="Feel for baby movements", category="pregnancy", order=4),
    ]
    DEFAULT_HYDRATION_GOAL = 8

    async def get_or_create_today(self, user: User) -> DailyCheckin:
        today = self._today()
        checkin = await self._get_by_date(user, today)
        if checkin:
            return checkin
        checkin = DailyCheckin(
            user=user,
            date=today,
            daily_plan=self._default_plan(),
            hydration=Hydration(goal=self.DEFAULT_HYDRATION_GOAL, count=0),
            craving_score=0,
            kick_count=0,
            substance_use=SubstanceUse(),
        )
        await checkin.insert()
        return checkin

    async def upsert_today(self, payload: DailyCheckinUpdate, user: User) -> DailyCheckinResponse:
        target_date = self._normalize_date(payload.date or self._today())
        checkin = await self._get_by_date(user, target_date)
        if not checkin:
            checkin = DailyCheckin(
                user=user,
                date=target_date,
                daily_plan=self._default_plan(),
                hydration=Hydration(goal=self.DEFAULT_HYDRATION_GOAL, count=0),
                substance_use=SubstanceUse(),
                craving_score=0,
                kick_count=0,
            )

        self._apply_update(checkin, payload)
        await checkin.save()
        return await self._shape_response(checkin, user)

    async def get_today(self, user: User) -> DailyCheckinResponse:
        checkin = await self.get_or_create_today(user)
        return await self._shape_response(checkin, user)

    async def increment_kicks(self, user: User, delta: int) -> DailyCheckinResponse:
        checkin = await self.get_or_create_today(user)
        checkin.kick_count = max(0, checkin.kick_count + delta)
        await checkin.save()
        return await self._shape_response(checkin, user)

    async def increment_hydration(self, user: User, delta: int) -> DailyCheckinResponse:
        checkin = await self.get_or_create_today(user)
        hydration = checkin.hydration or Hydration(goal=self.DEFAULT_HYDRATION_GOAL)
        hydration.count = max(0, hydration.count + delta)
        checkin.hydration = hydration
        await checkin.save()
        return await self._shape_response(checkin, user)

    async def toggle_plan_item(
        self, user: User, item_id: str, completed: bool
    ) -> DailyCheckinResponse:
        checkin = await self.get_or_create_today(user)
        updated = False
        for item in checkin.daily_plan:
            if item.id == item_id:
                item.completed = completed
                updated = True
                break
        if not updated:
            raise ValueError("plan item not found")
        await checkin.save()
        return await self._shape_response(checkin, user)

    async def set_substance_use(
        self, user: User, substance_use: SubstanceUse
    ) -> DailyCheckinResponse:
        checkin = await self.get_or_create_today(user)
        checkin.substance_use = substance_use
        await checkin.save()
        return await self._shape_response(checkin, user)

    async def get_history(
        self,
        user: User,
        params: HistoryQuery,
    ) -> HistoryResponse:
        start = self._normalize_date(params.start) if params.start else None
        end = self._normalize_date(params.end) if params.end else None

        query = DailyCheckin.find(DailyCheckin.user.id == user.id)
        if start:
            query = query.find(DailyCheckin.date >= start)
        if end:
            query = query.find(DailyCheckin.date <= end)

        items = await query.sort("-date").skip(params.skip).limit(params.limit).to_list()
        count_query = DailyCheckin.find(DailyCheckin.user.id == user.id)
        if start:
            count_query = count_query.find(DailyCheckin.date >= start)
        if end:
            count_query = count_query.find(DailyCheckin.date <= end)
        total = len(await count_query.to_list())

        history_items: List[HistoryItem] = []
        for entry in items:
            history_items.append(
                HistoryItem(
                    id=str(entry.id),
                    date=entry.date,
                    mood=entry.mood,
                    craving_score=entry.craving_score,
                    substance_status=entry.substance_use.status,
                    kick_count=entry.kick_count,
                    hydration_count=entry.hydration.count if entry.hydration else 0,
                    note=entry.note,
                    symptoms=entry.symptoms,
                )
            )
        return HistoryResponse(items=history_items, total=total)

    async def _shape_response(
        self, checkin: DailyCheckin, user: User
    ) -> DailyCheckinResponse:
        streak = await self._sober_streak_days(user)
        plan_completed, plan_total = self._plan_progress(checkin.daily_plan)
        return DailyCheckinResponse(
            id=str(checkin.id),
            date=checkin.date,
            pregnancy_week=checkin.pregnancy_week,
            affirmation=checkin.affirmation,
            daily_plan=checkin.daily_plan,
            kick_count=checkin.kick_count,
            hydration=checkin.hydration,
            craving_score=checkin.craving_score,
            symptoms=checkin.symptoms,
            mood=checkin.mood,
            note=checkin.note,
            substance_use=checkin.substance_use,
            created_at=checkin.created_at,
            updated_at=checkin.updated_at,
            sober_streak_days=streak,
            plan_completed=plan_completed,
            plan_total=plan_total,
        )

    def _apply_update(self, checkin: DailyCheckin, payload: DailyCheckinUpdate) -> None:
        if payload.pregnancy_week is not None:
            checkin.pregnancy_week = payload.pregnancy_week
        if payload.affirmation is not None:
            checkin.affirmation = payload.affirmation
        if payload.daily_plan is not None:
            checkin.daily_plan = [DailyPlanItem(**item.model_dump()) for item in payload.daily_plan]
        if payload.kick_count is not None:
            checkin.kick_count = max(0, payload.kick_count)
        if payload.hydration is not None:
            checkin.hydration = Hydration(**payload.hydration.model_dump())
        if payload.craving_score is not None:
            checkin.craving_score = payload.craving_score
        if payload.symptoms is not None:
            checkin.symptoms = payload.symptoms
        if payload.mood is not None:
            checkin.mood = payload.mood
        if payload.note is not None:
            checkin.note = payload.note
        if payload.substance_use is not None:
            checkin.substance_use = SubstanceUse(**payload.substance_use.model_dump())
        if payload.date is not None:
            checkin.date = payload.date

    async def _get_by_date(self, user: User, date: datetime) -> Optional[DailyCheckin]:
        normalized = self._normalize_date(date)
        return await (
            DailyCheckin.find(DailyCheckin.user.id == user.id)
            .find(DailyCheckin.date == normalized)
            .first_or_none()
        )

    async def _sober_streak_days(self, user: User) -> int:
        """Count consecutive SAFE days backwards until a USED day or gap appears."""
        checkins = await (
            DailyCheckin.find(DailyCheckin.user.id == user.id).sort("-date").to_list()
        )
        if not checkins:
            return 0

        streak = 0
        previous_date: datetime | None = None

        for entry in checkins:
            if entry.substance_use.status == SubstanceStatus.USED:
                # Used day breaks the streak
                if previous_date is None or self._days_apart(previous_date, entry.date) <= 1:
                    break
                break
            if previous_date is None:
                streak += 1
                previous_date = entry.date
                continue

            gap = self._days_apart(previous_date, entry.date)
            if gap == 1:
                streak += 1
                previous_date = entry.date
            else:
                break
        return streak

    def _days_apart(self, newer: datetime, older: datetime) -> int:
        return (self._normalize_date(newer).date() - self._normalize_date(older).date()).days

    def _plan_progress(self, plan: List[DailyPlanItem]) -> tuple[int, int]:
        total = len(plan)
        completed = len([item for item in plan if item.completed])
        return completed, total

    def _default_plan(self) -> List[DailyPlanItem]:
        return [
            DailyPlanItem(title=item.title, category=item.category, order=item.order)
            for item in self.DEFAULT_PLAN
        ]

    def _today(self) -> datetime:
        return self._normalize_date(datetime.now(timezone.utc))

    def _normalize_date(self, value: datetime) -> datetime:
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        else:
            value = value.astimezone(timezone.utc)
        return value.replace(hour=0, minute=0, second=0, microsecond=0)
