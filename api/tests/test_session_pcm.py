"""세션 매니저 PCM 유틸 테스트 — float32 스트림 변환·레벨 측정."""

import math
import struct

import numpy as np

from musicna_api.session.pcm import float32_to_int16, rms_dbfs


def _f32_bytes(values: list[float]) -> bytes:
    return struct.pack(f"<{len(values)}f", *values)


def test_float32_to_int16_scales_and_clips():
    raw = _f32_bytes([0.0, 0.5, -0.5, 1.0, -1.0, 1.5, -1.5])
    out = np.frombuffer(float32_to_int16(raw), dtype=np.int16)
    assert out[0] == 0
    assert abs(int(out[1]) - 16383) <= 1
    assert abs(int(out[2]) + 16383) <= 1
    assert out[3] == 32767  # 클리핑 상한
    assert out[4] == -32767
    assert out[5] == 32767  # 1.0 초과 입력도 클리핑
    assert out[6] == -32767


def test_rms_dbfs_full_scale_sine_is_minus_3db():
    t = np.arange(4800, dtype=np.float32)
    sine = np.sin(2 * math.pi * 440 * t / 48000).astype(np.float32)
    level = rms_dbfs(sine.tobytes())
    assert abs(level - (-3.01)) < 0.1


def test_rms_dbfs_silence_hits_floor():
    silence = np.zeros(4800, dtype=np.float32)
    assert rms_dbfs(silence.tobytes()) <= -120.0
