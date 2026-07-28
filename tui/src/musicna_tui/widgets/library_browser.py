"""라이브러리 브라우저 위젯 — /tracks 폴링, 웹 라이브러리 브라우저와 동등한 정보를 표 형태로."""

from textual.widgets import DataTable

from musicna_tui.client import ApiClient


class LibraryBrowserWidget(DataTable):
    """`/tracks`를 주기적으로 폴링해 트랙 목록을 표로 표시한다."""

    def __init__(self, client: ApiClient) -> None:
        super().__init__(cursor_type="row")
        self.client = client

    def on_mount(self) -> None:
        self.add_columns("제목", "아티스트", "BPM", "키", "무드")
        self.refresh_tracks()
        self.set_interval(5.0, self.refresh_tracks)

    def refresh_tracks(self) -> None:
        try:
            tracks = self.client.tracks()
            self.clear()
            for t in tracks:
                bpm = f"{t['bpm']:.0f}" if t.get("bpm") else "-"
                key = f"{t['key']} {t['mode']}" if t.get("key") else "-"
                mood = t["moods"][0]["tag"] if t.get("moods") else "-"
                self.add_row(
                    t["track"]["title"],
                    t["track"].get("artist") or "-",
                    bpm, key, mood,
                    key=str(t["id"]),
                )
        except Exception:
            self.clear()
            self.add_row("api 연결 실패", "", "", "", "")
