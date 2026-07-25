"""musicna-live — 실시간 미리보기 전사 프로세스.

캡처 헬퍼의 PCM을 stdin으로 받아 5초 청크마다 muscriptor(small)로 전사하고,
노트·코드·진행 이벤트를 api 서버(/live/ingest)로 보낸다:

    ./capture-macos/.build/release/musicna-capture | uv run musicna-live

api 서버(uvicorn)가 떠 있어야 하며, 웹 UI의 실시간 뷰(/live.html)가 /ws/live로 구독한다.
녹음 세션(musicna-session)과 동시 실행은 캡처 장치 경합이 있을 수 있어 v1에서는 택일.
"""

import argparse
import json
import logging
import sys
import urllib.request
from collections.abc import Callable, Iterator
from typing import Any, BinaryIO

import numpy as np

from musicna_core.analyze.live_chords import LiveChordTracker
from musicna_core.models import LiveEvent, LiveNoteOff, LiveNoteOn, LiveProgress, live_event_adapter

logger = logging.getLogger(__name__)

CAPTURE_SR = 48000  # capture-macos 출력 규격: 48kHz float32 stereo interleaved
CAPTURE_CHANNELS = 2


def read_pcm_chunks(
    stdin: BinaryIO,
    chunk_s: float = 5.0,
    sample_rate: int = CAPTURE_SR,
    channels: int = CAPTURE_CHANNELS,
) -> Iterator[tuple[np.ndarray, float]]:
    """stdin의 float32 interleaved PCM을 (모노 청크, 시작 오프셋 초)로 산출한다."""
    frame_bytes = 4 * channels
    chunk_bytes = int(sample_rate * chunk_s) * frame_bytes
    offset_s = 0.0
    while True:
        buf = stdin.read(chunk_bytes)
        if not buf:
            return
        usable = len(buf) - (len(buf) % frame_bytes)
        if usable == 0:
            return
        frames = np.frombuffer(buf[:usable], dtype=np.float32).reshape(-1, channels)
        yield frames.mean(axis=1).copy(), offset_s
        offset_s += frames.shape[0] / sample_rate


def adapt_muscriptor_events(raw_events: Iterator[Any], offset_s: float) -> Iterator[LiveEvent]:
    """muscriptor 스트림 이벤트를 LiveEvent로 변환한다 (청크 오프셋을 트랙 기준 시각으로 환산).

    이벤트 판별은 속성 기반(duck typing) — NoteStartEvent(pitch/start_time/index/instrument),
    NoteEndEvent(end_time/start_event), ProgressEvent(그 외)를 가정한다.
    """
    for ev in raw_events:
        if hasattr(ev, "pitch") and hasattr(ev, "start_time"):
            yield LiveNoteOn(
                index=getattr(ev, "index", 0),
                pitch=ev.pitch,
                instrument=getattr(ev, "instrument", None),
                start_s=round(offset_s + ev.start_time, 3),
            )
        elif hasattr(ev, "end_time"):
            start_event = getattr(ev, "start_event", None)
            yield LiveNoteOff(
                index=getattr(start_event, "index", 0) if start_event is not None else 0,
                end_s=round(offset_s + ev.end_time, 3),
            )
        # ProgressEvent는 청크 단위 LiveProgress로 대체하므로 건너뛴다


def post_events(api_base: str, events: list[LiveEvent]) -> None:
    body = json.dumps(
        [json.loads(live_event_adapter.dump_json(e)) for e in events]
    ).encode()
    req = urllib.request.Request(
        f"{api_base}/live/ingest", data=body, headers={"Content-Type": "application/json"}
    )
    urllib.request.urlopen(req, timeout=5).read()


def run_live(
    stdin: BinaryIO,
    transcribe_chunk: Callable[[np.ndarray, int], Iterator[Any]],
    post: Callable[[list[LiveEvent]], None],
    chunk_s: float = 5.0,
    chord_poll_s: float = 1.0,
) -> int:
    """청크 전사 → 이벤트 변환 → 코드 추정 → 전송 루프. 처리한 청크 수를 돌려준다."""
    tracker = LiveChordTracker()
    chunks = 0
    for samples, offset_s in read_pcm_chunks(stdin, chunk_s=chunk_s):
        events: list[LiveEvent] = list(
            adapt_muscriptor_events(transcribe_chunk(samples, CAPTURE_SR), offset_s)
        )
        for ev in events:
            if isinstance(ev, LiveNoteOn):
                tracker.note_on(ev.index, ev.pitch, ev.start_s)
            elif isinstance(ev, LiveNoteOff):
                tracker.note_off(ev.index, ev.end_s)

        chunk_end = offset_s + samples.size / CAPTURE_SR
        t = offset_s + chord_poll_s
        while t <= chunk_end + 1e-9:
            if chord := tracker.poll(t):
                events.append(chord)
            t += chord_poll_s
        events.append(LiveProgress(chunk_start_s=round(offset_s, 3), chunk_end_s=round(chunk_end, 3)))

        try:
            post(events)
        except Exception:
            logger.exception("이벤트 전송 실패 — 계속 진행")
        chunks += 1
    return chunks


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="PCM stdin → muscriptor 실시간 전사 → api 이벤트 전송")
    parser.add_argument("--api", default="http://127.0.0.1:8000", help="api 서버 주소")
    parser.add_argument("--model-size", default="small", choices=["small", "medium", "large"])
    parser.add_argument("--chunk-s", type=float, default=5.0)
    args = parser.parse_args()

    from musicna_core.transcribe import stream_chunk_events

    def transcribe(samples: np.ndarray, sr: int) -> Iterator[Any]:
        return stream_chunk_events(samples, sr, model_size=args.model_size)

    chunks = run_live(sys.stdin.buffer, transcribe, lambda evs: post_events(args.api, evs), args.chunk_s)
    print(f"종료: 청크 {chunks}개 처리")
