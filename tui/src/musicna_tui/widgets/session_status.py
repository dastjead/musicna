"""세션 캡처·spotify_player 데몬 상태 표시 위젯."""

from textual.widgets import Static

from musicna_tui.client import ApiClient


class SessionStatus(Static):
    """`/system/status`를 주기적으로 폴링해 데몬·캡처 상태를 표시한다."""

    def __init__(self, client: ApiClient) -> None:
        super().__init__()
        self.client = client

    def on_mount(self) -> None:
        self.refresh_status()
        self.set_interval(3.0, self.refresh_status)

    def refresh_status(self) -> None:
        try:
            status = self.client.system_status()
        except Exception:
            self.update("시스템 상태를 가져올 수 없습니다")
            return
        daemon = "켜짐" if status["spotify_player_daemon"] else "꺼짐"
        capturing = "녹음 중" if status["session_capturing"] else "대기"
        self.update(f"spotify_player 데몬: {daemon}  |  캡처: {capturing}")
