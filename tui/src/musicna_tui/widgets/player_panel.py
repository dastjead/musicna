"""현재 재생 상태 표시 + 재생 제어 위젯."""

from textual.widgets import Static

from musicna_tui.client import ApiClient


class PlayerPanel(Static):
    """재생 상태를 주기적으로 폴링해 표시하고, 키 입력으로 재생을 제어한다."""

    BINDINGS = [
        ("space", "play_pause", "재생/일시정지"),
        ("n", "next_track", "다음 곡"),
        ("p", "previous_track", "이전 곡"),
    ]
    can_focus = True

    def __init__(self, client: ApiClient) -> None:
        super().__init__()
        self.client = client

    def on_mount(self) -> None:
        self.refresh_status()
        self.set_interval(2.0, self.refresh_status)

    def refresh_status(self) -> None:
        try:
            status = self.client.player_status()
        except Exception:
            self.update("재생 상태를 가져올 수 없습니다 (api 연결 확인)")
            return
        if status is None:
            self.update("재생 중인 곡 없음")
            return
        icon = "▶" if status.get("is_playing") else "⏸"
        title = status.get("item_title") or "?"
        artist = status.get("item_artist") or "?"
        volume = status.get("volume_percent")
        self.update(f"{icon} {title} — {artist}  (볼륨 {volume}%)")

    def action_play_pause(self) -> None:
        try:
            status = self.client.player_status()
        except Exception:
            return
        if status and status.get("is_playing"):
            self.client.player_pause()
        else:
            self.client.player_play()
        self.refresh_status()

    def action_next_track(self) -> None:
        self.client.player_next()
        self.refresh_status()

    def action_previous_track(self) -> None:
        self.client.player_previous()
        self.refresh_status()
