from datetime import date, datetime, timezone
from typing import List

from pydantic import AliasChoices, Field, field_validator

from app.modules.daily_checkin.models import (
    DailyPlanItem,
    Hydration,
    SubstanceUse,
    Symptom,
)
from app.shared.schemas import CamelModel


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


class DailyCheckinBase(CamelModel):
    """Common fields for create/update operations."""

    pregnancy_week: int | None = Field(default=None, ge=0, alias="pregnancyWeek")
    affirmation: str | None = None
    daily_plan: List[DailyPlanItem] | None = Field(default=None, alias="dailyPlan")
    kick_count: int | None = Field(default=None, ge=0, alias="kickCount")
    hydration: Hydration | None = None
    craving_score: int | None = Field(default=None, ge=0, le=10, alias="cravingScore")
    symptoms: List[Symptom] | None = None
    mood: int | None = Field(default=None, ge=1, le=5)
    note: str | None = None
    substance_use: SubstanceUse | None = Field(default=None, alias="substanceUse")


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


class DailyCheckinResponse(CamelModel):
    """Returned shape for a single check-in."""

    id: str
    date: datetime
    pregnancy_week: int | None = None
    affirmation: str | None = None
    daily_plan: List[DailyPlanItem] = Field(default_factory=list)
    kick_count: int = 0
    hydration: Hydration = Field(default_factory=Hydration)
    craving_score: int = 0
    symptoms: List[Symptom] = Field(default_factory=list)
    mood: int | None = None
    note: str | None = None
    substance_use: SubstanceUse = Field(default_factory=SubstanceUse)
    created_at: datetime
    updated_at: datetime
    sober_streak_days: int = 0
    plan_completed: int = 0
    plan_total: int = 0


class IncrementRequest(CamelModel):
    delta: int = Field(default=1, ge=-100, le=100)


class PlanItemCreateRequest(CamelModel):
    title: str = Field(..., min_length=1)
    category: str | None = None
    order: int | None = Field(default=None, ge=0)
    completed: bool = False


class PlanItemUpdateRequest(CamelModel):
    title: str | None = Field(default=None, min_length=1)
    category: str | None = None
    order: int | None = Field(default=None, ge=0)
    completed: bool | None = None


class HistoryQuery(CamelModel):
    start: datetime | None = Field(
        default=None,
        description="Start date (ISO 8601 or epoch seconds)",
        validation_alias=AliasChoices("startDate", "start"),
        alias="start",
    )
    end: datetime | None = Field(
        default=None,
        description="End date (ISO 8601 or epoch seconds)",
        validation_alias=AliasChoices("endDate", "end"),
        alias="end",
    )
    limit: int = Field(default=30, ge=1, le=200, description="Maximum items to return")
    skip: int = Field(default=0, ge=0, description="Items to skip for pagination")

    @field_validator("start", "end", mode="before")
    @classmethod
    def parse_epoch(cls, value: object) -> object:
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(value, tz=timezone.utc)
        return value


class HistoryRangeQuery(HistoryQuery):
    start: datetime = Field(
        ...,
        description="Start date (ISO 8601 or epoch seconds)",
        validation_alias=AliasChoices("startDate", "start"),
        alias="start",
    )
    end: datetime = Field(
        ...,
        description="End date (ISO 8601 or epoch seconds)",
        validation_alias=AliasChoices("endDate", "end"),
        alias="end",
    )


class HistoryItem(CamelModel):
    """History row shaped for the log table."""

    id: str
    date: datetime
    mood: int | None = None
    craving_score: int = 0
    substance_use: SubstanceUse
    kick_count: int
    hydration_count: int
    note: str | None = None
    symptoms: List[Symptom] = Field(default_factory=list)


class DailyCheckinHistoryItem(CamelModel):
    id: str
    date: datetime
    pregnancy_week: int | None = None
    affirmation: str | None = None
    daily_plan: List[DailyPlanItem] = Field(default_factory=list)
    kick_count: int = 0
    hydration: Hydration = Field(default_factory=Hydration)
    craving_score: int = 0
    symptoms: List[Symptom] = Field(default_factory=list)
    mood: int | None = None
    note: str | None = None
    substance_use: SubstanceUse = Field(default_factory=SubstanceUse)
    created_at: datetime
    updated_at: datetime
    plan_completed: int = 0
    plan_total: int = 0


class HistoryResponse(CamelModel):
    items: List[HistoryItem]
    total: int


class DailyCheckinHistoryResponse(CamelModel):
    items: List[DailyCheckinHistoryItem]
    total: int
