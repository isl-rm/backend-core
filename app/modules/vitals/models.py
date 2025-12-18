from datetime import datetime, timezone
from enum import Enum

from beanie import Document, Link
from pymongo import IndexModel
from pydantic import Field

from app.modules.users.models import User


class VitalType(str, Enum):
    """Supported vital sign measurement types."""

    ECG = "ecg"
    BPM = "bpm"
    GYROSCOPE = "gyroscope"
    HEART_RATE = "heart_rate"
    BLOOD_PRESSURE = "blood_pressure"
    SPO2 = "spo2"
    TEMPERATURE = "temperature_c"
    RESP_RATE = "resp_rate"
    BLOOD_SUGAR = "blood_sugar"
    WEIGHT_KG = "weight_kg"


class Vital(Document):
    """Persisted vital sign measurement associated with a user."""

    type: VitalType
    value: float | str
    unit: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    user: Link[User]

    class Settings:
        name = "vitals"
        indexes = [
            IndexModel(
                [
                    ("user", 1),
                    ("type", 1),
                    ("timestamp", -1),
                ]
            )
        ]
