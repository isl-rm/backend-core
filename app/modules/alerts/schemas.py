from datetime import datetime
from typing import Any

from pydantic import Field

from app.shared.schemas import CamelModel


class AlertPayload(CamelModel):
    """Outbound alert payload for WebSocket consumers."""

    event: str
    alert_id: str
    tier: str
    patient_id: str
    vital_type: str
    vitals_window: list[float]
    threshold: dict[str, float | None]
    reasons: list[str]
    recipients: list[str]
    timestamp: datetime
    context: dict[str, Any] | None = None
    source: str = "mock_ai"


class AlertAckPayload(CamelModel):
    """Ack payload broadcast after patient acknowledgment."""

    event: str = "alert_acknowledged"
    alert_id: str
    patient_id: str
    tier: str
    timestamp: datetime
    acknowledged_by: str
    status: str | None = None
    note: str | None = None


class AlertAcknowledgmentRequest(CamelModel):
    """HTTP request body for acknowledging alerts (SSE clients)."""

    status: str | None = Field(None, description="Acknowledgment status (e.g., 'resolved', 'reviewing')")
    note: str | None = Field(None, description="Optional note from the acknowledging user")

