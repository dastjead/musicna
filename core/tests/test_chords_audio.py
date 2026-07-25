"""오디오(chroma) 코드 추출 테스트 — 합성 사인파 3화음 WAV (실음원 불필요, Linux CI 가능)."""

import numpy as np
import pytest
import soundfile as sf

from musicna_core.analyze.chords_audio import extract_chords_from_audio
from musicna_core.models import ChordSource

SR = 22050

# 4분음 평균율 주파수
FREQ = {"C4": 261.63, "E4": 329.63, "G4": 392.00, "F4": 349.23, "A4": 440.00,
        "C5": 523.25, "B4": 493.88, "D5": 587.33, "A3": 220.00, "E5": 659.26}


def _triad_wave(notes, seconds=2.0):
    t = np.arange(int(SR * seconds)) / SR
    wave = sum(np.sin(2 * np.pi * FREQ[n] * t) for n in notes)
    return (wave / len(notes)).astype(np.float32)


def _write_wav(path, chord_list):
    sf.write(str(path), np.concatenate([_triad_wave(n) for n in chord_list]), SR)
    return path


def test_major_progression(tmp_path):
    wav = _write_wav(tmp_path / "prog.wav", [
        ["C4", "E4", "G4"], ["F4", "A4", "C5"], ["G4", "B4", "D5"], ["C4", "E4", "G4"],
    ])
    events = extract_chords_from_audio(wav, window_s=1.0)
    assert [e.chord for e in events] == ["C", "F", "G", "C"]
    assert all(e.source == ChordSource.AUDIO for e in events)
    assert all(e.confidence and e.confidence > 0.6 for e in events)
    assert events[0].start_s == 0.0 and abs(events[-1].end_s - 8.0) < 0.1


def test_minor_chord(tmp_path):
    wav = _write_wav(tmp_path / "am.wav", [["A3", "C4", "E4"]])
    events = extract_chords_from_audio(wav, window_s=1.0)
    assert len(events) == 1
    assert events[0].chord == "Am"


def test_silence_yields_no_chords(tmp_path):
    sf.write(str(tmp_path / "silence.wav"), np.zeros(SR, dtype=np.float32), SR)
    assert extract_chords_from_audio(tmp_path / "silence.wav") == []


def test_empty_audio(tmp_path):
    sf.write(str(tmp_path / "empty.wav"), np.zeros(0, dtype=np.float32), SR)
    assert extract_chords_from_audio(tmp_path / "empty.wav") == []
