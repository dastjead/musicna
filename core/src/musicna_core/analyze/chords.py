"""MIDI 기반 코드 진행 추출.

전사 MIDI(muscriptor 출력)를 고정 길이 창으로 훑으며 창마다 울리는 피치클래스를
지속시간 가중으로 집계해 코드를 판정한다. 라벨링은 music21 harmony를 사용.

- 전사 MIDI는 마디 정보가 신뢰할 수 없으므로(고정 120bpm 가정) 초 단위 창을 쓴다
- 오디오(chroma) 기반 추출과의 교차 검증은 librosa/madmom 통합 시 추가 (source=AUDIO/MERGED)
"""

from collections import defaultdict
from pathlib import Path

from music21 import chord as m21chord
from music21 import converter, harmony, pitch

from musicna_core.models import ChordEvent, ChordSource

# 창 안에서 최대 가중치 대비 이 비율 이상인 피치클래스만 코드 구성음 후보로 삼는다
_PC_WEIGHT_THRESHOLD = 0.3
# 코드 구성음 최대 개수 (7th까지 표현, 텐션은 상위 4개로 축약)
_MAX_CHORD_TONES = 4


def _extract_notes_seconds(midi_path: Path) -> list[tuple[int, float, float]]:
    """MIDI에서 (midi_pitch, start_s, end_s) 목록을 뽑는다. 템포 이벤트를 반영한 초 단위."""
    score = converter.parse(str(midi_path))
    notes: list[tuple[int, float, float]] = []
    for entry in score.flatten().secondsMap:
        el = entry["element"]
        start = entry["offsetSeconds"]
        end = start + entry["durationSeconds"]
        if isinstance(el, m21chord.Chord):
            notes.extend((p.midi, start, end) for p in el.pitches)
        elif hasattr(el, "pitch"):  # Note
            notes.append((el.pitch.midi, start, end))
    return notes


def _label_chord(pcs_by_weight: list[int], bass_pc: int) -> str | None:
    """피치클래스 집합을 코드 기호(예: 'Am7')로 라벨링한다. 판정 불가면 None."""
    ordered = sorted(pcs_by_weight)
    if bass_pc in ordered:  # 베이스음을 최저 옥타브에 두어 루트 판정을 돕는다
        ordered.remove(bass_pc)
    pitches = [pitch.Pitch(midi=48 + bass_pc)] + [pitch.Pitch(midi=60 + pc) for pc in ordered]
    c = m21chord.Chord(pitches)
    try:
        figure = harmony.chordSymbolFigureFromChord(c)
    except Exception:
        figure = None
    if not figure or "Cannot" in str(figure):
        quality = c.quality  # 폴백: 루트 + 단순 품질
        suffix = {"major": "", "minor": "m", "diminished": "dim", "augmented": "aug"}.get(quality)
        if suffix is None:
            return None
        return f"{c.root().name}{suffix}"
    return str(figure)


def extract_chords_from_midi(
    midi_path: Path,
    window_s: float = 1.0,
    min_tones: int = 2,
) -> list[ChordEvent]:
    """MIDI를 window_s 창으로 나눠 코드 이벤트 목록을 돌려준다. 연속 동일 코드는 병합."""
    notes = _extract_notes_seconds(midi_path)
    if not notes:
        return []
    total_end = max(end for _, _, end in notes)

    events: list[ChordEvent] = []
    t = 0.0
    while t < total_end:
        w_start, w_end = t, min(t + window_s, total_end)
        t += window_s

        weights: dict[int, float] = defaultdict(float)
        lowest: tuple[int, float] | None = None  # (midi_pitch, overlap)
        for midi_pitch, start, end in notes:
            overlap = min(end, w_end) - max(start, w_start)
            if overlap <= 0:
                continue
            weights[midi_pitch % 12] += overlap
            if lowest is None or midi_pitch < lowest[0]:
                lowest = (midi_pitch, overlap)
        if not weights or lowest is None:
            continue

        max_w = max(weights.values())
        candidates = sorted(weights.items(), key=lambda kv: -kv[1])
        tones = [pc for pc, w in candidates if w >= max_w * _PC_WEIGHT_THRESHOLD][:_MAX_CHORD_TONES]
        if len(tones) < min_tones:
            continue

        label = _label_chord(tones, bass_pc=lowest[0] % 12)
        if label is None:
            continue
        confidence = round(sum(weights[pc] for pc in tones) / sum(weights.values()), 4)

        if events and events[-1].chord == label and abs(events[-1].end_s - w_start) < 1e-6:
            events[-1] = events[-1].model_copy(update={"end_s": w_end})  # 병합
        else:
            events.append(
                ChordEvent(
                    chord=label,
                    start_s=round(w_start, 3),
                    end_s=round(w_end, 3),
                    source=ChordSource.MIDI,
                    confidence=confidence,
                )
            )
    return events
