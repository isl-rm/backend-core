from pathlib import Path

from app.modules.alerts.config import load_rules
from app.modules.alerts.decision import AlertDecisionEngine
from app.modules.alerts.engine import AlertService
from app.modules.alerts.manager import AlertConnectionManager

rules_path = Path(__file__).resolve().parent / "mock_rules.json"
alert_manager = AlertConnectionManager()
decision_engine = AlertDecisionEngine(rules=load_rules(rules_path))
alert_service = AlertService(manager=alert_manager, decision_engine=decision_engine)
