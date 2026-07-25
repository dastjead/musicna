"""ApiClient 테스트 — httpx.MockTransport로 실제 서버 없이 요청 형태를 검증."""

import httpx
import pytest

from musicna_tui.client import ApiClient


def _client_with(handler) -> ApiClient:
    return ApiClient(transport=httpx.MockTransport(handler))


def test_health_true_on_200():
    def handler(request):
        assert request.url.path == "/health"
        return httpx.Response(200, json={"status": "ok"})
    assert _client_with(handler).health() is True


def test_health_false_on_connection_error():
    def handler(request):
        raise httpx.ConnectError("refused", request=request)
    assert _client_with(handler).health() is False


def test_player_status_returns_json():
    def handler(request):
        assert request.url.path == "/player/status"
        return httpx.Response(200, json={"is_playing": True, "item_title": "X"})
    status = _client_with(handler).player_status()
    assert status == {"is_playing": True, "item_title": "X"}


def test_player_status_returns_none_when_null():
    def handler(request):
        return httpx.Response(200, json=None)
    assert _client_with(handler).player_status() is None


def test_player_play_posts_to_correct_path():
    calls = []
    def handler(request):
        calls.append((request.method, request.url.path))
        return httpx.Response(200, json={"status": "ok"})
    _client_with(handler).player_play()
    assert calls == [("POST", "/player/play")]


def test_player_pause_posts_to_correct_path():
    calls = []
    def handler(request):
        calls.append(request.url.path)
        return httpx.Response(200, json={"status": "ok"})
    _client_with(handler).player_pause()
    assert calls == ["/player/pause"]


def test_player_next_and_previous():
    calls = []
    def handler(request):
        calls.append(request.url.path)
        return httpx.Response(200, json={"status": "ok"})
    client = _client_with(handler)
    client.player_next()
    client.player_previous()
    assert calls == ["/player/next", "/player/previous"]


def test_player_volume_sends_percent_param():
    def handler(request):
        assert request.url.path == "/player/volume"
        assert request.url.params["percent"] == "55"
        return httpx.Response(200, json={"status": "ok"})
    _client_with(handler).player_volume(55)


def test_system_start_returns_json():
    def handler(request):
        assert request.url.path == "/system/start"
        return httpx.Response(200, json={"spotify_player_daemon": True, "session_capturing": True})
    result = _client_with(handler).system_start()
    assert result["spotify_player_daemon"] is True


def test_system_status_returns_json():
    def handler(request):
        assert request.url.path == "/system/status"
        return httpx.Response(200, json={"spotify_player_daemon": False, "session_capturing": False})
    result = _client_with(handler).system_status()
    assert result["session_capturing"] is False


def test_http_error_raises():
    def handler(request):
        return httpx.Response(503, json={"detail": "daemon not running"})
    with pytest.raises(httpx.HTTPStatusError):
        _client_with(handler).player_play()
