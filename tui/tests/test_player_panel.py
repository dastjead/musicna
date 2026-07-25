"""PlayerPanel 위젯 테스트 — Textual Pilot + 가짜 ApiClient."""

import pytest
from textual.app import App, ComposeResult

from musicna_tui.widgets.player_panel import PlayerPanel


class _FakeClient:
    def __init__(self, status=None):
        self._status = status
        self.play_calls = 0
        self.pause_calls = 0
        self.next_calls = 0
        self.previous_calls = 0

    def player_status(self):
        return self._status

    def player_play(self):
        self.play_calls += 1
        if self._status:
            self._status["is_playing"] = True

    def player_pause(self):
        self.pause_calls += 1
        if self._status:
            self._status["is_playing"] = False

    def player_next(self):
        self.next_calls += 1

    def player_previous(self):
        self.previous_calls += 1


class _PanelApp(App):
    def __init__(self, client):
        super().__init__()
        self.client = client

    def compose(self) -> ComposeResult:
        yield PlayerPanel(self.client)


@pytest.mark.asyncio
async def test_shows_no_track_when_status_none():
    app = _PanelApp(_FakeClient(status=None))
    async with app.run_test() as pilot:
        await pilot.pause()
        panel = pilot.app.query_one(PlayerPanel)
        assert "재생 중인 곡 없음" in str(panel.render())


@pytest.mark.asyncio
async def test_shows_track_title_and_artist():
    status = {"is_playing": True, "item_title": "Test Track", "item_artist": "Test Artist",
              "volume_percent": 50}
    app = _PanelApp(_FakeClient(status=status))
    async with app.run_test() as pilot:
        await pilot.pause()
        panel = pilot.app.query_one(PlayerPanel)
        rendered = str(panel.render())
        assert "Test Track" in rendered
        assert "Test Artist" in rendered


@pytest.mark.asyncio
async def test_space_toggles_play_pause():
    status = {"is_playing": False, "item_title": "X", "item_artist": "Y", "volume_percent": 50}
    client = _FakeClient(status=status)
    app = _PanelApp(client)
    async with app.run_test() as pilot:
        await pilot.pause()
        pilot.app.query_one(PlayerPanel).focus()
        await pilot.press("space")
        assert client.play_calls == 1
        assert client.pause_calls == 0


@pytest.mark.asyncio
async def test_n_key_skips_next():
    client = _FakeClient(status={"is_playing": True, "item_title": "X", "volume_percent": 50})
    app = _PanelApp(client)
    async with app.run_test() as pilot:
        await pilot.pause()
        pilot.app.query_one(PlayerPanel).focus()
        await pilot.press("n")
        assert client.next_calls == 1


@pytest.mark.asyncio
async def test_p_key_goes_previous():
    client = _FakeClient(status={"is_playing": True, "item_title": "X", "volume_percent": 50})
    app = _PanelApp(client)
    async with app.run_test() as pilot:
        await pilot.pause()
        pilot.app.query_one(PlayerPanel).focus()
        await pilot.press("p")
        assert client.previous_calls == 1


@pytest.mark.asyncio
async def test_status_fetch_error_shows_message():
    class _BrokenClient(_FakeClient):
        def player_status(self):
            raise RuntimeError("connection refused")

    app = _PanelApp(_BrokenClient())
    async with app.run_test() as pilot:
        await pilot.pause()
        panel = pilot.app.query_one(PlayerPanel)
        assert "api 연결" in str(panel.render())
