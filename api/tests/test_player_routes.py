"""player.py의 /player/* 엔드포인트 — FastAPI TestClient, player 함수들은 모킹."""

import pytest
from fastapi.testclient import TestClient

from musicna_api import player
from musicna_api.player import PlayerDevice, PlayerStatus, SpotifyPlayerError


@pytest.fixture
def client():
    import musicna_api.main as main
    return TestClient(main.app)


def test_play_returns_ok(monkeypatch, client):
    monkeypatch.setattr(player, "play", lambda: None)
    r = client.post("/player/play")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_play_failure_returns_503(monkeypatch, client):
    def _raise():
        raise SpotifyPlayerError("daemon not running")
    monkeypatch.setattr(player, "play", _raise)
    r = client.post("/player/play")
    assert r.status_code == 503
    assert "daemon not running" in r.json()["detail"]


def test_pause_returns_ok(monkeypatch, client):
    monkeypatch.setattr(player, "pause", lambda: None)
    assert client.post("/player/pause").status_code == 200


def test_next_returns_ok(monkeypatch, client):
    monkeypatch.setattr(player, "next_track", lambda: None)
    assert client.post("/player/next").status_code == 200


def test_previous_returns_ok(monkeypatch, client):
    monkeypatch.setattr(player, "previous_track", lambda: None)
    assert client.post("/player/previous").status_code == 200


def test_volume_valid_returns_ok(monkeypatch, client):
    calls = []
    monkeypatch.setattr(player, "set_volume", lambda p: calls.append(p))
    r = client.post("/player/volume", params={"percent": 60})
    assert r.status_code == 200
    assert calls == [60]


def test_volume_out_of_range_returns_400(monkeypatch, client):
    def _raise(p):
        raise ValueError("out of range")
    monkeypatch.setattr(player, "set_volume", _raise)
    r = client.post("/player/volume", params={"percent": 999})
    assert r.status_code == 400


def test_devices_returns_list(monkeypatch, client):
    monkeypatch.setattr(player, "list_devices",
                         lambda: [PlayerDevice(id="d1", name="spotify-player", is_active=True)])
    r = client.get("/player/devices")
    assert r.status_code == 200
    assert r.json()[0]["id"] == "d1"


def test_connect_returns_ok(monkeypatch, client):
    calls = []
    monkeypatch.setattr(player, "connect_device", lambda device_id: calls.append(device_id))
    r = client.post("/player/connect", params={"device_id": "d1"})
    assert r.status_code == 200
    assert calls == ["d1"]


def test_status_returns_player_status(monkeypatch, client):
    monkeypatch.setattr(player, "get_status",
                         lambda: PlayerStatus(is_playing=True, item_title="X"))
    r = client.get("/player/status")
    assert r.status_code == 200
    assert r.json()["item_title"] == "X"


def test_status_returns_null_when_nothing_playing(monkeypatch, client):
    monkeypatch.setattr(player, "get_status", lambda: None)
    r = client.get("/player/status")
    assert r.status_code == 200
    assert r.json() is None


from musicna_api.player import Playlist, SearchResults


def test_search_returns_results(monkeypatch, client):
    monkeypatch.setattr(
        player, "search",
        lambda query: SearchResults(playlists=[{"id": "p1", "name": "X", "owner": None}]),
    )
    r = client.get("/player/search", params={"query": "test"})
    assert r.status_code == 200
    assert r.json()["playlists"][0]["id"] == "p1"


def test_search_failure_returns_503(monkeypatch, client):
    def _raise(query):
        raise SpotifyPlayerError("no active device")
    monkeypatch.setattr(player, "search", _raise)
    r = client.get("/player/search", params={"query": "test"})
    assert r.status_code == 503


def test_playlists_returns_list(monkeypatch, client):
    monkeypatch.setattr(player, "list_playlists",
                         lambda: [Playlist(id="p1", name="X", owner="Y", collaborative=False)])
    r = client.get("/player/playlists")
    assert r.status_code == 200
    assert r.json()[0]["id"] == "p1"


def test_play_playlist_returns_ok(monkeypatch, client):
    calls = []
    monkeypatch.setattr(player, "play_playlist", lambda playlist_id: calls.append(playlist_id))
    r = client.post("/player/playlists/p1/play")
    assert r.status_code == 200
    assert calls == ["p1"]


def test_play_playlist_failure_returns_503(monkeypatch, client):
    def _raise(playlist_id):
        raise SpotifyPlayerError("daemon not running")
    monkeypatch.setattr(player, "play_playlist", _raise)
    r = client.post("/player/playlists/p1/play")
    assert r.status_code == 503
