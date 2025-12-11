from datetime import datetime
from enum import Enum

from beanie import Document, Link
from pydantic import Field

from app.modules.users.models import User


class VitalType(str, Enum):
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
    type: VitalType
    value: float
    unit: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    user: Link[User]

    class Settings:
        name = "vitals"
