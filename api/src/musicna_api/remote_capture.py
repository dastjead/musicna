"""원격 오디오 인제스트 — 네트워크 클라이언트(iOS 등)가 스트리밍하는 PCM을 로컬 캡처와
동일한 산출물(WAV+JSON 사이드카)로 저장하고, 동시에 실시간 미리보기 파이프라인(Phase 6)에도 흘린다.

로컬 캡처(session/cli.py)는 서브프로세스가 stdout을 파이프하지만, 원격 클라이언트는
네트워크 너머에 있으므로 REST로 청크를 업로드한다. 트랙 경계는 클라이언트가 명시적으로
통지한다(로컬의 AppleScript 폴링과 달리 추론이 필요 없다 — docs/superpowers/specs/
2026-07-26-central-deployment-ios-player-design.md 참조).
"""

import os
import re
import uuid
import wave
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import numpy as np
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from musicna_api.live import broadcaster
from musicna_api.live_cli import process_chunk
from musicna_api.session.pcm import float32_to_int16
from musicna_core.analyze.live_chords import LiveChordTracker
from musicna_core.models import LiveEvent, LiveTrackEnded, LiveTrackStarted, TrackMeta, live_event_adapter

_UNSAFE = re.compile(r'[/\\:?"<>|*\x00-\x1f]')
_INDEX_RE = re.compile(r"^(\d{3}) - ")


def _sanitize(name: str) -> str:
    return _UNSAFE.sub("_", name).strip()


def _next_index(out_dir: Path) -> int:
    max_index = 0
    for path in out_dir.glob("*.wav"):
        m = _INDEX_RE.match(path.name)
        if m:
            max_index = max(max_index, int(m.group(1)))
    return max_index + 1


def _default_transcribe_chunk(samples: np.ndarray, sample_rate: int) -> Iterator[Any]:
    from musicna_core.transcribe import stream_chunk_events

    return stream_chunk_events(samples, sample_rate, model_size="small")


class RemoteCaptureSession:
    """세션 하나(트랙 하나)의 WAV 조립 + 실시간 전사 상태."""

    def __init__(
        self,
        wav_path: Path,
        meta: TrackMeta,
        sample_rate: int,
        channels: int,
        transcribe_chunk: Callable[[np.ndarray, int], Iterator[Any]],
        chunk_s: float = 5.0,
        chord_poll_s: float = 1.0,
    ) -> None:
        self.wav_path = wav_path
        self.meta = meta
        self.sample_rate = sample_rate
        self.channels = channels
        self._transcribe_chunk = transcribe_chunk
        self._chord_poll_s = chord_poll_s
        self._chunk_frames = int(sample_rate * chunk_s)

        self._wav = wave.open(str(wav_path), "wb")
        self._wav.setnchannels(channels)
        self._wav.setsampwidth(2)
        self._wav.setframerate(sample_rate)

        self._tracker = LiveChordTracker()
        self._pending = np.zeros(0, dtype=np.float32)
        self._offset_s = 0.0

    def feed(self, raw_float32: bytes) -> list[LiveEvent]:
        """PCM 청크를 WAV에 기록하고, chunk_s 분량이 쌓일 때마다 실시간 이벤트를 산출한다."""
        frame_bytes = 4 * self.channels
        usable = len(raw_float32) - (len(raw_float32) % frame_bytes)
        if usable == 0:
            return []
        raw_float32 = raw_float32[:usable]

        self._wav.writeframes(float32_to_int16(raw_float32))

        samples = np.frombuffer(raw_float32, dtype=np.float32)
        if self.channels > 1:
            samples = samples.reshape(-1, self.channels).mean(axis=1)
        self._pending = np.concatenate([self._pending, samples])

        events: list[LiveEvent] = []
        while self._pending.size >= self._chunk_frames:
            chunk = self._pending[: self._chunk_frames]
            self._pending = self._pending[self._chunk_frames :]
            events.extend(
                process_chunk(
                    self._tracker, chunk, self.sample_rate, self._offset_s,
                    self._transcribe_chunk, self._chord_poll_s,
                )
            )
            self._offset_s += self._chunk_frames / self.sample_rate
        return events

    def finalize(self) -> None:
        """WAV를 닫고 TrackMeta 사이드카 JSON을 저장한다 (musicna-analyze가 그대로 집어감)."""
        self._wav.close()
        json_path = self.wav_path.with_suffix(".json")
        json_path.write_text(self.meta.model_dump_json(indent=2), encoding="utf-8")


class RemoteCaptureManager:
    """세션 생성·조회·종료 — session_id로 여러 원격 클라이언트를 동시에 추적."""

    def __init__(
        self,
        out_dir: Path,
        transcribe_chunk: Callable[[np.ndarray, int], Iterator[Any]] | None = None,
    ) -> None:
        self.out_dir = Path(out_dir)
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self._transcribe_chunk = transcribe_chunk or _default_transcribe_chunk
        self._sessions: dict[str, RemoteCaptureSession] = {}

    def start(self, meta: TrackMeta, sample_rate: int, channels: int, chunk_s: float = 5.0) -> str:
        session_id = uuid.uuid4().hex
        index = _next_index(self.out_dir)
        parts = [f"{index:03d}", *filter(None, [meta.artist, meta.title])]
        wav_path = self.out_dir / (_sanitize(" - ".join(parts)) + ".wav")
        self._sessions[session_id] = RemoteCaptureSession(
            wav_path, meta, sample_rate, channels, self._transcribe_chunk, chunk_s=chunk_s
        )
        return session_id

    def feed(self, session_id: str, raw_float32: bytes) -> list[LiveEvent]:
        return self._sessions[session_id].feed(raw_float32)

    def end(self, session_id: str) -> Path:
        session = self._sessions.pop(session_id)
        session.finalize()
        return session.wav_path


manager = RemoteCaptureManager(out_dir=Path(os.environ.get("MUSICNA_AUDIO_DIR", "data/audio")))

router = APIRouter(prefix="/remote/audio", tags=["remote-capture"])


def _publish(event: LiveEvent) -> None:
    broadcaster.publish(live_event_adapter.dump_json(event).decode())


class RemoteSessionStart(BaseModel):
    meta: TrackMeta
    sample_rate: int
    channels: int = 1


class RemoteSessionStartResponse(BaseModel):
    session_id: str


@router.post("/sessions", response_model=RemoteSessionStartResponse)
def start_session(body: RemoteSessionStart) -> RemoteSessionStartResponse:
    session_id = manager.start(body.meta, body.sample_rate, body.channels)
    _publish(LiveTrackStarted(track=body.meta))
    return RemoteSessionStartResponse(session_id=session_id)


@router.post("/sessions/{session_id}/chunk", status_code=202)
async def upload_chunk(session_id: str, request: Request) -> dict[str, int]:
    raw = await request.body()
    try:
        events = manager.feed(session_id, raw)
    except KeyError:
        raise HTTPException(status_code=404, detail="unknown session_id") from None
    for ev in events:
        _publish(ev)
    return {"accepted": len(events)}


@router.post("/sessions/{session_id}/end")
def end_session(session_id: str) -> dict[str, str]:
    try:
        wav_path = manager.end(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="unknown session_id") from None
    _publish(LiveTrackEnded())
    return {"wav_path": str(wav_path)}
