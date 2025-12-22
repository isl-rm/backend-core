from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import Any

import structlog

from app.modules.alerts.config import VitalThresholdConfig
from app.modules.alerts.decision import AlertDecisionEngine
from app.modules.alerts.manager import AlertConnectionManager
from app.modules.alerts.models import AlertDecision, PendingAlert
from app.modules.alerts.schemas import AlertAckPayload, AlertPayload

log = structlog.get_logger()


class AlertService:
    """Alert delivery service that routes decisions and handles escalation/acks."""

    def __init__(
        self, manager: AlertConnectionManager, decision_engine: AlertDecisionEngine
    ) -> None:
        self._manager = manager
        self._decision_engine = decision_engine
        self._pending_alerts: dict[str, PendingAlert] = {}

    async def process_vital(
        self,
        patient_id: str,
        vital_type: str,
        value: float | str,
        unit: str | None,
        timestamp: datetime | None,
        raw_payload: str | None = None,
    ) -> None:
        decision = self._decision_engine.evaluate(
            patient_id=patient_id,
            vital_type=vital_type,
            value=value,
            unit=unit,
            timestamp=timestamp,
        )
        if not decision:
            return

        alert_id = uuid.uuid4().hex
        context = self._extract_context(raw_payload)
        payload = AlertPayload(
            event="alert",
            alert_id=alert_id,
            tier=decision.level.name,
            patient_id=patient_id,
            vital_type=decision.vital_key,
            vitals_window=[sample.value for sample in decision.window],
            threshold={"min": decision.thresholds.min, "max": decision.thresholds.max},
            reasons=[
                self._build_reason(
                    decision.vital_key,
                    decision.level.consecutive_samples,
                    decision.thresholds,
                )
            ],
            recipients=decision.level.initial_recipients,
            timestamp=decision.sample_time,
            context=context,
        )

        await self._manager.send_to_roles(
            patient_id,
            decision.level.initial_recipients,
            payload.model_dump(by_alias=True, mode="json"),
        )

        await self._schedule_escalation(
            alert_id=alert_id,
            patient_id=patient_id,
            vital_type=decision.vital_key,
            tier=decision.level.name,
            recipients=decision.level.initial_recipients,
            escalation_recipients=decision.level.escalation_recipients,
            escalate_after_seconds=decision.level.escalate_after_seconds,
            context=context,
            decision=decision,
        )

    async def acknowledge(
        self,
        alert_id: str,
        patient_id: str,
        recipient_role: str,
        status: str | None = None,
        note: str | None = None,
    ) -> bool:
        pending = self._pending_alerts.get(alert_id)
        if not pending:
            return False
        if pending.patient_id != patient_id:
            return False
        if recipient_role.strip().lower() != "patient":
            return False

        pending.acknowledged = True
        if pending.task and not pending.task.done():
            pending.task.cancel()
        self._pending_alerts.pop(alert_id, None)

        ack_payload = AlertAckPayload(
            alert_id=alert_id,
            patient_id=patient_id,
            tier=pending.tier,
            timestamp=datetime.now(timezone.utc),
            acknowledged_by=recipient_role,
            status=status,
            note=note,
        )
        await self._manager.send_to_roles(
            patient_id,
            list({*pending.initial_recipients, *pending.escalation_recipients}),
            ack_payload.model_dump(by_alias=True, mode="json"),
        )
        return True

    async def _schedule_escalation(
        self,
        alert_id: str,
        patient_id: str,
        vital_type: str,
        tier: str,
        recipients: list[str],
        escalation_recipients: list[str],
        escalate_after_seconds: int,
        context: dict[str, Any] | None,
        decision: AlertDecision,
    ) -> None:
        if not escalation_recipients or escalate_after_seconds <= 0:
            return

        pending = PendingAlert(
            alert_id=alert_id,
            patient_id=patient_id,
            tier=tier,
            vital_type=vital_type,
            initial_recipients=recipients,
            escalation_recipients=escalation_recipients,
            escalate_after_seconds=escalate_after_seconds,
        )
        self._pending_alerts[alert_id] = pending

        async def _escalate() -> None:
            try:
                await asyncio.sleep(escalate_after_seconds)
            except asyncio.CancelledError:
                return
            if pending.acknowledged:
                return
            escalation_payload = AlertPayload(
                event="alert_escalated",
                alert_id=alert_id,
                tier=tier,
                patient_id=patient_id,
                vital_type=vital_type,
                vitals_window=[sample.value for sample in decision.window],
                threshold={"min": decision.thresholds.min, "max": decision.thresholds.max},
                reasons=[
                    self._build_reason(
                        vital_type,
                        decision.level.consecutive_samples,
                        decision.thresholds,
                    )
                ],
                recipients=escalation_recipients,
                timestamp=datetime.now(timezone.utc),
                context=context,
            )
            await self._manager.send_to_roles(
                patient_id,
                escalation_recipients,
                escalation_payload.model_dump(by_alias=True, mode="json"),
            )
            self._pending_alerts.pop(alert_id, None)

        pending.task = asyncio.create_task(_escalate())

    @staticmethod
    def _extract_context(raw_payload: str | None) -> dict[str, Any] | None:
        if not raw_payload:
            return None
        try:
            data = json.loads(raw_payload)
        except json.JSONDecodeError:
            return None
        if not isinstance(data, dict):
            return None

        context: dict[str, Any] = {}
        for key in ("context", "metadata"):
            value = data.get(key)
            if isinstance(value, dict):
                context.update(value)
        age = data.get("age")
        if age is not None:
            context["age"] = age
        return context or None

    @staticmethod
    def _build_reason(
        vital_key: str, window_size: int, thresholds: VitalThresholdConfig
    ) -> str:
        low = thresholds.min
        high = thresholds.max
        if low is not None and high is not None:
            bound = f"{low}-{high}"
        elif low is not None:
            bound = f">= {low}"
        elif high is not None:
            bound = f"<= {high}"
        else:
            bound = "custom bounds"
        return f"{vital_key} outside {bound} for {window_size} samples"
