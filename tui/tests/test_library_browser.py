"""LibraryBrowserWidget 테스트 — Textual Pilot + 가짜 ApiClient."""

import pytest
from textual.app import App, ComposeResult
from textual.widgets import DataTable

from musicna_tui.widgets.library_browser import LibraryBrowserWidget


class _FakeClient:
    def __init__(self, tracks=None, raise_on_fetch=False):
        self._tracks = tracks or []
        self._raise = raise_on_fetch

    def tracks(self):
        if self._raise:
            raise RuntimeError("connection refused")
        return self._tracks


class _BrowserApp(App):
    def __init__(self, client):
        super().__init__()
        self.client = client

    def compose(self) -> ComposeResult:
        yield LibraryBrowserWidget(self.client)


@pytest.mark.asyncio
async def test_populates_rows_from_tracks():
    tracks = [
        {"id": 1, "track": {"title": "Song A", "artist": "Artist A"},
         "bpm": 120.0, "key": "C", "mode": "major", "moods": [{"tag": "happy", "score": 0.8}]},
        {"id": 2, "track": {"title": "Song B", "artist": None},
         "bpm": None, "key": None, "mode": None, "moods": []},
    ]
    app = _BrowserApp(_FakeClient(tracks=tracks))
    async with app.run_test() as pilot:
        await pilot.pause()
        table = pilot.app.query_one(LibraryBrowserWidget)
        assert table.row_count == 2
        row0 = table.get_row_at(0)
        assert row0[0] == "Song A"
        assert row0[1] == "Artist A"
        assert row0[2] == "120"
        assert row0[3] == "C major"
        assert row0[4] == "happy"
        row1 = table.get_row_at(1)
        assert row1[1] == "-"
        assert row1[2] == "-"
        assert row1[3] == "-"
        assert row1[4] == "-"


@pytest.mark.asyncio
async def test_shows_error_row_when_fetch_fails():
    app = _BrowserApp(_FakeClient(raise_on_fetch=True))
    async with app.run_test() as pilot:
        await pilot.pause()
        table = pilot.app.query_one(LibraryBrowserWidget)
        assert table.row_count == 1
        assert "api 연결" in table.get_row_at(0)[0]


@pytest.mark.asyncio
async def test_cursor_type_is_row():
    app = _BrowserApp(_FakeClient(tracks=[]))
    async with app.run_test() as pilot:
        await pilot.pause()
        table = pilot.app.query_one(LibraryBrowserWidget)
        assert table.cursor_type == "row"
