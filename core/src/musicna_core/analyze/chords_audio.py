"""오디오(chroma) 기반 코드 추출 — MIDI 기반 추출(chords.py)의 교차 검증 상대.

librosa chroma_cqt를 MIDI 쪽과 동일한 초 단위 창으로 집계하고, 장/단 3화음
템플릿 24개와 코사인 유사도로 라벨링한다. librosa는 optional extra(chroma/analyze).
"""

from pathlib import Path

from musicna_core.models import ChordEvent, ChordSource

_NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def _build_templates(np):
    """(24, 12) 정규화 템플릿과 라벨. 행 순서: C, Cm, C#, C#m, …"""
    rows, labels = [], []
    for root in range(12):
        for third, suffix in ((4, ""), (3, "m")):
            v = np.zeros(12)
            v[root] = v[(root + third) % 12] = v[(root + 7) % 12] = 1.0
            rows.append(v / np.linalg.norm(v))
            labels.append(f"{_NOTE_NAMES[root]}{suffix}")
    return np.vstack(rows), labels


def extract_chords_from_audio(
    audio_path: Path,
    window_s: float = 1.0,
    min_confidence: float = 0.6,
) -> list[ChordEvent]:
    """오디오를 window_s 창으로 나눠 코드 이벤트 목록을 돌려준다. 연속 동일 코드는 병합.

    confidence는 chroma-템플릿 코사인 유사도(0~1). min_confidence 미만 창은 무코드로 본다.
    """
    import librosa
    import numpy as np

    y, sr = librosa.load(str(audio_path), sr=22050, mono=True)
    if y.size == 0:
        return []
    duration = y.size / sr

    hop = 512
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr, hop_length=hop)
    frame_time = hop / sr
    templates, labels = _build_templates(np)

    events: list[ChordEvent] = []
    t = 0.0
    while t < duration:
        w_end = min(t + window_s, duration)
        f0 = int(t / frame_time)
        f1 = max(int(w_end / frame_time), f0 + 1)
        v = chroma[:, f0:f1].mean(axis=1)
        norm = float(np.linalg.norm(v))
        if norm < 1e-6:  # 무음 창
            t += window_s
            continue
        sims = templates @ (v / norm)
        best = int(np.argmax(sims))
        confidence = float(sims[best])
        if confidence < min_confidence:
            t += window_s
            continue

        label = labels[best]
        if events and events[-1].chord == label and abs(events[-1].end_s - t) < 1e-6:
            events[-1] = events[-1].model_copy(update={"end_s": round(w_end, 3)})
        else:
            events.append(
                ChordEvent(
                    chord=label,
                    start_s=round(t, 3),
                    end_s=round(w_end, 3),
                    source=ChordSource.AUDIO,
                    confidence=round(confidence, 4),
                )
            )
        t += window_s
    return events
