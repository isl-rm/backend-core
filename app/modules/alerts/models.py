from dataclasses import dataclass

import asyncio
from datetime import datetime

from app.modules.alerts.config import AlertLevelConfig, VitalThresholdConfig


@dataclass
class VitalSample:
    value: float
    timestamp: datetime


@dataclass
class AlertDecision:
    level: AlertLevelConfig
    thresholds: VitalThresholdConfig
    window: list[VitalSample]
    vital_key: str
    sample_time: datetime


@dataclass
class PendingAlert:
    alert_id: str
    patient_id: str
    tier: str
    vital_type: str
    initial_recipients: list[str]
    escalation_recipients: list[str]
    escalate_after_seconds: int
    acknowledged: bool = False
    task: asyncio.Task | None = None
