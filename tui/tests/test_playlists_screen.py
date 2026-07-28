"""PlaylistsScreen 테스트 — Textual Pilot + 가짜 ApiClient."""

import pytest
from textual.app import App, ComposeResult
from textual.widgets import DataTable

from musicna_tui.widgets.playlists_screen import PlaylistsScreen


class _FakeClient:
    def __init__(self, playlists=None):
        self._playlists = playlists or []
        self.played = []

    def player_playlists(self):
        return self._playlists

    def player_play_playlist(self, playlist_id):
        self.played.append(playlist_id)


class _HostApp(App):
    def __init__(self, client):
        super().__init__()
        self.client = client

    def compose(self) -> ComposeResult:
        yield from ()


@pytest.mark.asyncio
async def test_lists_playlists_on_mount():
    client = _FakeClient(playlists=[{"id": "p1", "name": "Chill", "owner": "Me"}])
    app = _HostApp(client)
    async with app.run_test() as pilot:
        await pilot.app.push_screen(PlaylistsScreen(client))
        await pilot.pause()
        table = pilot.app.screen.query_one(DataTable)
        assert table.row_count == 1
        assert table.get_row_at(0)[0] == "Chill"


@pytest.mark.asyncio
async def test_enter_plays_selected_playlist_and_dismisses():
    client = _FakeClient(playlists=[{"id": "p1", "name": "Chill", "owner": "Me"}])
    app = _HostApp(client)
    async with app.run_test() as pilot:
        await pilot.app.push_screen(PlaylistsScreen(client))
        await pilot.pause()
        table = pilot.app.screen.query_one(DataTable)
        table.focus()
        await pilot.press("enter")
        await pilot.pause()
        assert client.played == ["p1"]
        assert len(pilot.app.screen_stack) == 1


@pytest.mark.asyncio
async def test_escape_dismisses_without_playing():
    client = _FakeClient(playlists=[{"id": "p1", "name": "Chill", "owner": "Me"}])
    app = _HostApp(client)
    async with app.run_test() as pilot:
        await pilot.app.push_screen(PlaylistsScreen(client))
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
        assert client.played == []
        assert len(pilot.app.screen_stack) == 1
