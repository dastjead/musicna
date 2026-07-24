"""저장소 패턴 테스트 — AnalysisResult 저장 → 재조회 왕복."""

from datetime import datetime

from musicna_core.models import (
    AnalysisResult,
    CaptureSource,
    ChordEvent,
    ChordSource,
    MoodTag,
    Section,
    TrackMeta,
)
from musicna_core.store import create_session_factory, list_latest_analyses, save_analysis


def _result(title="Song A", captured_at=None, bpm=120.0):
    return AnalysisResult(
        track=TrackMeta(title=title, artist="Tester", source=CaptureSource.SPOTIFY, captured_at=captured_at),
        bpm=bpm,
        key="C",
        mode="major",
        sections=[Section(label="chorus", start_s=30.0, end_s=60.0)],
        chords=[ChordEvent(chord="Am7", start_s=0.0, end_s=2.0, source=ChordSource.MIDI, confidence=0.9)],
        moods=[MoodTag(tag="energetic", score=0.8)],
        midi_path="data/midi/a.mid",
        engine_versions={"music21": "10.5.0"},
        analyzed_at=datetime(2026, 7, 25, 12, 0),
    )


def test_save_and_list_roundtrip(tmp_path):
    factory = create_session_factory(str(tmp_path / "t.db"))
    original = _result(captured_at=datetime(2026, 7, 25, 10, 0))
    with factory() as session:
        save_analysis(session, original, audio_path="data/audio/a.wav")
    with factory() as session:
        [loaded] = list_latest_analyses(session)
    assert loaded == original


def test_reanalysis_reuses_track_and_returns_latest(tmp_path):
    factory = create_session_factory(str(tmp_path / "t.db"))
    captured = datetime(2026, 7, 25, 10, 0)
    with factory() as session:
        save_analysis(session, _result(captured_at=captured, bpm=120.0))
        newer = _result(captured_at=captured, bpm=121.0)
        newer = newer.model_copy(update={"analyzed_at": datetime(2026, 7, 26, 12, 0)})
        save_analysis(session, newer)

        from musicna_core.store import Analysis, Track

        assert session.query(Track).count() == 1  # 같은 트랙 재사용
        assert session.query(Analysis).count() == 2  # 분석 이력은 누적
        [latest] = list_latest_analyses(session)
        assert latest.bpm == 121.0


def test_multiple_tracks_ordered_by_captured_desc(tmp_path):
    factory = create_session_factory(str(tmp_path / "t.db"))
    with factory() as session:
        save_analysis(session, _result(title="Old", captured_at=datetime(2026, 7, 24, 9, 0)))
        save_analysis(session, _result(title="New", captured_at=datetime(2026, 7, 25, 9, 0)))
        results = list_latest_analyses(session)
    assert [r.track.title for r in results] == ["New", "Old"]
