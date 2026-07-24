"""무음 감지 기반 트랙 경계 폴백 테스트."""

import numpy as np

from musicna_api.session.silence import SilenceSplitter

SR = 48000
CH = 2


def _tone(seconds: float, amp: float = 0.5) -> bytes:
    n = int(SR * seconds)
    t = np.arange(n, dtype=np.float32)
    mono = (amp * np.sin(2 * np.pi * 440 * t / SR)).astype(np.float32)
    stereo = np.repeat(mono, CH)
    return stereo.tobytes()


def _silence(seconds: float) -> bytes:
    return np.zeros(int(SR * seconds) * CH, dtype=np.float32).tobytes()


def _feed_chunks(splitter: SilenceSplitter, data: bytes, chunk_frames: int = 4800) -> int:
    """0.1초 단위로 나눠 공급하고 경계 감지 횟수를 센다."""
    stride = chunk_frames * CH * 4
    boundaries = 0
    for i in range(0, len(data), stride):
        if splitter.feed(data[i : i + stride]):
            boundaries += 1
    return boundaries


def test_detects_single_boundary_in_gap():
    s = SilenceSplitter(sample_rate=SR, channels=CH, threshold_dbfs=-50.0, min_silence_s=1.0)
    audio = _tone(2.0) + _silence(1.5) + _tone(2.0)
    assert _feed_chunks(s, audio) == 1


def test_short_gap_is_not_a_boundary():
    s = SilenceSplitter(sample_rate=SR, channels=CH, threshold_dbfs=-50.0, min_silence_s=1.0)
    audio = _tone(2.0) + _silence(0.5) + _tone(2.0)
    assert _feed_chunks(s, audio) == 0


def test_leading_silence_is_not_a_boundary():
    s = SilenceSplitter(sample_rate=SR, channels=CH, threshold_dbfs=-50.0, min_silence_s=1.0)
    audio = _silence(3.0) + _tone(2.0)
    assert _feed_chunks(s, audio) == 0
