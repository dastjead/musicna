"""float32 PCM 스트림 유틸 — 캡처 헬퍼 출력(48kHz float32 interleaved)을 다룬다."""

import math

import numpy as np

_INT16_MAX = 32767
DBFS_FLOOR = -120.0


def float32_to_int16(raw: bytes) -> bytes:
    """float32 [-1, 1] 버퍼를 int16 PCM으로 변환한다. 범위 밖 값은 클리핑."""
    samples = np.frombuffer(raw, dtype=np.float32)
    clipped = np.clip(samples, -1.0, 1.0)
    return (clipped * _INT16_MAX).astype(np.int16).tobytes()


def rms_dbfs(raw: bytes) -> float:
    """float32 버퍼의 RMS 레벨(dBFS). 완전 무음은 DBFS_FLOOR."""
    samples = np.frombuffer(raw, dtype=np.float32)
    if samples.size == 0:
        return DBFS_FLOOR
    rms = float(np.sqrt(np.mean(np.square(samples, dtype=np.float64))))
    if rms <= 10 ** (DBFS_FLOOR / 20):
        return DBFS_FLOOR
    return 20.0 * math.log10(rms)
