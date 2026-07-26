"""MusicnaApp 테스트 — 상시 api에 접속만 하는 클라이언트(Phase 8.5)."""

import pytest

from musicna_tui.app import DEFAULT_API_URL, MusicnaApp
from musicna_tui.widgets.player_panel import PlayerPanel
from musicna_tui.widgets.session_status import SessionStatus


def test_app_uses_default_api_url_when_env_unset(monkeypatch):
    monkeypatch.delenv("MUSICNA_API_URL", raising=False)
    app = MusicnaApp()
    assert app.client.base_url == DEFAULT_API_URL


def test_app_uses_musicna_api_url_env_var(monkeypatch):
    monkeypatch.setenv("MUSICNA_API_URL", "http://mac-mini.tailnet.ts.net:8000")
    app = MusicnaApp()
    assert app.client.base_url == "http://mac-mini.tailnet.ts.net:8000"


@pytest.mark.asyncio
async def test_app_composes_player_panel_and_session_status(monkeypatch):
    app = MusicnaApp()
    monkeypatch.setattr(app.client, "system_start", lambda: {"spotify_player_daemon": True, "session_capturing": False})
    async with app.run_test() as pilot:
        await pilot.pause()
        assert pilot.app.query_one(PlayerPanel) is not None
        assert pilot.app.query_one(SessionStatus) is not None


@pytest.mark.asyncio
async def test_app_exits_with_message_when_system_start_fails(monkeypatch):
    """system_start 실패(api 연결 불가 등)는 화면 크래시가 아니라 App.exit(message=...) 호출로 종료해야 한다."""
    app = MusicnaApp()

    def _raise():
        raise RuntimeError("연결 실패")

    monkeypatch.setattr(app.client, "system_start", _raise)
    exit_calls = []
    monkeypatch.setattr(app, "exit", lambda *a, **kw: exit_calls.append(kw))

    async with app.run_test() as pilot:
        await pilot.pause()

    assert len(exit_calls) == 1
    assert "연결 실패" in exit_calls[0]["message"]
