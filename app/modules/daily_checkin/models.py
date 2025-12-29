import logging
from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional
from uuid import uuid4

from beanie import Document, Insert, Link, Replace, Save, Update, before_event
from pydantic import BaseModel, ConfigDict, Field, field_validator
from pymongo import IndexModel

from app.modules.users.models import User


def _utc_today() -> datetime:
    """UTC midnight for the current day."""
    now = datetime.now(timezone.utc)
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


class Symptom(str, Enum):
    """Supported symptom tags for daily check-ins."""

    NAUSEA = "Nausea"
    SHAKING_TREMORS = "Shaking / Tremors"
    SWEATING = "Sweating"
    ANXIETY_PANIC = "Anxiety / Panic"
    IRRITABILITY = "Irritability"
    INSOMNIA = "Insomnia"
    MUSCLE_ACHES = "Muscle Aches"


class SubstanceStatus(str, Enum):
    """Substance use status for the check-in."""

    NOT_USED = "not_used"
    USED = "used"


class DailyPlanItem(BaseModel):
    """Single daily plan item with completion status."""

    id: str = Field(default_factory=lambda: uuid4().hex)
    title: str
    category: Optional[str] = None
    completed: bool = False
    order: int = 0


class Hydration(BaseModel):
    """Hydration progress for the day."""

    goal: int = Field(default=8, ge=0, le=24)
    count: int = Field(default=0, ge=0)


class SubstanceUse(BaseModel):
    """Substance use declaration for the check-in."""

    status: SubstanceStatus = SubstanceStatus.NOT_USED
    used_at: datetime | None = Field(default=None, alias="usedAt")
    substances: list[str] = Field(default_factory=list)

    @field_validator("status", mode="before")
    @classmethod
    def normalize_status(cls, value: object) -> object:
        if isinstance(value, str) and value.lower() == "safe":
            logging.warning("Substance status is set to 'safe' which is not a valid value. Using 'not_used' instead.")
            return SubstanceStatus.NOT_USED
        return value

    model_config = ConfigDict(populate_by_name=True)


class DailyCheckin(Document):
    """Daily recovery and pregnancy check-in."""

    user: Link[User]
    date: datetime = Field(default_factory=_utc_today)
    pregnancy_week: int | None = Field(default=None, ge=0)
    affirmation: str | None = None
    daily_plan: List[DailyPlanItem] = Field(default_factory=list)
    kick_count: int = Field(default=0, ge=0)
    hydration: Hydration = Field(default_factory=Hydration)
    craving_score: int = Field(default=0, ge=0, le=10)
    symptoms: List[Symptom] = Field(default_factory=list)
    mood: int | None = Field(default=None, ge=1, le=5)
    note: str | None = None
    substance_use: SubstanceUse = Field(default_factory=SubstanceUse)

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "daily_checkins"
        indexes = [
            IndexModel([("user", 1), ("date", -1)], unique=True),
            IndexModel([("user", 1), ("substance_use.status", 1), ("date", -1)]),
        ]

    @before_event(Insert, Replace, Save, Update)
    def _touch(self) -> None:
        """Keep timestamps fresh and normalize date to UTC midnight."""
        self.updated_at = datetime.now(timezone.utc)
        if self.date:
            if self.date.tzinfo is None:
                self.date = self.date.replace(tzinfo=timezone.utc)
            else:
                self.date = self.date.astimezone(timezone.utc)
            self.date = self.date.replace(hour=0, minute=0, second=0, microsecond=0)
