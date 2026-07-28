"""실시간 분석 뷰 위젯 — /ws/live 구독, 현재 코드+진행 히스토리+울리는 노트 개수를 표시.

터미널은 웹의 캔버스 피아노 롤을 그릴 수 없으므로, 코드·노트 활동을 텍스트로 보여주는 것으로
기능적 동등성을 삼는다(각 클라이언트는 독립 인터페이스이되 기능은 동등하다는 설계 원칙).
"""

import json

import websockets
from textual.widgets import Static

from musicna_tui.client import ApiClient

RECONNECT_DELAY_S = 2.0
HISTORY_LIMIT = 8


class LiveAnalysisWidget(Static):
    """`/ws/live`를 구독해 현재 코드·직전 진행·울리는 노트 개수를 표시한다."""

    def __init__(self, client: ApiClient) -> None:
        super().__init__()
        self.client = client
        self._connected = False
        self._current_chord: str | None = None
        self._chord_history: list[str] = []
        self._active_notes: set[int] = set()

    def on_mount(self) -> None:
        self._render_state()
        self.run_worker(self._listen(), exclusive=True)

    async def _listen(self) -> None:
        import asyncio

        while True:
            try:
                async with websockets.connect(self.client.live_ws_url) as ws:
                    self._connected = True
                    self._render_state()
                    async for raw in ws:
                        self._handle_event(json.loads(raw))
                        self._render_state()
            except Exception:
                pass
            # 정상 종료(서버가 스트림을 닫음)든 예외든, 재연결 전 항상 대기한다 —
            # 그렇지 않으면 즉시 재연결 → 즉시 종료가 반복되어 이벤트 루프를 독점하는
            # 바쁜 루프(busy loop)가 된다.
            self._connected = False
            self._render_state()
            await asyncio.sleep(RECONNECT_DELAY_S)

    def _handle_event(self, event: dict) -> None:
        match event.get("type"):
            case "track_started":
                self._current_chord = None
                self._chord_history = []
                self._active_notes = set()
            case "note_on":
                self._active_notes.add(event["index"])
            case "note_off":
                self._active_notes.discard(event["index"])
            case "chord":
                if self._current_chord is not None:
                    self._chord_history.append(self._current_chord)
                    self._chord_history = self._chord_history[-HISTORY_LIMIT:]
                self._current_chord = event["chord"]
            case "track_ended":
                self._active_notes = set()

    def _render_state(self) -> None:
        conn = "연결됨" if self._connected else "재연결 중…"
        chord = self._current_chord or "—"
        history = " → ".join(self._chord_history) if self._chord_history else "(없음)"
        notes = len(self._active_notes)
        self.update(f"[{conn}] 현재 코드: {chord}  |  진행: {history}  |  울리는 노트: {notes}개")
