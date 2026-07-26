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


def test_find_chord_loops_deduplicates_phase_shifted_repeats_of_same_pattern():
    """3회 이상 반복되는 패턴이 위상만 다른 여러 개의 중복 루프로 보고되면 안 된다."""
    pattern = ["I", "V", "vi", "IV"]
    sequence = [
        RomanEvent(roman=r, start_s=float(i), end_s=float(i + 1))
        for i, r in enumerate(pattern * 3)
    ]
    loops = find_chord_loops(sequence, min_length=4)
    assert len(loops) == 1
    assert loops[0].pattern == ["I", "V", "vi", "IV"]
    assert loops[0].occurrences == [(0.0, 4.0), (4.0, 8.0), (8.0, 12.0)]


def test_summarize_sections_two_empty_sections_do_not_link_to_each_other():
    sequence = [RomanEvent(roman="I", start_s=10.0, end_s=11.0)]  # 두 구간과 안 겹침
    sections = [
        Section(label="silence1", start_s=0.0, end_s=1.0),
        Section(label="silence2", start_s=2.0, end_s=3.0),
    ]
    summaries = summarize_sections(sequence, sections)
    assert summaries[0].roman_progression == [] and summaries[0].repeats_of is None
    assert summaries[1].roman_progression == [] and summaries[1].repeats_of is None


def test_find_chord_loops_does_not_report_shorter_subsumed_pattern():
    """6코드 패턴이 2회 반복되면, 그 안에 포함된 4코드 하위 패턴이 별도로 보고되면 안 된다."""
    pattern = ["I", "V", "vi", "IV", "ii", "V"]
    sequence = [
        RomanEvent(roman=r, start_s=float(i), end_s=float(i + 1))
        for i, r in enumerate(pattern * 2)
    ]
    loops = find_chord_loops(sequence, min_length=4)
    assert len(loops) == 1
    assert loops[0].pattern == pattern
    assert loops[0].occurrences == [(0.0, 6.0), (6.0, 12.0)]


def test_find_chord_loops_reports_primitive_period_for_four_repeats():
    """4회 반복은 '8코드 패턴이 2회'가 아니라 '4코드 패턴이 4회'로 보고돼야 한다."""
    pattern = ["I", "V", "vi", "IV"]
    sequence = [
        RomanEvent(roman=r, start_s=float(i), end_s=float(i + 1))
        for i, r in enumerate(pattern * 4)
    ]
    loops = find_chord_loops(sequence, min_length=4)
    assert len(loops) == 1
    assert loops[0].pattern == pattern
    assert loops[0].occurrences == [(0.0, 4.0), (4.0, 8.0), (8.0, 12.0), (12.0, 16.0)]


def test_find_chord_loops_does_not_drop_trailing_occurrence_for_odd_repeats():
    """5회(홀수) 반복에서도 마지막 등장이 누락되면 안 된다."""
    pattern = ["I", "V", "vi", "IV"]
    sequence = [
        RomanEvent(roman=r, start_s=float(i), end_s=float(i + 1))
        for i, r in enumerate(pattern * 5)
    ]
    loops = find_chord_loops(sequence, min_length=4)
    assert len(loops) == 1
    assert loops[0].pattern == pattern
    assert loops[0].occurrences == [
        (0.0, 4.0), (4.0, 8.0), (8.0, 12.0), (12.0, 16.0), (16.0, 20.0),
    ]


def test_find_chord_loops_greedily_selects_non_overlapping_occurrences():
    """등장끼리 겹치지 않는지 검증하는 일반 불변식 테스트."""
    # 실제 반복 패턴이 있는 시퀀스에서 occurrence가 절대 겹치지 않음을 확인
    pattern = ["I", "V", "vi", "IV", "ii", "V"]
    sequence = [
        RomanEvent(roman=r, start_s=float(i), end_s=float(i + 1))
        for i, r in enumerate(pattern * 2)
    ]
    loops = find_chord_loops(sequence, min_length=4)
    for loop in loops:
        starts = sorted(s for s, _ in loop.occurrences)
        ends = sorted(e for _, e in loop.occurrences)
        # 각 occurrence의 끝이 다음 occurrence의 시작보다 작거나 같아야 함
        assert all(e <= s2 for e, s2 in zip(ends, starts[1:]))
