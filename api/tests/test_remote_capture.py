"""RemoteCaptureManager/RemoteCaptureSession 핵심 로직 — 실 muscriptor 불필요(가짜 transcribe_chunk)."""

import json
import wave

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


def test_stereo_downmix_for_transcription(manager):
    session_id = manager.start(TrackMeta(title="곡"), sample_rate=16000, channels=2, chunk_s=1.0)
    stereo = np.zeros(16000 * 2, dtype=np.float32)  # 1초 인터리브 스테레오
    events = manager.feed(session_id, stereo.tobytes())
    [progress] = [e for e in events if isinstance(e, LiveProgress)]
    assert (progress.chunk_start_s, progress.chunk_end_s) == (0.0, 1.0)
