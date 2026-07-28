"""검색 모달 — 트랙/아티스트/앨범/플레이리스트 열람, 플레이리스트만 선택 시 바로 재생.

설계 범위: `player.py`가 제공하는 재생 액션은 `play_playlist()`뿐이므로(트랙 단건 재생
함수는 이번 Phase 범위 밖), 트랙/아티스트/앨범 결과 행은 열람 전용이다.
"""

from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.widgets import DataTable, Input

from musicna_tui.client import ApiClient

_PLAYLIST_KEY_PREFIX = "playlist:"


class SearchScreen(ModalScreen[None]):
    """검색어를 입력하면 `GET /player/search` 결과를 표로 보여준다."""

    BINDINGS = [("escape", "dismiss_screen", "닫기")]

    def __init__(self, client: ApiClient) -> None:
        super().__init__()
        self.client = client

    def compose(self) -> ComposeResult:
        yield Input(placeholder="검색어 입력 후 Enter")
        yield DataTable(cursor_type="row")

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.add_columns("종류", "이름", "부가정보")
        self.query_one(Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        table = self.query_one(DataTable)
        table.clear()
        try:
            results = self.client.player_search(event.value)
        except Exception:
            return
        for t in results.get("tracks", []):
            extra = f"{t.get('album') or '-'} · {', '.join(t.get('artists', [])) or '-'}"
            table.add_row("트랙", t["name"], extra, key=f"track:{t['id']}")
        for a in results.get("artists", []):
            table.add_row("아티스트", a["name"], "-", key=f"artist:{a['id']}")
        for a in results.get("albums", []):
            table.add_row("앨범", a["name"], "-", key=f"album:{a['id']}")
        for p in results.get("playlists", []):
            table.add_row("플레이리스트", p["name"], p.get("owner") or "-",
                           key=f"{_PLAYLIST_KEY_PREFIX}{p['id']}")

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        row_key = event.row_key.value or ""
        if not row_key.startswith(_PLAYLIST_KEY_PREFIX):
            return
        playlist_id = row_key[len(_PLAYLIST_KEY_PREFIX):]
        try:
            self.client.player_play_playlist(playlist_id)
        except Exception:
            pass
        self.dismiss()

    def action_dismiss_screen(self) -> None:
        self.dismiss()
