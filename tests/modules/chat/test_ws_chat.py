from fastapi.testclient import TestClient

from app.main import app
from app.modules.chat.service import manager


def test_chat_websocket_broadcasts_message() -> None:
    manager.active_connections.clear()
    client = TestClient(app)

    with client.websocket_connect("/api/v1/ws/chat/7") as ws:
        ws.send_text("hello")
        data = ws.receive_text()

    assert data == "Client #7 says: hello"
    assert not manager.active_connections
