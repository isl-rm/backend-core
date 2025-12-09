from datetime import datetime
from enum import Enum
from typing import Optional
from beanie import Document, Link
from pydantic import Field
from app.models.user import User

class VitalType(str, Enum):
    ECG = "ecg"
    BPM = "bpm"
    GYROSCOPE = "gyroscope"
    HEART_RATE = "heart_rate"

class Vital(Document):
    type: VitalType
    value: float
    unit: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    user: Link[User]

    class Settings:
        name = "vitals"
