"""RemoteCaptureManager/RemoteCaptureSession 핵심 로직 — 실 muscriptor 불필요(가짜 transcribe_chunk)."""

import json
import wave
from datetime import datetime, timedelta

import numpy as np
import pytest

from musicna_api.remote_capture import RemoteCaptureManager
from musicna_core.models import LiveChord, LiveNoteOn, LiveProgress, TrackMeta


def _fake_transcribe(samples, sample_rate):
    for i, p in enumerate([48, 60, 64, 67]):
        yield type("Note", (), {"pitch": p, "start_time": 0.0, "index": i, "instrument": None})()


def _silence(seconds, sample_rate):
    return np.zeros(int(sample_rate * seconds), dtype=np.float32).tobytes()


@pytest.fixture
def manager(tmp_path):
    return RemoteCaptureManager(out_dir=tmp_path, transcribe_chunk=_fake_transcribe)


def test_start_creates_wav_immediately(manager, tmp_path):
    meta = TrackMeta(title="곡", artist="아티스트")
    manager.start(meta, sample_rate=16000, channels=1, chunk_s=1.0)
    wavs = list(tmp_path.glob("*.wav"))
    assert len(wavs) == 1
    assert wavs[0].name.startswith("001 - 아티스트 - 곡")


def test_feed_below_chunk_threshold_returns_no_events(manager):
    session_id = manager.start(TrackMeta(title="곡"), sample_rate=16000, channels=1, chunk_s=5.0)
    assert manager.feed(session_id, _silence(1.0, 16000)) == []


def test_feed_reaching_chunk_threshold_emits_notes_and_progress(manager):
    session_id = manager.start(TrackMeta(title="곡"), sample_rate=16000, channels=1, chunk_s=1.0)
    events = manager.feed(session_id, _silence(1.0, 16000))
    assert sum(isinstance(e, LiveNoteOn) for e in events) == 4
    assert any(isinstance(e, LiveChord) for e in events)
    [progress] = [e for e in events if isinstance(e, LiveProgress)]
    assert (progress.chunk_start_s, progress.chunk_end_s) == (0.0, 1.0)


def test_end_writes_json_sidecar_and_closes_wav(manager):
    meta = TrackMeta(title="곡", artist="아티스트", source="unknown")
    session_id = manager.start(meta, sample_rate=16000, channels=1, chunk_s=5.0)
    manager.feed(session_id, _silence(0.5, 16000))
    wav_path = manager.end(session_id)

    assert wav_path.exists()
    json_path = wav_path.with_suffix(".json")
    assert json.loads(json_path.read_text())["title"] == "곡"
    with wave.open(str(wav_path), "rb") as w:
        assert w.getnframes() == 8000  # 0.5s @ 16kHz mono


def test_feed_unknown_session_raises_keyerror(manager):
    with pytest.raises(KeyError):
        manager.feed("nope", b"")


def test_end_unknown_session_raises_keyerror(manager):
    with pytest.raises(KeyError):
        manager.end("nope")


def test_lock_for_returns_lock_after_start(manager):
    session_id = manager.start(TrackMeta(title="곡"), sample_rate=16000, channels=1)
    import asyncio

    assert isinstance(manager.lock_for(session_id), asyncio.Lock)


def test_lock_for_unknown_session_raises_keyerror(manager):
    with pytest.raises(KeyError):
        manager.lock_for("nope")


def test_lock_for_raises_keyerror_after_end(manager):
    session_id = manager.start(TrackMeta(title="곡"), sample_rate=16000, channels=1)
    manager.end(session_id)
    with pytest.raises(KeyError):
        manager.lock_for(session_id)


def test_stereo_downmix_for_transcription(manager):
    session_id = manager.start(TrackMeta(title="곡"), sample_rate=16000, channels=2, chunk_s=1.0)
    stereo = np.zeros(16000 * 2, dtype=np.float32)  # 1초 인터리브 스테레오
    events = manager.feed(session_id, stereo.tobytes())
    [progress] = [e for e in events if isinstance(e, LiveProgress)]
    assert (progress.chunk_start_s, progress.chunk_end_s) == (0.0, 1.0)


def test_start_stamps_captured_at_when_missing(manager):
    """캡처 시각을 안 보내는 원격 클라이언트(향후 iOS 앱)도 유일한 captured_at을 받아야 한다.

    core/store/repository.py의 has_analysis()는 (title, artist, captured_at)로 dedup하므로,
    captured_at=None이 그대로 남으면 같은 제목의 두 번째 녹음이 "이미 분석됨"으로 오인되어
    유실된다 — 서버가 수신 시각을 스탬프해서 막는다.
    """
    meta = TrackMeta(title="곡")
    assert meta.captured_at is None

    before = datetime.now()
    session_id = manager.start(meta, sample_rate=16000, channels=1)
    after = datetime.now()

    session = manager._sessions[session_id]
    assert session.meta.captured_at is not None
    assert before - timedelta(seconds=1) <= session.meta.captured_at <= after + timedelta(seconds=1)


def test_feed_non_frame_aligned_chunk_trims_without_error(manager):
    """Non-frame-aligned PCM chunks should be trimmed, not raise ValueError."""
    session_id = manager.start(TrackMeta(title="곡"), sample_rate=16000, channels=1, chunk_s=5.0)
    # 0.5 seconds = 8000 samples = 32000 bytes for mono float32
    # Add 3 trailing bytes that don't complete a frame (4 bytes per sample)
    silence_bytes = _silence(0.5, 16000)
    non_aligned = silence_bytes + b"\x00\x00\x00"  # 32003 bytes total

    # Should not raise ValueError; instead trim to 32000 bytes and return no events
    events = manager.feed(session_id, non_aligned)
    assert events == []

    # Finalize and verify WAV has exactly 8000 frames (the trailing 3 bytes discarded)
    wav_path = manager.end(session_id)
    with wave.open(str(wav_path), "rb") as w:
        assert w.getnframes() == 8000
