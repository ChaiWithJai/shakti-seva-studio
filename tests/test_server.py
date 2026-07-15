from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from shaki_seva.hermes import HermesStatus
from shaki_seva.server import FIXTURE, ROOT, create_app


class FakeHermes:
    def inspect(self):
        return HermesStatus("/fake/hermes", "Hermes Agent v0.test", {"--tui": True}, True, False)


def test_health_and_fixture_use_websocket(tmp_path: Path) -> None:
    app = create_app(root=ROOT, traces=tmp_path, fixture=FIXTURE, hermes=FakeHermes())
    with TestClient(app) as client:
        health = client.get("/api/health").json()
        assert health["transport"] == "websocket"
        assert health["loopback_only"] is True
        assert health["hermes"]["ready"] is True

        with client.websocket_connect("/ws", headers={"origin": "http://testserver"}) as socket:
            assert socket.receive_json()["type"] == "connection"
            socket.send_json({"type": "fixture"})
            progress = socket.receive_json()
            result = socket.receive_json()
            assert progress["stage"] == "curating"
            assert result["type"] == "case"
            assert result["case"]["fixture"] is True
            assert result["case"]["next_step"]["code"] == "urgent_hpd_follow_up"
            assert len(result["trace"]) == 4
            assert "apartment" not in result["case"]["violations"][0]


def test_websocket_rejects_cross_origin_browser(tmp_path: Path) -> None:
    app = create_app(root=ROOT, traces=tmp_path, fixture=FIXTURE, hermes=FakeHermes())
    with TestClient(app) as client:
        with pytest.raises(WebSocketDisconnect) as rejected:
            with client.websocket_connect("/ws", headers={"origin": "https://hostile.example"}):
                pass
        assert rejected.value.code == 1008


def test_static_app_uses_brand_and_socket() -> None:
    html = (ROOT / "static" / "index.html").read_text()
    javascript = (ROOT / "static" / "app.js").read_text()
    assert "Shaki Seva Studio" in html
    assert "/assets/shaki-seva-mark.svg" in html
    assert "new WebSocket" in javascript
    assert "Ask Hermes" in html
