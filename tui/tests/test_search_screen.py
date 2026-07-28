"""SearchScreen 테스트 — Textual Pilot + 가짜 ApiClient."""

import pytest
from textual.app import App, ComposeResult
from textual.widgets import DataTable, Input

from musicna_tui.widgets.search_screen import SearchScreen


class _FakeClient:
    def __init__(self, results=None):
        self._results = results or {"tracks": [], "artists": [], "albums": [], "playlists": []}
        self.played = []

    def player_search(self, query):
        self._last_query = query
        return self._results

    def player_play_playlist(self, playlist_id):
        self.played.append(playlist_id)


class _HostApp(App):
    def __init__(self, client):
        super().__init__()
        self.client = client

    def compose(self) -> ComposeResult:
        yield from ()


@pytest.mark.asyncio
async def test_submitting_query_populates_results_table():
    client = _FakeClient(results={
        "tracks": [{"id": "t1", "name": "Song", "artists": ["A"], "album": "Al", "duration_s": 200.0}],
        "artists": [{"id": "a1", "name": "Artist"}],
        "albums": [{"id": "al1", "name": "Album"}],
        "playlists": [{"id": "p1", "name": "Playlist", "owner": "Me"}],
    })
    app = _HostApp(client)
    async with app.run_test() as pilot:
        await pilot.app.push_screen(SearchScreen(client))
        await pilot.pause()
        input_widget = pilot.app.screen.query_one(Input)
        input_widget.value = "test"
        input_widget.post_message(Input.Submitted(input_widget, "test", None))
        await pilot.pause()
        table = pilot.app.screen.query_one(DataTable)
        assert table.row_count == 4  # 트랙 1 + 아티스트 1 + 앨범 1 + 플레이리스트 1


@pytest.mark.asyncio
async def test_selecting_playlist_row_plays_it_and_dismisses():
    client = _FakeClient(results={
        "tracks": [], "artists": [], "albums": [],
        "playlists": [{"id": "p1", "name": "Playlist", "owner": "Me"}],
    })
    app = _HostApp(client)
    async with app.run_test() as pilot:
        await pilot.app.push_screen(SearchScreen(client))
        await pilot.pause()
        input_widget = pilot.app.screen.query_one(Input)
        input_widget.post_message(Input.Submitted(input_widget, "test", None))
        await pilot.pause()
        table = pilot.app.screen.query_one(DataTable)
        table.focus()
        await pilot.press("enter")
        await pilot.pause()
        assert client.played == ["p1"]
        assert len(pilot.app.screen_stack) == 1


@pytest.mark.asyncio
async def test_selecting_track_row_does_not_play_anything():
    """설계 스펙 범위: 트랙/아티스트/앨범 결과는 열람만 가능, 재생 동작 없음."""
    client = _FakeClient(results={
        "tracks": [{"id": "t1", "name": "Song", "artists": ["A"], "album": "Al", "duration_s": 200.0}],
        "artists": [], "albums": [], "playlists": [],
    })
    app = _HostApp(client)
    async with app.run_test() as pilot:
        await pilot.app.push_screen(SearchScreen(client))
        await pilot.pause()
        input_widget = pilot.app.screen.query_one(Input)
        input_widget.post_message(Input.Submitted(input_widget, "test", None))
        await pilot.pause()
        table = pilot.app.screen.query_one(DataTable)
        table.focus()
        await pilot.press("enter")
        await pilot.pause()
        assert client.played == []
