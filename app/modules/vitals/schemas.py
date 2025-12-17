from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.modules.vitals.models import VitalType


class BloodPressureReading(BaseModel):
    """Structured representation of a blood pressure reading."""

    systolic: int = Field(gt=0)
    diastolic: int = Field(gt=0)

    def as_string(self) -> str:
        return f"{self.systolic}/{self.diastolic}"


class VitalCreate(BaseModel):
    """Inbound payload for a single vital measurement."""

    type: VitalType
    value: float | str | None = None
    unit: str
    timestamp: Optional[datetime] = None
    blood_pressure: BloodPressureReading | None = Field(
        default=None, alias="bloodPressure"
    )

    model_config = ConfigDict(populate_by_name=True)

    # Allow integer/float epoch seconds as timestamp input
    @field_validator("timestamp", mode="before")
    @classmethod
    def parse_epoch_timestamp(cls, value: object) -> object:
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(value, tz=timezone.utc)
        return value

    @model_validator(mode="after")
    def normalize_value(self) -> "VitalCreate":
        if self.type == VitalType.BLOOD_PRESSURE:
            if self.blood_pressure:
                self.value = self.blood_pressure.as_string()
                return self
            if isinstance(self.value, str) and "/" in self.value:
                systolic_raw, diastolic_raw = self.value.split("/", 1)
                systolic = int(systolic_raw)
                diastolic = int(diastolic_raw)
                bp = BloodPressureReading(systolic=systolic, diastolic=diastolic)
                self.blood_pressure = bp
                self.value = bp.as_string()
                return self
            if isinstance(self.value, (int, float)):
                # Preserve provided numeric reading by storing as a string to avoid losing diastolic data.
                self.value = str(self.value)
                return self
            raise ValueError("blood pressure requires systolic/diastolic values")

        if self.value is None:
            raise ValueError("value is required for this vital type")
        if isinstance(self.value, str):
            try:
                self.value = float(self.value)
            except ValueError as exc:
                raise ValueError("value must be numeric for this vital type") from exc
        return self


class EcgStreamPayload(BaseModel):
    """
    Streaming payload for ECG data delivered over WebSocket.

    Supports either a BPM reading, raw waveform samples, or both.
    """

    bpm: float | None = None
    samples: list[float] | None = None
    sample_rate: int = Field(default=250, alias="sampleRate")
    timestamp: Optional[datetime] = None
    value: float | None = None
    unit: str | None = None

    model_config = ConfigDict(populate_by_name=True)

    @field_validator("timestamp", mode="before")
    @classmethod
    def parse_epoch_timestamp(cls, value: object) -> object:
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(value, tz=timezone.utc)
        return value

    @model_validator(mode="before")
    @classmethod
    def lift_nested_payload(cls, data: object) -> object:
        """Allow clients to nest ECG data under a 'payload' key."""
        if not isinstance(data, dict):
            return data
        payload = data.get("payload")
        if isinstance(payload, dict):
            # Payload fields take precedence only when not already provided at the top level
            merged = {**payload, **data}
            return merged
        return data

    @model_validator(mode="after")
    def validate_presence(self) -> "EcgStreamPayload":
        has_bpm_like_value = self.bpm is not None or self.value is not None
        if not has_bpm_like_value and not self.samples:
            raise ValueError("ECG payload must include bpm or samples")
        if self.samples is not None and len(self.samples) == 0:
            raise ValueError("samples cannot be empty when provided")
        if self.sample_rate <= 0:
            raise ValueError("sampleRate must be positive")
        return self


class VitalBulkCreate(BaseModel):
    """Inbound payload for batching multiple vital measurements."""

    vitals: list[VitalCreate] = Field(default_factory=list)

    @field_validator("vitals")
    @classmethod
    def ensure_non_empty(cls, value: list[VitalCreate]) -> list[VitalCreate]:
        if not value:
            raise ValueError("vitals list cannot be empty")
        return value


class VitalsQueryParams(BaseModel):
    """Query params for listing vitals with pagination/filtering."""

    type: Optional[VitalType] = None
    limit: int = Field(default=100, ge=1, le=1000)
    skip: int = Field(default=0, ge=0)
    start: Optional[datetime] = None
    end: Optional[datetime] = None

    @field_validator("start", "end", mode="before")
    @classmethod
    def parse_epoch_timestamp(cls, value: object) -> object:
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(value, tz=timezone.utc)
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value)
            except ValueError:
                # Common case: unencoded '+' in query params becomes a space; recover if possible.
                if " " in value and "+" not in value:
                    try:
                        candidate = value.replace(" ", "+", 1)
                        return datetime.fromisoformat(candidate)
                    except ValueError:
                        pass
        return value

    @model_validator(mode="after")
    def validate_range(self) -> "VitalsQueryParams":
        if self.start and self.end and self.start > self.end:
            raise ValueError("start must be before end")
        return self


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
