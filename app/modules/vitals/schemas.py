from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from app.modules.vitals.models import VitalType


class VitalCreate(BaseModel):
    """Inbound payload for a single vital measurement."""

    type: VitalType
    value: float
    unit: str
    timestamp: Optional[datetime] = None
    # Allow integer/float epoch seconds as timestamp input
    @field_validator("timestamp", mode="before")
    @classmethod
    def parse_epoch_timestamp(cls, value: object) -> object:
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(value, tz=timezone.utc)
        return value


class VitalBulkCreate(BaseModel):
    """Inbound payload for batching multiple vital measurements."""

    vitals: list[VitalCreate] = Field(default_factory=list)

    @field_validator("vitals")
    @classmethod
    def ensure_non_empty(cls, value: list[VitalCreate]) -> list[VitalCreate]:
        if not value:
            raise ValueError("vitals list cannot be empty")
        return value


class DashboardVitals(BaseModel):
    """Latest vitals shaped for the dashboard contract."""

    ecg: str = "0"
    bloodPressure: str = "0"
    heartRate: float = 0.0
    spo2: float = 0.0
    temperatureC: float = 0.0
    respRate: float = 0.0
    bloodSugar: float = 0.0
    weightKg: float = 0.0


class DashboardSummary(BaseModel):
    """Aggregate response for the vitals dashboard."""

    status: str = "empty"
    statusNote: str = "empty"
    lastUpdated: Optional[datetime] = None
    vitals: DashboardVitals = Field(default_factory=DashboardVitals)
