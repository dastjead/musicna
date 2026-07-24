"""MIDI 코드 진행 추출 테스트 — 합성 MIDI fixture (기본 120bpm: 4분음표=0.5초)."""

from music21 import chord as m21chord
from music21 import stream

from musicna_core.analyze.chords import extract_chords_from_midi
from musicna_core.models import ChordSource


def _write_midi(path, chord_names, quarters=4.0):
    s = stream.Stream()
    for name in chord_names:
        c = m21chord.Chord(name)
        c.quarterLength = quarters
        s.append(c)
    s.write("midi", fp=str(path))
    return path


def test_triad_progression_labels_and_merging(tmp_path):
    # C–F–G–C, 각 2초. 1초 창 → 연속 동일 코드가 병합되어 4개 이벤트여야 한다
    midi = _write_midi(tmp_path / "prog.mid", ["C4 E4 G4", "F3 A3 C4", "G3 B3 D4", "C4 E4 G4"])
    events = extract_chords_from_midi(midi, window_s=1.0)
    assert [e.chord for e in events] == ["C", "F", "G", "C"]
    assert all(e.source == ChordSource.MIDI for e in events)
    assert events[0].start_s == 0.0
    assert abs(events[0].end_s - 2.0) < 0.1
    assert abs(events[-1].end_s - 8.0) < 0.1


def test_seventh_chord(tmp_path):
    midi = _write_midi(tmp_path / "am7.mid", ["A2 A3 C4 E4 G4"])
    events = extract_chords_from_midi(midi, window_s=1.0)
    assert len(events) == 1
    assert events[0].chord == "Am7"
    assert events[0].confidence and events[0].confidence > 0.9


def test_empty_midi(tmp_path):
    s = stream.Stream()
    s.write("midi", fp=str(tmp_path / "empty.mid"))
    assert extract_chords_from_midi(tmp_path / "empty.mid") == []
