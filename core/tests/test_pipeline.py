"""analyze_track 파이프라인 테스트 — base 의존성만으로 (allin1/CLAP 미설치 환경) 동작 검증."""

from music21 import chord as m21chord
from music21 import stream

from musicna_core.analyze import analyze_track
from musicna_core.models import AnalysisResult, CaptureSource, TrackMeta


def test_analyze_track_midi_only(tmp_path):
    s = stream.Stream()
    for name in ["C4 E4 G4", "F3 A3 C4", "G3 B3 D4", "C4 E4 G4"]:
        c = m21chord.Chord(name)
        c.quarterLength = 4.0
        s.append(c)
    midi = tmp_path / "track.mid"
    s.write("midi", fp=str(midi))

    meta = TrackMeta(title="Test", artist="Tester", source=CaptureSource.SPOTIFY)
    result = analyze_track(tmp_path / "missing.wav", midi, meta)

    assert (result.key, result.mode) == ("C", "major")
    assert [e.chord for e in result.chords] == ["C", "F", "G", "C"]
    assert "music21" in result.engine_versions
    assert result.midi_path == str(midi)
    # optional extra 미설치 환경에서는 구조/무드가 비어 있어야 한다 (오류 없이 건너뜀)
    assert result.sections == [] and result.moods == [] and result.bpm is None
    # API 응답으로 그대로 직렬화 가능해야 한다
    assert AnalysisResult.model_validate_json(result.model_dump_json()) == result


def test_analyze_track_without_midi(tmp_path):
    meta = TrackMeta(title="NoMidi")
    result = analyze_track(tmp_path / "missing.wav", None, meta)
    assert result.key is None and result.chords == [] and result.midi_path is None
