"""코드 단순화·로마자 변환·시퀀스 생성 테스트 — 실측 검증된 music21 동작 기준."""

from musicna_core.analyze.chord_structure import (
    RomanEvent,
    build_roman_sequence,
    find_chord_loops,
    simplify_chord,
    summarize_sections,
    to_roman,
)
from musicna_core.models import ChordEvent, ChordSource, Section


def test_simplify_chord_strips_extensions_to_triad_quality():
    assert simplify_chord("Am7") == "Am"
    assert simplify_chord("Cmaj7") == "C"
    assert simplify_chord("G7") == "G"
    assert simplify_chord("Bdim") == "Bdim"


def test_simplify_chord_returns_none_for_unparseable_input():
    assert simplify_chord("not-a-chord-symbol-###") is None


def test_to_roman_major_key_diatonic_triads():
    assert to_roman("C", "C", "major") == "I"
    assert to_roman("Dm", "C", "major") == "ii"
    assert to_roman("Em", "C", "major") == "iii"
    assert to_roman("F", "C", "major") == "IV"
    assert to_roman("G", "C", "major") == "V"
    assert to_roman("Am", "C", "major") == "vi"
    assert to_roman("Bdim", "C", "major") == "vii°"


def test_to_roman_extensions_reduce_to_triad_roman():
    assert to_roman("Am7", "C", "major") == "vi"
    assert to_roman("G7", "C", "major") == "V"


def test_to_roman_chromatic_chords_get_accidental_prefix():
    assert to_roman("B-", "C", "major") == "bVII"
    assert to_roman("F#", "C", "major") == "#IV"


def test_to_roman_minor_key():
    assert to_roman("Am", "A", "minor") == "i"
    assert to_roman("G", "A", "minor") == "VII"
    assert to_roman("F", "A", "minor") == "VI"


def test_to_roman_unparseable_returns_none():
    assert to_roman("garbage", "C", "major") is None


def test_build_roman_sequence_merges_consecutive_identical_romans():
    chords = [
        ChordEvent(chord="C", start_s=0.0, end_s=1.0, source=ChordSource.MIDI),
        ChordEvent(chord="Cmaj7", start_s=1.0, end_s=2.0, source=ChordSource.MIDI),  # 같은 로마자(I)로 병합돼야 함
        ChordEvent(chord="F", start_s=2.0, end_s=3.0, source=ChordSource.MIDI),
    ]
    sequence = build_roman_sequence(chords, "C", "major")
    assert sequence == [
        RomanEvent(roman="I", start_s=0.0, end_s=2.0),
        RomanEvent(roman="IV", start_s=2.0, end_s=3.0),
    ]


def test_build_roman_sequence_skips_unparseable_chords():
    chords = [
        ChordEvent(chord="C", start_s=0.0, end_s=1.0, source=ChordSource.MIDI),
        ChordEvent(chord="garbage", start_s=1.0, end_s=2.0, source=ChordSource.MIDI),
        ChordEvent(chord="F", start_s=2.0, end_s=3.0, source=ChordSource.MIDI),
    ]
    sequence = build_roman_sequence(chords, "C", "major")
    assert [e.roman for e in sequence] == ["I", "IV"]


def test_summarize_sections_links_repeated_progressions():
    sequence = [
        RomanEvent(roman="I", start_s=0.0, end_s=1.0),
        RomanEvent(roman="V", start_s=1.0, end_s=2.0),
        RomanEvent(roman="vi", start_s=2.0, end_s=3.0),
        RomanEvent(roman="IV", start_s=3.0, end_s=4.0),
        RomanEvent(roman="ii", start_s=4.0, end_s=5.0),
        RomanEvent(roman="V", start_s=5.0, end_s=6.0),
        RomanEvent(roman="I", start_s=6.0, end_s=7.0),
        RomanEvent(roman="V", start_s=7.0, end_s=8.0),
        RomanEvent(roman="vi", start_s=8.0, end_s=9.0),
        RomanEvent(roman="IV", start_s=9.0, end_s=10.0),
    ]
    sections = [
        Section(label="verse", start_s=0.0, end_s=4.0),
        Section(label="chorus", start_s=4.0, end_s=6.0),
        Section(label="verse", start_s=6.0, end_s=10.0),
    ]
    summaries = summarize_sections(sequence, sections)

    assert [s.roman_progression for s in summaries] == [
        ["I", "V", "vi", "IV"],
        ["ii", "V"],
        ["I", "V", "vi", "IV"],
    ]
    assert summaries[0].repeats_of is None  # 첫 등장
    assert summaries[1].repeats_of is None  # 다른 진행
    assert summaries[2].repeats_of == 0     # 0번 구간(verse)과 동일 진행


def test_summarize_sections_empty_section_has_no_repeats_of():
    sequence = [RomanEvent(roman="I", start_s=5.0, end_s=6.0)]
    sections = [Section(label="silence", start_s=0.0, end_s=1.0)]  # 겹치는 이벤트 없음
    [summary] = summarize_sections(sequence, sections)
    assert summary.roman_progression == []
    assert summary.repeats_of is None


def test_find_chord_loops_detects_repeated_four_chord_pattern():
    sequence = [
        RomanEvent(roman=r, start_s=float(i), end_s=float(i + 1))
        for i, r in enumerate(["I", "V", "vi", "IV", "I", "V", "vi", "IV"])
    ]
    loops = find_chord_loops(sequence, min_length=4)
    assert len(loops) == 1
    assert loops[0].pattern == ["I", "V", "vi", "IV"]
    assert loops[0].occurrences == [(0.0, 4.0), (4.0, 8.0)]


def test_find_chord_loops_ignores_repeats_shorter_than_min_length():
    sequence = [
        RomanEvent(roman=r, start_s=float(i), end_s=float(i + 1))
        for i, r in enumerate(["I", "V", "vi", "I", "V", "vi", "IV"])
    ]
    assert find_chord_loops(sequence, min_length=4) == []


def test_find_chord_loops_empty_sequence_returns_empty():
    assert find_chord_loops([], min_length=4) == []
