from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from shakti_seva.data import DATASETS, QueryReceipt
from shakti_seva.hermes import HermesStatus
from shakti_seva.server import GEOSEARCH_AUTOCOMPLETE, GEOSEARCH_SEARCH, ROOT, create_app, geosearch_suggestions
from shakti_seva.trace import sha256_json


class FakeHermes:
    def __init__(self):
        self.inspect_calls = 0

    def inspect(self):
        self.inspect_calls += 1
        return HermesStatus("/fake/hermes", "Hermes Agent v0.test", {"--tui": True}, True, False)


class CandidateClient:
    def query(self, dataset_id, fields, predicate, *, order=None, limit=25):
        if dataset_id == DATASETS["buildings"]:
            rows = [
                {
                    "buildingid": "101",
                    "boro": "QUEENS",
                    "housenumber": "10",
                    "streetname": "SAMPLE STREET",
                    "zip": "11101",
                },
                {
                    "buildingid": "102",
                    "boro": "QUEENS",
                    "housenumber": "10",
                    "streetname": "SAMPLE STREET",
                    "zip": "11102",
                },
            ]
        else:
            rows = []
        return rows, QueryReceipt(
            dataset_id=dataset_id,
            fetched_at="2026-07-15T00:00:00Z",
            fields=fields,
            predicate_hash=sha256_json({"predicate": predicate}),
            row_count=len(rows),
            response_hash=sha256_json(rows),
        )


def test_health_and_ping_use_websocket(tmp_path: Path) -> None:
    hermes = FakeHermes()
    app = create_app(root=ROOT, traces=tmp_path, hermes=hermes)
    with TestClient(app) as client:
        live = client.get("/api/live").json()
        assert live == {"status": "ok", "check": "liveness", "loopback_only": True}
        assert hermes.inspect_calls == 0

        health = client.get("/api/health").json()
        assert health["check"] == "readiness"
        assert health["transport"] == "websocket"
        assert health["loopback_only"] is True
        assert health["hermes"]["ready"] is True
        assert hermes.inspect_calls == 1

        with client.websocket_connect("/ws", headers={"origin": "http://testserver"}) as socket:
            assert socket.receive_json()["type"] == "connection"
            socket.send_json({"type": "ping"})
            assert socket.receive_json() == {"type": "pong"}


def test_address_suggestions_are_proxied_without_trace_storage(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        "shakti_seva.server.geosearch_suggestions",
        lambda query: [{"id": "one", "label": "120 BROADWAY, New York, NY", "query_seen": query}],
    )
    app = create_app(root=ROOT, traces=tmp_path, hermes=FakeHermes())
    with TestClient(app) as client:
        result = client.get("/api/address-suggestions", params={"q": "120 broadway"}).json()
    assert result["provider"] == "NYC GeoSearch"
    assert result["suggestions"][0]["query_seen"] == "120 broadway"
    assert list(tmp_path.iterdir()) == []


def test_geosearch_fallback_never_changes_the_house_number(monkeypatch) -> None:
    def features(endpoint, query):
        assert query == "900 East 9th Street"
        if endpoint == GEOSEARCH_AUTOCOMPLETE:
            return []
        assert endpoint == GEOSEARCH_SEARCH
        return [
            {
                "properties": {"label": "212 EAST 9 STREET, Brooklyn, NY, USA", "housenumber": "212", "street": "EAST 9 STREET", "borough": "Brooklyn"},
                "geometry": {"coordinates": [-73.9, 40.6]},
            },
            {
                "properties": {
                    "label": "900 EAST 9 STREET, Brooklyn, NY, USA",
                    "housenumber": "900",
                    "street": "EAST 9 STREET",
                    "borough": "Brooklyn",
                    "postalcode": "11230",
                    "addendum": {"pad": {"bin": "3000001"}},
                },
                "geometry": {"coordinates": [-73.9, 40.6]},
            },
        ]

    monkeypatch.setattr("shakti_seva.server._geosearch_features", features)
    suggestions = geosearch_suggestions("900 East 9th Street")
    assert [item["house_number"] for item in suggestions] == ["900"]
    assert suggestions[0]["bin"] == "3000001"


def test_websocket_rejects_cross_origin_browser(tmp_path: Path) -> None:
    app = create_app(root=ROOT, traces=tmp_path, hermes=FakeHermes())
    with TestClient(app) as client:
        with pytest.raises(WebSocketDisconnect) as rejected:
            with client.websocket_connect("/ws", headers={"origin": "https://hostile.example"}):
                pass
        assert rejected.value.code == 1008


def test_websocket_has_no_fixture_case_path(tmp_path: Path) -> None:
    app = create_app(root=ROOT, traces=tmp_path, hermes=FakeHermes())
    with TestClient(app) as client:
        with client.websocket_connect("/ws", headers={"origin": "http://testserver"}) as socket:
            socket.receive_json()
            socket.send_json({"type": "fixture"})
            assert socket.receive_json() == {"type": "error", "message": "Unknown socket message type."}
    assert list(tmp_path.iterdir()) == []


def test_ambiguous_address_can_be_confirmed(tmp_path: Path) -> None:
    app = create_app(
        root=ROOT,
        traces=tmp_path,
        hermes=FakeHermes(),
        client_factory=CandidateClient,
    )
    with TestClient(app) as client:
        with client.websocket_connect("/ws", headers={"origin": "http://testserver"}) as socket:
            socket.receive_json()
            socket.send_json(
                {
                    "type": "case",
                    "payload": {"borough": "QUEENS", "house_number": "10", "street_name": "SAMPLE STREET"},
                }
            )
            assert socket.receive_json()["stage"] == "resolving"
            candidates = socket.receive_json()
            assert candidates["type"] == "candidates"
            assert len(candidates["candidates"]) == 2
            socket.send_json({"type": "confirm", "trace_id": candidates["trace_id"], "building_id": "102"})
            assert socket.receive_json()["stage"] == "building"
            result = socket.receive_json()
            assert result["type"] == "case"
            assert result["case"]["building"]["buildingid"] == "102"
            assert "building.confirmed" in [event["kind"] for event in result["trace"]]


def test_static_app_uses_brand_and_socket() -> None:
    html = (ROOT / "static" / "index.html").read_text()
    javascript = (ROOT / "static" / "app.js").read_text()
    assert "Shakti Seva Studio" in html
    assert "/assets/shakti-seva-mark.svg" in html
    assert "new WebSocket" in javascript
    assert "Developer test fixture" not in html
    assert "fixture-button" not in html
    assert "NYC GeoSearch" in javascript
    assert "No City suggestion yet" in javascript
    assert "Ready to search" not in javascript
    assert "One building can answer to two addresses" in html
    assert "registration-and-listing-data.page" in html
    assert "https://www.nyc.gov/content/tenantprotection/pages/" in html
    assert 'type: "confirm"' in javascript
    assert "This public-record lookup does not use AI." in html
    assert 'state.runtime === "serverless"' in javascript
    assert 'fetch("/api/case"' in javascript
    assert 'method: "POST"' in javascript
    assert "Live City data · no AI" in javascript
    assert "Run the local AI edition" in html
