"""/live/ingest → /ws/live 브로드캐스트 왕복 테스트."""

import pytest
from fastapi.testclient import TestClient

import musicna_api.main as main


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("MUSICNA_DB", str(tmp_path / "live.db"))
    main._session_factory.cache_clear()
    return TestClient(main.app)


def test_ingest_broadcasts_to_ws_subscriber(client):
    with client.websocket_connect("/ws/live") as ws:
        r = client.post("/live/ingest", json=[
            {"type": "chord", "chord": "Am7", "start_s": 12.0, "confidence": 0.9},
            {"type": "note_on", "index": 1, "pitch": 60, "start_s": 12.1},
        ])
        assert r.status_code == 202
        assert r.json()["accepted"] == 2
        assert r.json()["subscribers"] == 1

        first = ws.receive_json()
        assert first == {"type": "chord", "chord": "Am7", "start_s": 12.0, "confidence": 0.9}
        second = ws.receive_json()
        assert second["type"] == "note_on" and second["pitch"] == 60


def test_ingest_rejects_unknown_event_type(client):
    r = client.post("/live/ingest", json=[{"type": "unknown", "x": 1}])
    assert r.status_code == 422


def test_ingest_without_subscribers_is_accepted(client):
    r = client.post("/live/ingest", json=[{"type": "track_ended"}])
    assert r.status_code == 202
    assert r.json()["subscribers"] == 0
