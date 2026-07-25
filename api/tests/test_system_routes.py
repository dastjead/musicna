"""system.py의 /system/* 엔드포인트 — FastAPI TestClient, orchestrator는 모킹."""

import pytest
from fastapi.testclient import TestClient

from musicna_api import player, system
from musicna_api.system import SystemStatus


@pytest.fixture
def client():
    import musicna_api.main as main
    return TestClient(main.app)


def test_start_returns_status(monkeypatch, client):
    monkeypatch.setattr(system.orchestrator, "start", lambda: None)
    monkeypatch.setattr(system.orchestrator, "status",
                         lambda: SystemStatus(spotify_player_daemon=True, session_capturing=True))
    r = client.post("/system/start")
    assert r.status_code == 200
    assert r.json() == {"spotify_player_daemon": True, "session_capturing": True}


def test_start_failure_returns_503(monkeypatch, client):
    def _raise():
        raise player.SpotifyPlayerError("brew install spotify_player 필요")
    monkeypatch.setattr(system.orchestrator, "start", _raise)
    r = client.post("/system/start")
    assert r.status_code == 503


def test_stop_returns_status(monkeypatch, client):
    monkeypatch.setattr(system.orchestrator, "stop", lambda: None)
    monkeypatch.setattr(system.orchestrator, "status",
                         lambda: SystemStatus(spotify_player_daemon=False, session_capturing=False))
    r = client.post("/system/stop")
    assert r.status_code == 200
    assert r.json()["session_capturing"] is False


def test_status_returns_current_state(monkeypatch, client):
    monkeypatch.setattr(system.orchestrator, "status",
                         lambda: SystemStatus(spotify_player_daemon=False, session_capturing=False))
    r = client.get("/system/status")
    assert r.status_code == 200
    assert r.json() == {"spotify_player_daemon": False, "session_capturing": False}
