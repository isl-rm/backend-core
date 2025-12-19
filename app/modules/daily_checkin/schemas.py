from datetime import date, datetime, timezone
from typing import List, Optional
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.modules.daily_checkin.models import (
    DailyPlanItem,
    Hydration,
    SubstanceStatus,
    SubstanceUse,
    Symptom,
)


def _utc_midnight(dt: datetime | date | None = None) -> datetime:
    """Normalize to UTC midnight."""
    if dt is None:
        dt = datetime.now(timezone.utc)
    if isinstance(dt, date) and not isinstance(dt, datetime):
        dt = datetime(dt.year, dt.month, dt.day, tzinfo=timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.replace(hour=0, minute=0, second=0, microsecond=0)


class DailyPlanItemIn(BaseModel):
    """Input shape for daily plan items."""

    id: str = Field(default_factory=lambda: uuid4().hex)
    title: str
    category: Optional[str] = None
    completed: bool = False
    order: int = 0

    model_config = ConfigDict(populate_by_name=True)


class HydrationIn(BaseModel):
    goal: int = Field(default=8, ge=0, le=24)
    count: int = Field(default=0, ge=0)

    model_config = ConfigDict(populate_by_name=True)


class SubstanceUseIn(BaseModel):
    status: SubstanceStatus = SubstanceStatus.SAFE
    used_at: datetime | None = Field(default=None, alias="usedAt")
    substances: list[str] = Field(default_factory=list)

    model_config = ConfigDict(populate_by_name=True)


class DailyCheckinBase(BaseModel):
    """Common fields for create/update operations."""

    pregnancy_week: int | None = Field(default=None, ge=0, alias="pregnancyWeek")
    affirmation: str | None = None
    daily_plan: List[DailyPlanItemIn] | None = Field(default=None, alias="dailyPlan")
    kick_count: int | None = Field(default=None, ge=0, alias="kickCount")
    hydration: HydrationIn | None = None
    craving_score: int | None = Field(default=None, ge=0, le=10, alias="cravingScore")
    symptoms: List[Symptom] | None = None
    mood: int | None = Field(default=None, ge=1, le=5)
    note: str | None = None
    substance_use: SubstanceUseIn | None = Field(default=None, alias="substanceUse")

    model_config = ConfigDict(populate_by_name=True)


class DailyCheckinUpdate(DailyCheckinBase):
    """Upsert today's check-in."""

    date: datetime | date | None = None

    @field_validator("date", mode="before")
    @classmethod
    def parse_date(cls, value: object) -> object:
        if value is None:
            return value
        if isinstance(value, (datetime, date)):
            return _utc_midnight(value)
        return value


class DailyCheckinResponse(BaseModel):
    """Returned shape for a single check-in."""

    id: str
    date: datetime
    pregnancyWeek: int | None = None
    affirmation: str | None = None
    dailyPlan: List[DailyPlanItem] = Field(default_factory=list)
    kickCount: int = 0
    hydration: Hydration = Field(default_factory=Hydration)
    cravingScore: int = 0
    symptoms: List[Symptom] = Field(default_factory=list)
    mood: int | None = None
    note: str | None = None
    substanceUse: SubstanceUse = Field(default_factory=SubstanceUse)
    createdAt: datetime
    updatedAt: datetime
    soberStreakDays: int = 0
    planCompleted: int = 0
    planTotal: int = 0


class IncrementRequest(BaseModel):
    delta: int = Field(default=1, ge=-100, le=100)


class PlanToggleRequest(BaseModel):
    completed: bool = True


class HistoryQuery(BaseModel):
    start: datetime | None = None
    end: datetime | None = None
    limit: int = Field(default=30, ge=1, le=200)
    skip: int = Field(default=0, ge=0)

    @field_validator("start", "end", mode="before")
    @classmethod
    def parse_epoch(cls, value: object) -> object:
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(value, tz=timezone.utc)
        return value

    model_config = ConfigDict(populate_by_name=True)


class HistoryItem(BaseModel):
    """History row shaped for the log table."""

    id: str
    date: datetime
    mood: int | None = None
    cravingScore: int = 0
    substanceStatus: SubstanceStatus
    kickCount: int
    hydrationCount: int
    note: str | None = None
    symptoms: List[Symptom] = Field(default_factory=list)


class HistoryResponse(BaseModel):
    items: List[HistoryItem]
    total: int
