"""SessionStatus 위젯 테스트 — Textual Pilot + 가짜 ApiClient."""

import pytest
from textual.app import App, ComposeResult

from musicna_tui.widgets.session_status import SessionStatus


class _FakeClient:
    def __init__(self, status):
        self._status = status

    def system_status(self):
        return self._status


class _StatusApp(App):
    def __init__(self, client):
        super().__init__()
        self.client = client

    def compose(self) -> ComposeResult:
        yield SessionStatus(self.client)


@pytest.mark.asyncio
async def test_shows_daemon_on_and_capturing():
    client = _FakeClient({"spotify_player_daemon": True, "session_capturing": True})
    app = _StatusApp(client)
    async with app.run_test() as pilot:
        await pilot.pause()
        widget = pilot.app.query_one(SessionStatus)
        rendered = str(widget.render())
        assert "켜짐" in rendered
        assert "녹음 중" in rendered


@pytest.mark.asyncio
async def test_shows_daemon_off_and_idle():
    client = _FakeClient({"spotify_player_daemon": False, "session_capturing": False})
    app = _StatusApp(client)
    async with app.run_test() as pilot:
        await pilot.pause()
        widget = pilot.app.query_one(SessionStatus)
        rendered = str(widget.render())
        assert "꺼짐" in rendered
        assert "대기" in rendered


@pytest.mark.asyncio
async def test_status_fetch_error_shows_message():
    class _BrokenClient(_FakeClient):
        def system_status(self):
            raise RuntimeError("connection refused")

    app = _StatusApp(_BrokenClient(None))
    async with app.run_test() as pilot:
        await pilot.pause()
        widget = pilot.app.query_one(SessionStatus)
        assert "가져올 수 없습니다" in str(widget.render())
