"""실시간 코드 추정기 테스트 — 순수 이벤트 입력, 외부 의존성 없음."""

from musicna_core.analyze.live_chords import LiveChordTracker


def _play_triad(tracker, pitches, start, end, base_index=0):
    for i, p in enumerate(pitches):
        tracker.note_on(base_index + i, p, start)
    for i in range(len(pitches)):
        tracker.note_off(base_index + i, end)


def test_c_major_then_f_major():
    tracker = LiveChordTracker(window_s=2.0)
    _play_triad(tracker, [48, 60, 64, 67], 0.0, 2.0)  # C3 C4 E4 G4
    ev = tracker.poll(2.0)
    assert ev is not None and ev.chord == "C"
    assert ev.confidence and ev.confidence > 0.9

    # 같은 코드가 이어지면 이벤트 없음
    assert tracker.poll(2.5) is None

    _play_triad(tracker, [41, 53, 57, 60], 2.0, 4.0, base_index=10)  # F2 F3 A3 C4
    ev = tracker.poll(4.0)
    assert ev is not None and ev.chord == "F"


def test_sustained_note_counts_until_now():
    tracker = LiveChordTracker(window_s=2.0)
    for i, p in enumerate([45, 57, 60, 64]):  # A2 A3 C4 E4, note_off 없이 지속
        tracker.note_on(i, p, 0.0)
    ev = tracker.poll(1.0)
    assert ev is not None and ev.chord == "Am"


def test_no_notes_yields_none():
    assert LiveChordTracker().poll(1.0) is None


def test_old_notes_fall_out_of_window():
    tracker = LiveChordTracker(window_s=2.0)
    _play_triad(tracker, [48, 60, 64, 67], 0.0, 1.0)  # C — 창 밖으로 밀려남
    assert tracker.poll(1.0).chord == "C"
    _play_triad(tracker, [43, 55, 59, 62], 4.0, 6.0, base_index=10)  # G2 G3 B3 D4
    ev = tracker.poll(6.0)
    assert ev is not None and ev.chord == "G"
