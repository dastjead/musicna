"""무음 감지 기반 트랙 경계 폴백 — 메타데이터가 없는 소스(브라우저 재생 등)용."""

from .pcm import rms_dbfs


class SilenceSplitter:
    """PCM 청크를 받아 '충분히 긴 무음'을 트랙 경계로 감지한다.

    경계는 무음 구간당 한 번만 보고하며, 소리를 들은 적이 없으면(시작 전 무음)
    경계로 치지 않는다.
    """

    def __init__(
        self,
        sample_rate: int = 48000,
        channels: int = 2,
        threshold_dbfs: float = -50.0,
        min_silence_s: float = 1.0,
    ) -> None:
        self._frame_bytes = channels * 4  # float32
        self._min_silence_frames = int(min_silence_s * sample_rate)
        self._threshold_dbfs = threshold_dbfs
        self._silent_frames = 0
        self._heard_sound = False
        self._reported = False

    @property
    def heard_sound(self) -> bool:
        """스트림 시작 이후 무음이 아닌 소리를 한 번이라도 들었는지."""
        return self._heard_sound

    def feed(self, chunk: bytes) -> bool:
        """청크 하나를 처리하고, 이 청크에서 경계가 확정되면 True."""
        if not chunk:
            return False
        frames = len(chunk) // self._frame_bytes
        if rms_dbfs(chunk) < self._threshold_dbfs:
            self._silent_frames += frames
            if (
                self._heard_sound
                and not self._reported
                and self._silent_frames >= self._min_silence_frames
            ):
                self._reported = True
                return True
        else:
            self._heard_sound = True
            self._silent_frames = 0
            self._reported = False
        return False
