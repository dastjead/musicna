"""MIDI 키 추정 테스트 — music21로 합성한 MIDI fixture 사용 (실음원 불필요, Linux CI 가능)."""

from music21 import chord as m21chord
from music21 import stream

from musicna_core.analyze.keys import estimate_key_from_midi


def _write_progression_midi(path, chord_names):
    s = stream.Stream()
    for name in chord_names:
        c = m21chord.Chord(name)
        c.quarterLength = 4.0
        s.append(c)
    s.write("midi", fp=str(path))
    return path


def test_c_major_progression(tmp_path):
    midi = _write_progression_midi(tmp_path / "cmaj.mid", ["C4 E4 G4", "F4 A4 C5", "G4 B4 D5", "C4 E4 G4"])
    tonic, mode, confidence = estimate_key_from_midi(midi)
    assert (tonic, mode) == ("C", "major")
    assert confidence > 0.7


def test_a_minor_progression(tmp_path):
    midi = _write_progression_midi(tmp_path / "amin.mid", ["A3 C4 E4", "D4 F4 A4", "E4 G#4 B4", "A3 C4 E4"])
    tonic, mode, confidence = estimate_key_from_midi(midi)
    assert (tonic, mode) == ("A", "minor")
