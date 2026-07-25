"""실시간 코드 추정 — 전사 스트림의 note on/off를 받아 롤링 창으로 코드를 판정한다.

배치 추출(chords.py)과 같은 라벨링 로직(label_weighted_pcs)을 공유하므로
실시간 미리보기와 확정 분석의 코드 표기가 일치한다. 순수 Python — 어디서나 테스트 가능.
"""

from dataclasses import dataclass, field

from musicna_core.analyze.chords import label_weighted_pcs
from musicna_core.models import LiveChord


@dataclass
class _Note:
    pitch: int
    start_s: float
    end_s: float | None = None  # None = 아직 울리는 중


@dataclass
class LiveChordTracker:
    """note_on/note_off를 누적하고 poll() 시점의 최근 창에서 코드를 추정한다.

    같은 코드가 이어지는 동안은 이벤트를 내지 않는다 (변화 시점만 산출).
    """

    window_s: float = 2.0
    _notes: dict[int, _Note] = field(default_factory=dict)
    _last_chord: str | None = None

    def note_on(self, index: int, pitch: int, start_s: float) -> None:
        self._notes[index] = _Note(pitch=pitch, start_s=start_s)

    def note_off(self, index: int, end_s: float) -> None:
        note = self._notes.get(index)
        if note is not None:
            note.end_s = end_s

    def poll(self, now_s: float) -> LiveChord | None:
        """[now-window, now] 창에서 코드를 판정한다. 직전과 같은 코드면 None."""
        w_start = now_s - self.window_s
        weights: dict[int, float] = {}
        lowest: int | None = None
        for note in self._notes.values():
            end = note.end_s if note.end_s is not None else now_s
            overlap = min(end, now_s) - max(note.start_s, w_start)
            if overlap <= 0:
                continue
            weights[note.pitch % 12] = weights.get(note.pitch % 12, 0.0) + overlap
            if lowest is None or note.pitch < lowest:
                lowest = note.pitch

        # 창을 완전히 벗어난 노트는 버린다 (메모리 상한)
        self._notes = {
            i: n for i, n in self._notes.items() if n.end_s is None or n.end_s > w_start
        }

        if not weights or lowest is None:
            return None
        labeled = label_weighted_pcs(weights, bass_pc=lowest % 12)
        if labeled is None:
            return None
        label, confidence = labeled
        if label == self._last_chord:
            return None
        self._last_chord = label
        return LiveChord(chord=label, start_s=round(now_s, 3), confidence=confidence)
