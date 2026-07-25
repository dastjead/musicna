"""analyze_track 파이프라인 테스트 — base 의존성만으로 (allin1/CLAP 미설치 환경) 동작 검증."""

import sys
import types

import pytest
from music21 import chord as m21chord
from music21 import stream

import musicna_core.analyze as analyze_mod
from musicna_core.analyze import analyze_track
from musicna_core.models import AnalysisResult, CaptureSource, TrackMeta


@pytest.fixture(autouse=True)
def no_ml_extras(monkeypatch):
    """extras가 설치된 환경에서도 미설치 경로를 검증한다 — 실모델 로드(다운로드 수 GB) 방지."""
    monkeypatch.setitem(sys.modules, "allin1", None)
    monkeypatch.setitem(sys.modules, "laion_clap", None)


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
    # optional extra 미설치 또는 분석 실패(여기서는 오디오 없음) 시 구조/무드가 비어야 한다 (크래시 금지)
    assert result.sections == [] and result.moods == [] and result.bpm is None
    # API 응답으로 그대로 직렬화 가능해야 한다
    assert AnalysisResult.model_validate_json(result.model_dump_json()) == result


def test_analyze_track_without_midi(tmp_path):
    meta = TrackMeta(title="NoMidi")
    result = analyze_track(tmp_path / "missing.wav", None, meta)
    assert result.key is None and result.chords == [] and result.midi_path is None


def test_analyze_track_noteless_midi(tmp_path):
    """노트 없는 MIDI(저레벨 캡처의 전사 결과)에서도 크래시 없이 키/코드만 비워야 한다."""
    from music21 import note

    s = stream.Stream()
    s.append(note.Rest(quarterLength=4.0))
    midi = tmp_path / "empty.mid"
    s.write("midi", fp=str(midi))

    result = analyze_track(tmp_path / "missing.wav", midi, TrackMeta(title="Quiet"))
    assert result.key is None and result.mode is None and result.chords == []
    assert result.midi_path == str(midi)


def test_analyze_track_structure_without_bpm(monkeypatch, tmp_path):
    """준무음 오디오에서 allin1이 bpm=None을 반환해도 크래시 없이 구간만 담아야 한다 (실기기 발견 사례)."""
    fake = types.ModuleType("allin1")
    seg = types.SimpleNamespace(label="intro", start=0.0, end=5.0)
    fake.analyze = lambda path, **kw: types.SimpleNamespace(bpm=None, segments=[seg])
    monkeypatch.setitem(sys.modules, "allin1", fake)
    monkeypatch.setattr(analyze_mod, "pkg_version", lambda name: "0.0-test")

    result = analyze_track(tmp_path / "missing.wav", None, TrackMeta(title="Quiet"))
    assert result.bpm is None
    assert [s.label for s in result.sections] == ["intro"]
