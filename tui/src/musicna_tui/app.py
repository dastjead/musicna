"""musicna TUI 진입점 — 상시 구동 중인 api 서버에 접속해 통합 대시보드를 표시한다.

api/system.py가 오케스트레이션(spotify_player 데몬·세션 캡처)을 소유한다. 이 앱은
웹 UI와 동일하게 api에 접속만 하는 순수 클라이언트다(Phase 8.5) — api는 Mac mini에서
launchd로 상시 구동되며, MUSICNA_API_URL 환경변수로 접속 주소를 지정한다
(기본값은 로컬 개발용, docs/PLAN.md 참조).
"""

import os

from textual.app import App, ComposeResult
from textual.widgets import Footer, Header

from musicna_tui.client import ApiClient
from musicna_tui.widgets.library_browser import LibraryBrowserWidget
from musicna_tui.widgets.live_analysis import LiveAnalysisWidget
from musicna_tui.widgets.player_panel import PlayerPanel
from musicna_tui.widgets.playlists_screen import PlaylistsScreen
from musicna_tui.widgets.search_screen import SearchScreen
from musicna_tui.widgets.session_status import SessionStatus

DEFAULT_API_URL = "http://127.0.0.1:8000"


class MusicnaApp(App):
    """musicna 통합 대시보드 — 재생 제어 + 세션 상태 + 실시간 분석 + 라이브러리."""

    CSS = """
    PlayerPanel { height: 3; border: round $accent; padding: 0 1; }
    SessionStatus { height: 3; border: round $accent; padding: 0 1; }
    LiveAnalysisWidget { height: 3; border: round $accent; padding: 0 1; }
    LibraryBrowserWidget { height: 1fr; border: round $accent; }
    """

    BINDINGS = [
        ("/", "open_search", "검색"),
        ("u", "open_playlists", "플레이리스트"),
    ]

    def __init__(self) -> None:
        super().__init__()
        base_url = os.environ.get("MUSICNA_API_URL", DEFAULT_API_URL)
        self.client = ApiClient(base_url=base_url)

    def compose(self) -> ComposeResult:
        yield Header()
        yield PlayerPanel(self.client)
        yield SessionStatus(self.client)
        yield LiveAnalysisWidget(self.client)
        yield LibraryBrowserWidget(self.client)
        yield Footer()

    def on_mount(self) -> None:
        try:
            self.client.system_start()
        except Exception as e:
            self.exit(message=f"musicna 기동 실패: {e}")

    def action_open_search(self) -> None:
        self.push_screen(SearchScreen(self.client))

    def action_open_playlists(self) -> None:
        self.push_screen(PlaylistsScreen(self.client))

    def on_unmount(self) -> None:
        self.client.close()


def run() -> None:
    MusicnaApp().run()


if __name__ == "__main__":
    run()
