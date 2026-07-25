"""MIDI ↔ 오디오 코드 교차 검증(병합) 테스트 — 순수 이벤트 조작, 외부 의존성 없음."""

from musicna_core.analyze.chords import _chord_family, merge_chord_tracks
from musicna_core.models import ChordEvent, ChordSource


def _ev(chord, start, end, source, conf=0.8):
    return ChordEvent(chord=chord, start_s=start, end_s=end, source=source, confidence=conf)


def test_chord_family_normalization():
    assert _chord_family("Am7") == _chord_family("Am") == (9, "minor")
    assert _chord_family("C") == _chord_family("Cmaj7") == (0, "major")
    assert _chord_family("A#") == _chord_family("B-") == (10, "major")  # 이명동음
    assert _chord_family("Bdim") == (11, "minor")
    assert _chord_family("N") is None


def test_agreement_merges_with_midi_label_and_bonus():
    midi = [_ev("Am7", 0, 4, ChordSource.MIDI, 0.7)]
    audio = [_ev("Am", 0, 4, ChordSource.AUDIO, 0.8)]
    [m] = merge_chord_tracks(midi, audio)
    assert m.chord == "Am7"  # 더 구체적인 MIDI 라벨 유지
    assert m.source == ChordSource.MERGED
    assert m.confidence == 0.95  # max(0.7, 0.8) + 0.15
    assert (m.start_s, m.end_s) == (0, 4)


def test_disagreement_picks_higher_confidence_with_penalty():
    midi = [_ev("C", 0, 4, ChordSource.MIDI, 0.9)]
    audio = [_ev("Dm", 0, 4, ChordSource.AUDIO, 0.5)]
    [m] = merge_chord_tracks(midi, audio)
    assert m.chord == "C" and m.source == ChordSource.MIDI
    assert m.confidence == 0.72  # 0.9 * 0.8


def test_one_sided_intervals_preserved():
    midi = [_ev("C", 0, 4, ChordSource.MIDI)]
    audio = [_ev("C", 0, 4, ChordSource.AUDIO), _ev("G", 4, 8, ChordSource.AUDIO)]
    merged = merge_chord_tracks(midi, audio)
    assert [(m.chord, m.source) for m in merged] == [
        ("C", ChordSource.MERGED), ("G", ChordSource.AUDIO),
    ]


def test_partial_overlap_splits_at_boundaries():
    # MIDI: C 0-4 / audio: C 0-2, Am 2-4 → 0-2 MERGED C, 2-4는 불일치(신뢰도 동률 → MIDI 우선)
    midi = [_ev("C", 0, 4, ChordSource.MIDI, 0.8)]
    audio = [_ev("C", 0, 2, ChordSource.AUDIO, 0.8), _ev("Am", 2, 4, ChordSource.AUDIO, 0.8)]
    merged = merge_chord_tracks(midi, audio)
    assert [(m.chord, m.source, m.start_s, m.end_s) for m in merged] == [
        ("C", ChordSource.MERGED, 0, 2), ("C", ChordSource.MIDI, 2, 4),
    ]
