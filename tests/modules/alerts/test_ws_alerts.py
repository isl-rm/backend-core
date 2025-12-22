from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core import security
from app.main import app
from app.modules.alerts.service import alert_manager
from app.shared.constants import Role, UserStatus


def _reset_alert_manager() -> None:
    alert_manager._connections.clear()


def _mock_user(user_id: str, roles: list[Role]) -> MagicMock:
    user = MagicMock()
    user.id = user_id
    user.roles = roles
    user.status = UserStatus.ACTIVE
    return user


@patch("app.modules.users.models.User.get", new_callable=AsyncMock)
def test_alerts_ws_patient_scopes_to_self(mock_get) -> None:
    _reset_alert_manager()
    mock_get.return_value = _mock_user("user123", [Role.USER])
    token = security.create_access_token(subject="user123")
    client = TestClient(app)

    with client.websocket_connect(
        f"/api/v1/alerts/ws?role=patient&token={token}&patient_id=other"
    ) as ws:
        ws.send_text("ping")
        assert "user123" in alert_manager._connections
        assert "patient" in alert_manager._connections["user123"]

    assert alert_manager._connections == {}


@patch("app.modules.users.models.User.get", new_callable=AsyncMock)
def test_alerts_ws_rejects_missing_role_permission(mock_get) -> None:
    _reset_alert_manager()
    mock_get.return_value = _mock_user("user123", [Role.USER])
    token = security.create_access_token(subject="user123")
    client = TestClient(app)

    with pytest.raises(Exception):
        with client.websocket_connect(
            f"/api/v1/alerts/ws?role=caregiver&token={token}&patient_id=user123"
        ):
            pass

    assert alert_manager._connections == {}


@patch("app.modules.users.models.User.get", new_callable=AsyncMock)
def test_alerts_ws_rejects_missing_patient_id_for_non_patient(mock_get) -> None:
    _reset_alert_manager()
    mock_get.return_value = _mock_user("caregiver1", [Role.CAREGIVER])
    token = security.create_access_token(subject="caregiver1")
    client = TestClient(app)

    with pytest.raises(Exception):
        with client.websocket_connect(
            f"/api/v1/alerts/ws?role=caregiver&token={token}"
        ):
            pass

    assert alert_manager._connections == {}


@patch("app.modules.users.models.User.get", new_callable=AsyncMock)
def test_alerts_ws_admin_allows_wildcard(mock_get) -> None:
    _reset_alert_manager()
    mock_get.return_value = _mock_user("admin1", [Role.ADMIN])
    token = security.create_access_token(subject="admin1")
    client = TestClient(app)

    with client.websocket_connect(
        f"/api/v1/alerts/ws?role=admin&token={token}&patient_id=*"
    ) as ws:
        ws.send_text("ping")
        assert "*" in alert_manager._connections
        assert "admin" in alert_manager._connections["*"]

    assert alert_manager._connections == {}
