"""MusicnaApp·ensure_api_running 테스트."""

import subprocess
import time

import pytest
from textual.app import App

import musicna_tui.app as app_module
from musicna_tui.app import MusicnaApp, ensure_api_running
from musicna_tui.widgets.player_panel import PlayerPanel
from musicna_tui.widgets.session_status import SessionStatus


class _FakeClient:
    def __init__(self, healthy_sequence):
        self._seq = list(healthy_sequence)

    def health(self):
        return self._seq.pop(0) if self._seq else self._seq[-1] if self._seq else True

    def system_start(self):
        return {"spotify_player_daemon": True, "session_capturing": True}

    def player_status(self):
        return None

    def system_status(self):
        return {"spotify_player_daemon": True, "session_capturing": True}

    def close(self):
        pass


def test_ensure_api_running_noop_when_already_healthy(monkeypatch):
    spawned = []
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **kw: spawned.append(1))
    client = _FakeClient(healthy_sequence=[True])
    proc = ensure_api_running(client)
    assert proc is None
    assert spawned == []


def test_ensure_api_running_spawns_when_unhealthy(monkeypatch):
    class _FakeProc:
        def terminate(self):
            pass

    spawned = []
    monkeypatch.setattr(subprocess, "Popen", lambda cmd, **kw: spawned.append(cmd) or _FakeProc())
    monkeypatch.setattr(time, "sleep", lambda s: None)

    client = _FakeClient(healthy_sequence=[False, False, True])
    proc = ensure_api_running(client, timeout=5.0)

    assert proc is not None
    assert "uvicorn" in " ".join(spawned[0])


def test_ensure_api_running_times_out(monkeypatch):
    class _FakeProc:
        def __init__(self):
            self.terminated = False

        def terminate(self):
            self.terminated = True

    fake_proc = _FakeProc()
    monkeypatch.setattr(subprocess, "Popen", lambda cmd, **kw: fake_proc)
    monkeypatch.setattr(time, "sleep", lambda s: None)
    # 항상 unhealthy
    monkeypatch.setattr(time, "monotonic", _make_advancing_clock())

    client = _FakeClient(healthy_sequence=[])
    client.health = lambda: False  # 항상 실패
    with pytest.raises(RuntimeError, match="기동하지"):
        ensure_api_running(client, timeout=0.01)
    assert fake_proc.terminated


def _make_advancing_clock():
    """time.monotonic()이 호출마다 큰 폭으로 흘러 짧은 timeout을 즉시 초과하게 한다."""
    state = {"t": 0.0}

    def _clock():
        state["t"] += 1.0
        return state["t"]

    return _clock


@pytest.mark.asyncio
async def test_app_composes_player_panel_and_session_status(monkeypatch):
    monkeypatch.setattr(app_module, "ensure_api_running", lambda client: None)

    app = MusicnaApp()
    monkeypatch.setattr(app.client, "system_start", lambda: {"spotify_player_daemon": True, "session_capturing": False})
    async with app.run_test() as pilot:
        await pilot.pause()
        assert pilot.app.query_one(PlayerPanel) is not None
        assert pilot.app.query_one(SessionStatus) is not None


@pytest.mark.asyncio
async def test_app_exits_with_message_when_bootstrap_fails(monkeypatch):
    """부트스트랩 실패는 화면 크래시가 아니라 App.exit(message=...) 호출로 종료해야 한다."""
    def _raise(client):
        raise RuntimeError("api 서버가 15.0초 내에 기동하지 않았습니다")

    monkeypatch.setattr(app_module, "ensure_api_running", _raise)

    exit_calls = []
    app = MusicnaApp()
    monkeypatch.setattr(app, "exit", lambda *a, **kw: exit_calls.append(kw))

    async with app.run_test() as pilot:
        await pilot.pause()

    assert len(exit_calls) == 1
    assert "기동하지 않았습니다" in exit_calls[0]["message"]
