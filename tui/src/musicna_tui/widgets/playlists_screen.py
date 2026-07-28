"""플레이리스트 모달 — 내 플레이리스트 목록에서 골라 바로 재생."""

from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.widgets import DataTable

from musicna_tui.client import ApiClient


class PlaylistsScreen(ModalScreen[None]):
    """`GET /player/playlists` 목록을 표로 보여주고, Enter로 선택한 플레이리스트를 재생한다."""

    BINDINGS = [("escape", "dismiss_screen", "닫기")]

    def __init__(self, client: ApiClient) -> None:
        super().__init__()
        self.client = client

    def compose(self) -> ComposeResult:
        yield DataTable(cursor_type="row")

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.add_columns("이름", "소유자")
        try:
            playlists = self.client.player_playlists()
        except Exception:
            playlists = []
        for p in playlists:
            try:
                table.add_row(p["name"], p.get("owner") or "-", key=p["id"])
            except Exception:
                continue
        table.focus()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        playlist_id = event.row_key.value
        try:
            self.client.player_play_playlist(playlist_id)
        except Exception:
            pass
        self.dismiss()

    def action_dismiss_screen(self) -> None:
        self.dismiss()
