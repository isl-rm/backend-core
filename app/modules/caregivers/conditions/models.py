from datetime import datetime, timezone
from enum import Enum

from beanie import Document, Insert, Replace, Save, Update, before_event
from pydantic import Field
from pymongo import IndexModel


class ConditionSeverity(str, Enum):
    NORMAL = "normal"
    MODERATE = "moderate"
    CRITICAL = "critical"


class PatientCondition(Document):
    """Latest condition snapshot per patient (single row per patient)."""
    patient_id: str = Field(..., min_length=1)
    severity: ConditionSeverity = ConditionSeverity.NORMAL
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "patient_conditions"
        indexes = [
            IndexModel([("patient_id", 1)], unique=True),
            IndexModel([("severity", 1), ("updated_at", -1)]),
        ]

    @before_event(Insert, Replace, Save, Update)
    def _touch(self) -> None:
        self.updated_at = datetime.now(timezone.utc)
