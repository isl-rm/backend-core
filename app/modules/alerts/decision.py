from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
from typing import Deque

from app.modules.alerts.config import AlertRulesConfig, VitalThresholdConfig
from app.modules.alerts.models import AlertDecision, VitalSample


class AlertDecisionEngine:
    """Evaluate incoming vitals and return alert decisions when thresholds are met."""

    def __init__(self, rules: AlertRulesConfig) -> None:
        self._rules = rules
        self._buffers: dict[str, dict[str, Deque[VitalSample]]] = {}
        self._max_window = max(
            (level.consecutive_samples for level in rules.levels), default=3
        )

    def evaluate(
        self,
        patient_id: str,
        vital_type: str,
        value: float | str,
        unit: str | None,
        timestamp: datetime | None,
    ) -> AlertDecision | None:
        vital_key = self._normalize_vital_key(vital_type, unit)
        if not vital_key:
            return None
        rule = self._rules.vitals.get(vital_key)
        if not rule:
            return None

        numeric_value = self._as_float(value)
        if numeric_value is None:
            return None

        sample_time = self._ensure_utc(timestamp) or datetime.now(timezone.utc)
        buffer = self._get_buffer(patient_id, vital_key)
        if buffer and (sample_time - buffer[-1].timestamp).total_seconds() > self._rules.stale_after_seconds:
            buffer.clear()
        buffer.append(VitalSample(value=numeric_value, timestamp=sample_time))

        decision = self._evaluate_match(vital_key, rule.levels, buffer)
        if not decision:
            return None
        return decision

    def _evaluate_match(
        self,
        vital_key: str,
        thresholds_by_level: dict[str, VitalThresholdConfig],
        buffer: Deque[VitalSample],
    ) -> AlertDecision | None:
        for level in self._rules.levels_by_priority():
            thresholds = thresholds_by_level.get(level.name)
            if not thresholds:
                continue
            if len(buffer) < level.consecutive_samples:
                continue
            window = list(buffer)[-level.consecutive_samples:]
            if self._window_stale(window):
                continue
            if all(self._outside_threshold(sample.value, thresholds) for sample in window):
                return AlertDecision(
                    level=level,
                    thresholds=thresholds,
                    window=window,
                    vital_key=vital_key,
                    sample_time=window[-1].timestamp,
                )
        return None

    def _get_buffer(self, patient_id: str, vital_key: str) -> Deque[VitalSample]:
        patient_buffers = self._buffers.setdefault(patient_id, {})
        if vital_key not in patient_buffers:
            patient_buffers[vital_key] = deque(maxlen=self._max_window)
        return patient_buffers[vital_key]

    def _window_stale(self, window: list[VitalSample]) -> bool:
        if not window:
            return True
        if len(window) == 1:
            return False
        span_seconds = (window[-1].timestamp - window[0].timestamp).total_seconds()
        return span_seconds > self._rules.max_sample_age_seconds

    @staticmethod
    def _outside_threshold(value: float, thresholds: VitalThresholdConfig) -> bool:
        has_min = thresholds.min is not None
        has_max = thresholds.max is not None
        if not has_min and not has_max:
            return False
        if has_min and value < float(thresholds.min):
            return True
        if has_max and value > float(thresholds.max):
            return True
        return False

    @staticmethod
    def _as_float(value: float | str) -> float | None:
        if isinstance(value, (int, float)):
            return float(value)
        try:
            return float(str(value))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _ensure_utc(value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    @staticmethod
    def _normalize_vital_key(vital_type: str, unit: str | None) -> str | None:
        normalized = vital_type.strip().lower()
        if normalized in {"bpm", "heart_rate"}:
            return "heart_rate"
        if normalized == "ecg" and unit and unit.lower() == "bpm":
            return "heart_rate"
        return normalized
