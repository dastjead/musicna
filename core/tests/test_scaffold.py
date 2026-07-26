"""Phase 0 스모크 테스트: 모델 계약과 DB 스키마가 성립하는지 확인."""

from datetime import datetime

from musicna_core.models import (
    AnalysisResult,
    ChordEvent,
    ChordLoop,
    ChordSource,
    MoodTag,
    Section,
    SectionChordSummary,
    TrackMeta,
)
from musicna_core.store import Analysis, Chord, Mood, SectionRow, Track, create_session_factory


def test_analysis_result_roundtrip():
    result = AnalysisResult(
        track=TrackMeta(title="Test Song", artist="Tester", source="spotify"),
        bpm=120.0,
        key="C",
        mode="major",
        time_signature="4/4",
        sections=[Section(label="chorus", start_s=30.0, end_s=60.0)],
        chords=[ChordEvent(chord="Am7", start_s=0.0, end_s=2.0, source=ChordSource.MIDI, confidence=0.9)],
        moods=[MoodTag(tag="energetic", score=0.8)],
    )
    assert AnalysisResult.model_validate_json(result.model_dump_json()) == result


def test_db_schema_roundtrip(tmp_path):
    factory = create_session_factory(str(tmp_path / "test.db"))
    with factory() as session:
        track = Track(title="Test Song", artist="Tester", source="spotify", captured_at=datetime.now())
        analysis = Analysis(track=track, bpm=120.0, key="C", mode="major")
        analysis.sections.append(SectionRow(label="chorus", start_s=30.0, end_s=60.0))
        analysis.chords.append(Chord(chord="Am7", start_s=0.0, end_s=2.0, source="midi", confidence=0.9))
        analysis.moods.append(Mood(tag="energetic", score=0.8))
        session.add(track)
        session.commit()

        loaded = session.query(Track).one()
        assert loaded.analyses[0].chords[0].chord == "Am7"
        assert loaded.analyses[0].sections[0].label == "chorus"


def test_analysis_result_defaults_new_chord_structure_fields_to_empty():
    result = AnalysisResult(track=TrackMeta(title="X"))
    assert result.section_chord_summaries == []
    assert result.chord_loops == []


def test_section_chord_summary_and_chord_loop_round_trip():
    summary = SectionChordSummary(
        section_label="verse", start_s=0.0, end_s=10.0,
        roman_progression=["I", "V", "vi", "IV"], repeats_of=None,
    )
    loop = ChordLoop(pattern=["I", "V", "vi", "IV"], occurrences=[(0.0, 4.0), (4.0, 8.0)])
    result = AnalysisResult(
        track=TrackMeta(title="X"),
        section_chord_summaries=[summary],
        chord_loops=[loop],
    )
    assert AnalysisResult.model_validate_json(result.model_dump_json()) == result
