"""musicna TUI 진입점 — 로컬 api 서버 부트스트랩 후 통합 대시보드를 표시한다.

api/system.py가 오케스트레이션(spotify_player 데몬·세션 캡처)을 소유한다 — 이 앱의
특수 역할은 로컬 api 서버(uvicorn) 자체가 안 떠 있을 때 부트스트랩하는 것뿐이다.
원격 클라이언트(미래 iOS 앱)는 이 부트스트랩이 필요 없다 — Mac의 api가 항상 떠 있다고
가정한다 (docs/PLAN.md).
"""

import subprocess
import sys
import time

from textual.app import App, ComposeResult
from textual.widgets import Footer, Header

from musicna_tui.client import ApiClient
from musicna_tui.widgets.player_panel import PlayerPanel
from musicna_tui.widgets.session_status import SessionStatus


def ensure_api_running(client: ApiClient, timeout: float = 15.0) -> subprocess.Popen | None:
    """로컬 api 서버가 응답하지 않으면 uvicorn을 서브프로세스로 띄우고 준비될 때까지 대기.

    이미 떠 있으면 아무것도 하지 않고 None을 반환한다(우리가 띄운 게 아니므로 종료 책임도 없음).
    """
    if client.health():
        return None
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "musicna_api.main:app", "--host", "127.0.0.1", "--port", "8000"]
    )
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if client.health():
            return proc
        time.sleep(0.5)
    proc.terminate()
    raise RuntimeError(f"api 서버가 {timeout}초 내에 기동하지 않았습니다")


class MusicnaApp(App):
    """musicna 통합 대시보드 — 재생 제어 + 세션 상태 (Phase 7 최소 셸)."""

    CSS = """
    PlayerPanel { height: 3; border: round $accent; padding: 0 1; }
    SessionStatus { height: 3; border: round $accent; padding: 0 1; }
    """

    def __init__(self) -> None:
        super().__init__()
        self.client = ApiClient()
        self._owned_api_proc: subprocess.Popen | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        yield PlayerPanel(self.client)
        yield SessionStatus(self.client)
        yield Footer()

    def on_mount(self) -> None:
        try:
            self._owned_api_proc = ensure_api_running(self.client)
            self.client.system_start()
        except Exception as e:
            # 부트스트랩 실패를 화면 크래시가 아니라 터미널에 메시지로 남기고 종료한다.
            self.exit(message=f"musicna 기동 실패: {e}")

    def on_unmount(self) -> None:
        self.client.close()
        if self._owned_api_proc is not None:
            self._owned_api_proc.terminate()


def run() -> None:
    MusicnaApp().run()


if __name__ == "__main__":
    run()
