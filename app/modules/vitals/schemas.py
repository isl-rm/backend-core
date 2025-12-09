from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from app.modules.vitals.models import VitalType


class VitalCreate(BaseModel):
    type: VitalType
    value: float
    unit: str
    timestamp: Optional[datetime] = None
