import json
from pathlib import Path

import structlog
from pydantic import Field

from app.shared.schemas import CamelModel

log = structlog.get_logger()


class VitalThresholdConfig(CamelModel):
    min: float | None = None
    max: float | None = None


class VitalRuleConfig(CamelModel):
    unit: str | None = None
    levels: dict[str, VitalThresholdConfig] = Field(default_factory=dict)


class AlertLevelConfig(CamelModel):
    name: str
    priority: int = 0
    consecutive_samples: int = Field(default=3, ge=1)
    initial_recipients: list[str] = Field(default_factory=lambda: ["patient"])
    escalation_recipients: list[str] = Field(default_factory=list)
    escalate_after_seconds: int = Field(default=30, ge=0)


class AlertRulesConfig(CamelModel):
    version: str = "mock-v1"
    stale_after_seconds: int = 120
    max_sample_age_seconds: int = 120
    levels: list[AlertLevelConfig] = Field(default_factory=list)
    vitals: dict[str, VitalRuleConfig] = Field(default_factory=dict)

    def levels_by_priority(self) -> list[AlertLevelConfig]:
        return sorted(self.levels, key=lambda level: level.priority, reverse=True)


DEFAULT_RULES = AlertRulesConfig(
    levels=[
        AlertLevelConfig(
            name="slight",
            priority=1,
            consecutive_samples=3,
            initial_recipients=["patient"],
            escalation_recipients=["caregiver"],
            escalate_after_seconds=30,
        ),
        AlertLevelConfig(
            name="moderate",
            priority=2,
            consecutive_samples=3,
            initial_recipients=["patient"],
            escalation_recipients=["caregiver", "dispatcher"],
            escalate_after_seconds=30,
        ),
        AlertLevelConfig(
            name="critical",
            priority=3,
            consecutive_samples=3,
            initial_recipients=["patient"],
            escalation_recipients=["caregiver", "dispatcher", "hospital"],
            escalate_after_seconds=30,
        ),
    ],
    vitals={
        "heart_rate": VitalRuleConfig(
            unit="bpm",
            levels={
                "slight": VitalThresholdConfig(min=55, max=120),
                "moderate": VitalThresholdConfig(min=50, max=140),
                "critical": VitalThresholdConfig(min=40, max=180),
            },
        )
    },
)


def load_rules(path: Path) -> AlertRulesConfig:
    try:
        payload = json.loads(path.read_text())
        return AlertRulesConfig.model_validate(payload)
    except FileNotFoundError:
        log.info("alert rules file not found, using defaults", path=str(path))
        return DEFAULT_RULES
    except Exception as exc:
        log.warning("alert rules load failed, using defaults", path=str(path), error=str(exc))
        return DEFAULT_RULES
