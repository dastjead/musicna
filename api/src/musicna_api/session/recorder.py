"""트랙 레코더 — 메타데이터 전환을 경계로 PCM 스트림을 트랙별 WAV로 저장.

각 트랙은 `NNN - Artist - Title.wav`와 같은 이름의 int16 WAV,
그리고 동일 이름의 `.json` 사이드카(core의 TrackMeta 스키마)로 저장된다.
"""

import re
import wave
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from musicna_core.models import CaptureSource, TrackMeta

from .metadata import NowPlaying
from .pcm import float32_to_int16

_UNSAFE = re.compile(r'[/\\:?"<>|*\x00-\x1f]')


def _sanitize(name: str) -> str:
    return _UNSAFE.sub("_", name).strip()


@dataclass
class FinishedTrack:
    wav_path: Path
    json_path: Path
    meta: TrackMeta
    frames: int


class TrackRecorder:
    def __init__(self, out_dir: Path | str, sample_rate: int = 48000, channels: int = 2) -> None:
        self._out_dir = Path(out_dir)
        self._out_dir.mkdir(parents=True, exist_ok=True)
        self._sample_rate = sample_rate
        self._channels = channels
        self._index = 0
        self._wav: wave.Wave_write | None = None
        self._wav_path: Path | None = None
        self._now: NowPlaying | None = None
        self._started_at: datetime | None = None
        self._finished: list[FinishedTrack] = []

    def update_metadata(self, now: NowPlaying | None) -> None:
        """폴링된 재생 정보를 반영한다. 트랙이 바뀌면 이전 트랙을 확정한다.

        None(조회 실패)과 일시정지는 현재 트랙을 유지한다 — 같은 트랙 재개 시
        파일이 쪼개지지 않도록.
        """
        if now is None or not now.is_playing:
            return
        if self._now is not None and self._now.track_key == now.track_key:
            return
        self._finish_current()
        self._start_track(now)

    def feed(self, raw_float32: bytes) -> None:
        """PCM 청크를 현재 트랙에 기록한다. 활성 트랙이 없으면 버린다."""
        if self._wav is None or not raw_float32:
            return
        self._wav.writeframes(float32_to_int16(raw_float32))

    def finalize(self) -> list[FinishedTrack]:
        """현재 트랙을 닫고 완료된 트랙 목록을 반환한다."""
        self._finish_current()
        return list(self._finished)

    def _start_track(self, now: NowPlaying) -> None:
        self._index += 1
        parts = [f"{self._index:03d}", *filter(None, [now.artist, now.title])]
        filename = _sanitize(" - ".join(parts)) + ".wav"
        self._wav_path = self._out_dir / filename
        self._wav = wave.open(str(self._wav_path), "wb")
        self._wav.setnchannels(self._channels)
        self._wav.setsampwidth(2)
        self._wav.setframerate(self._sample_rate)
        self._now = now
        self._started_at = datetime.now()

    def _finish_current(self) -> None:
        if self._wav is None or self._wav_path is None or self._now is None:
            return
        frames = self._wav.getnframes()
        self._wav.close()

        try:
            source = CaptureSource(self._now.source)
        except ValueError:
            source = CaptureSource.UNKNOWN
        meta = TrackMeta(
            title=self._now.title,
            artist=self._now.artist,
            album=self._now.album,
            source=source,
            duration_s=self._now.duration_s,
            captured_at=self._started_at,
        )
        json_path = self._wav_path.with_suffix(".json")
        json_path.write_text(meta.model_dump_json(indent=2), encoding="utf-8")

        self._finished.append(
            FinishedTrack(wav_path=self._wav_path, json_path=json_path, meta=meta, frames=frames)
        )
        self._wav = None
        self._wav_path = None
        self._now = None
        self._started_at = None
