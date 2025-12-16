from unittest.mock import AsyncMock, patch, MagicMock
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core import security
from app.modules.vitals.service import vital_manager

# Use a mock user object to bypass Pydantic validation complexity
mock_user = MagicMock()
mock_user.id = "user123"
mock_user.email = "test@example.com"

@patch("app.modules.users.models.User.get", new_callable=AsyncMock)
@patch("app.modules.vitals.service.VitalService.create", new_callable=AsyncMock)
def test_vitals_streaming_with_persistence(mock_create, mock_get) -> None:
    """
    Test the full producer-consumer flow with persistence.
    1. Authenticate mobile client.
    2. Send data.
    3. Verify data is 'saved' (service.create called).
    4. Verify data is broadcasted.
    """
    client = TestClient(app)

    # Setup mocks for user lookup and persistence
    mock_get.return_value = mock_user
    mock_create.return_value = None

    # 1. Generate Token
    token = security.create_access_token(subject="user123")
    
    # 2. Connect frontend (consumer)
    # Frontend auth is currently optional/open in the code I wrote (it doesn't check token)
    with client.websocket_connect("/api/v1/vitals/ws/frontend") as frontend_ws:
        
        # 3. Connect mobile (producer) with TOKEN
        with client.websocket_connect(f"/api/v1/vitals/ws/mobile?token={token}") as mobile_ws:
            
            # 4. Mobile sends valid JSON
            payload = '{"type": "bpm", "value": 80, "unit": "bpm"}'
            mobile_ws.send_text(payload)
            
            # 5. Frontend should receive it
            data = frontend_ws.receive_text()
            assert data == payload
            
    # 6. Verify Persistence
    mock_create.assert_awaited_once()
    # Check arguments: ensure user was passed
    args, _ = mock_create.call_args
    # args[0] is vital_in, args[1] is user
    assert args[1] == mock_user

def test_vitals_mobile_auth_failure() -> None:
    """Test connection is rejected without valid token"""
    client = TestClient(app)
    # Attempt connect with bad token should raise through TestClient wrapper
    with pytest.raises(Exception): # TestClient raises generic WebSocketDisconnect or similar on reject
         with client.websocket_connect("/api/v1/vitals/ws/mobile?token=invalid"):
             pass


@patch("app.modules.users.models.User.get", new_callable=AsyncMock)
def test_mobile_ws_rejects_missing_user(mock_get) -> None:
    mock_get.return_value = None
    client = TestClient(app)
    token = security.create_access_token(subject="ghost-user")

    # Auth passes but user lookup fails; connection should be rejected
    with pytest.raises(Exception):
        with client.websocket_connect(f"/api/v1/vitals/ws/mobile?token={token}"):
            pass


@patch("app.modules.users.models.User.get", new_callable=AsyncMock)
@patch("app.modules.vitals.service.VitalService.process_vital_stream", new_callable=AsyncMock)
def test_mobile_ws_ignores_invalid_json(mock_process, mock_get) -> None:
    mock_get.return_value = mock_user
    client = TestClient(app)
    token = security.create_access_token(subject=mock_user.id)

    # Send invalid payload to exercise validation failure path
    with client.websocket_connect(f"/api/v1/vitals/ws/mobile?token={token}") as mobile_ws:
        mobile_ws.send_text("not-json")  # triggers ValidationError/JSONDecodeError path

    mock_process.assert_not_awaited()
    assert not vital_manager.mobile_connections


def test_frontend_ws_connect_and_disconnect() -> None:
    client = TestClient(app)
    # Frontend connects, sends one heartbeat, then disconnects cleanly
    with client.websocket_connect("/api/v1/vitals/ws/frontend") as frontend_ws:
        frontend_ws.send_text("ping")  # satisfy receive loop once

    assert not vital_manager.frontend_connections
