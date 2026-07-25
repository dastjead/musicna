"""musicna-live 파이프라인 테스트 — 가짜 전사기·수집용 post로 전 구간 검증 (muscriptor 불필요)."""

import io
import types

import numpy as np

from musicna_api.live_cli import CAPTURE_SR, adapt_muscriptor_events, read_pcm_chunks, run_live
from musicna_core.models import LiveChord, LiveNoteOff, LiveNoteOn, LiveProgress


def _stereo_pcm(seconds):
    frames = int(CAPTURE_SR * seconds)
    return np.zeros(frames * 2, dtype=np.float32).tobytes()


def test_read_pcm_chunks_offsets_and_mono():
    stdin = io.BytesIO(_stereo_pcm(12.0))
    chunks = list(read_pcm_chunks(stdin, chunk_s=5.0))
    assert [round(off, 3) for _, off in chunks] == [0.0, 5.0, 10.0]
    assert chunks[0][0].shape == (CAPTURE_SR * 5,)  # 모노 다운믹스
    assert chunks[2][0].shape == (CAPTURE_SR * 2,)  # 마지막 부분 청크


def test_adapter_offsets_and_types():
    start = types.SimpleNamespace(pitch=60, start_time=1.0, index=3, instrument="acoustic_piano")
    end = types.SimpleNamespace(end_time=2.5, start_event=start)
    progress = types.SimpleNamespace(completed=1, total=2)  # 무시되어야 함
    events = list(adapt_muscriptor_events(iter([start, end, progress]), offset_s=10.0))
    assert events == [
        LiveNoteOn(index=3, pitch=60, instrument="acoustic_piano", start_s=11.0),
        LiveNoteOff(index=3, end_s=12.5),
    ]


def test_run_live_emits_notes_chords_progress():
    stdin = io.BytesIO(_stereo_pcm(5.0))

    def fake_transcribe(samples, sr):
        # C 트라이어드가 청크 내내 울리는 상황
        for i, p in enumerate([48, 60, 64, 67]):
            yield types.SimpleNamespace(pitch=p, start_time=0.0, index=i, instrument=None)

    batches = []
    chunks = run_live(stdin, fake_transcribe, batches.append, chunk_s=5.0)
    assert chunks == 1
    [events] = batches
    assert sum(isinstance(e, LiveNoteOn) for e in events) == 4
    chords = [e for e in events if isinstance(e, LiveChord)]
    assert chords and chords[0].chord == "C"  # 코드 변화는 1회만 산출
    assert len(chords) == 1
    [progress] = [e for e in events if isinstance(e, LiveProgress)]
    assert (progress.chunk_start_s, progress.chunk_end_s) == (0.0, 5.0)


def test_run_live_survives_post_failure():
    stdin = io.BytesIO(_stereo_pcm(5.0))

    def failing_post(events):
        raise ConnectionError("api down")

    assert run_live(stdin, lambda s, sr: iter([]), failing_post) == 1
