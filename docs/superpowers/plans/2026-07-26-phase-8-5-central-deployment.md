# Phase 8.5 — 중앙 배포 인프라 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** api 프로세스를 Mac mini에 상시 구동 서비스로 배포하고(launchd) Tailscale로 집 밖에서도 접근 가능하게 하며, TUI가 더 이상 자체적으로 api를 부팅하지 않고 상시 인스턴스에 접속만 하도록 바꾸고, 원격(iOS 등) 캡처 클라이언트가 오디오를 스트리밍해 기존 실시간 미리보기·배치 분석 파이프라인에 그대로 태울 수 있는 인제스트 엔드포인트를 추가한다.

**Architecture:** 실시간 청크 처리 로직(`live_cli.py`의 전사→코드추적→진행이벤트 산출)을 순수 함수 `process_chunk`로 추출해 로컬 CLI와 신규 원격 인제스트가 공유한다. 신규 `api/src/musicna_api/remote_capture.py`가 세션별 WAV 조립 + 실시간 브로드캐스트를 담당하고, `POST /remote/audio/sessions` → `chunk` → `end` 3단계 REST로 노출한다. TUI는 `ApiClient`의 기존 `base_url` 파라미터를 환경변수로 노출하고 로컬 부트스트랩 코드를 제거한다. 배포는 launchd LaunchAgent(자동 재시작) + Tailscale(원격 접근)로 구성한다.

**Tech Stack:** Python 3.12(uv 워크스페이스), FastAPI, numpy, 표준 라이브러리 `wave`, macOS `launchd`/Tailscale(코드 아님, OS 설정).

## Global Constraints

- 기존 145개 테스트(`uv run pytest core/tests api/tests tui/tests`)는 전 과정에서 계속 통과해야 한다 — 특히 Task 1은 `run_live`의 외부 동작을 절대 바꾸지 않는 순수 리팩터다.
- `core/`는 이 계획에서 건드리지 않는다(macOS API import 금지 원칙, 신규 코드는 전부 `api/`·`tui/`에 위치).
- muscriptor 등 무거운 ML 의존성은 지연 import 유지 — `remote_capture.py`를 import하는 것만으로 muscriptor가 필요해지면 안 된다(기존 `live_cli.py` 패턴과 동일).
- Tailscale·launchd 관련 Task(5·6·7)는 macOS 실기기에서만 검증 가능하다. 이 저장소의 개발 환경(원격 컨테이너일 수 있음)에서는 코드/설정 파일 작성까지만 하고, 실행·검증은 macOS 터미널에서 수행한다.
- 신규 Python 의존성 없음 — 전부 기존 워크스페이스 패키지(fastapi, numpy, httpx, pydantic)로 구현한다.

---

## Task 1: `live_cli.py`에서 청크 처리 로직을 `process_chunk`로 추출

Task 2(원격 인제스트)가 로컬 CLI와 동일한 전사→코드추적→진행이벤트 로직을 재사용해야 한다. 지금은 이 로직이 `run_live` 함수 안에 갇혀 있고 샘플레이트도 `CAPTURE_SR`(48000)로 하드코딩돼 있어, 다른 샘플레이트를 쓰는 원격 클라이언트가 재사용할 수 없다. 순수 함수로 뽑아내고 샘플레이트를 매개변수화한다 — `run_live`의 외부 동작(기존 테스트 5개)은 그대로 유지된다.

**Files:**
- Modify: `api/src/musicna_api/live_cli.py:86-119` (`run_live` 함수)
- Test: `api/tests/test_live_cli.py`

**Interfaces:**
- Produces: `process_chunk(tracker: LiveChordTracker, samples: np.ndarray, sample_rate: int, offset_s: float, transcribe_chunk: Callable[[np.ndarray, int], Iterator[Any]], chord_poll_s: float = 1.0) -> list[LiveEvent]` — Task 2가 이 함수를 `from musicna_api.live_cli import process_chunk`로 가져다 쓴다.

- [x] **Step 1: `process_chunk`를 호출하는 실패 테스트를 작성**

`api/tests/test_live_cli.py` 최상단 import에 `process_chunk`를 추가하고, 파일 끝에 아래 테스트를 추가한다:

```python
from musicna_core.analyze.live_chords import LiveChordTracker
from musicna_api.live_cli import CAPTURE_SR, adapt_muscriptor_events, process_chunk, read_pcm_chunks, run_live


def test_process_chunk_emits_notes_chords_progress():
    def fake_transcribe(samples, sr):
        for i, p in enumerate([48, 60, 64, 67]):
            yield types.SimpleNamespace(pitch=p, start_time=0.0, index=i, instrument=None)

    tracker = LiveChordTracker()
    samples = np.zeros(CAPTURE_SR * 5, dtype=np.float32)
    events = process_chunk(tracker, samples, CAPTURE_SR, 0.0, fake_transcribe, chord_poll_s=1.0)

    assert sum(isinstance(e, LiveNoteOn) for e in events) == 4
    chords = [e for e in events if isinstance(e, LiveChord)]
    assert chords and chords[0].chord == "C"
    assert len(chords) == 1
    [progress] = [e for e in events if isinstance(e, LiveProgress)]
    assert (progress.chunk_start_s, progress.chunk_end_s) == (0.0, 5.0)


def test_process_chunk_respects_sample_rate():
    """샘플레이트가 CAPTURE_SR과 달라도 진행 이벤트 구간이 정확해야 한다(원격 인제스트용 일반화)."""
    tracker = LiveChordTracker()
    samples = np.zeros(16000, dtype=np.float32)  # 16kHz 1초
    events = process_chunk(tracker, samples, 16000, 10.0, lambda s, sr: iter([]), chord_poll_s=1.0)
    [progress] = [e for e in events if isinstance(e, LiveProgress)]
    assert (progress.chunk_start_s, progress.chunk_end_s) == (10.0, 11.0)
```

`test_adapter_offsets_and_types` 바로 위에 있는 `import types`는 이미 파일 상단에 있으므로 추가 import 불필요. `LiveChord` import도 이미 상단에 있다.

- [x] **Step 2: 테스트 실행 → 실패 확인**

Run: `uv run pytest api/tests/test_live_cli.py -k process_chunk -v`
Expected: FAIL — `ImportError: cannot import name 'process_chunk'`

- [x] **Step 3: `run_live`에서 `process_chunk`를 추출하고 샘플레이트를 매개변수화**

`api/src/musicna_api/live_cli.py`의 86~119번 줄(`run_live` 함수 전체)을 아래로 교체:

```python
def process_chunk(
    tracker: LiveChordTracker,
    samples: np.ndarray,
    sample_rate: int,
    offset_s: float,
    transcribe_chunk: Callable[[np.ndarray, int], Iterator[Any]],
    chord_poll_s: float = 1.0,
) -> list[LiveEvent]:
    """청크 하나를 전사→노트추적→코드폴링→진행이벤트까지 처리해 LiveEvent 목록을 산출한다.

    로컬 CLI(`run_live`)와 원격 인제스트(`remote_capture.py`)가 공유하는 순수 함수 —
    부작용은 tracker 상태 갱신뿐이고, 전송(post)은 호출 측 책임이다.
    """
    events: list[LiveEvent] = list(
        adapt_muscriptor_events(transcribe_chunk(samples, sample_rate), offset_s)
    )
    for ev in events:
        if isinstance(ev, LiveNoteOn):
            tracker.note_on(ev.index, ev.pitch, ev.start_s)
        elif isinstance(ev, LiveNoteOff):
            tracker.note_off(ev.index, ev.end_s)

    chunk_end = offset_s + samples.size / sample_rate
    t = offset_s + chord_poll_s
    while t <= chunk_end + 1e-9:
        if chord := tracker.poll(t):
            events.append(chord)
        t += chord_poll_s
    events.append(LiveProgress(chunk_start_s=round(offset_s, 3), chunk_end_s=round(chunk_end, 3)))
    return events


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
        events = process_chunk(tracker, samples, CAPTURE_SR, offset_s, transcribe_chunk, chord_poll_s)
        try:
            post(events)
        except Exception:
            logger.exception("이벤트 전송 실패 — 계속 진행")
        chunks += 1
    return chunks
```

또한 파일 상단 import에 `LiveChordTracker`를 추가해야 한다(현재 `run_live` 안에서만 쓰이던 것을 `process_chunk`가 참조하지는 않지만 — 실제로는 `tracker`는 `process_chunk`의 매개변수로 전달되므로 `LiveChordTracker` 자체는 `run_live` 안에서만 인스턴스화된다. `live_cli.py` 상단의 기존 `from musicna_core.analyze.live_chords import LiveChordTracker` import는 그대로 둔다 — 삭제하지 말 것).

- [x] **Step 4: 전체 테스트 실행 → 신규+기존 모두 통과 확인**

Run: `uv run pytest api/tests/test_live_cli.py -v`
Expected: PASS — 기존 5개 + 신규 2개 = 7개 전부 통과

- [x] **Step 5: 커밋** (실제 커밋: `6e49cd0`)

```bash
git add api/src/musicna_api/live_cli.py api/tests/test_live_cli.py
git commit -m "refactor: live_cli의 청크 처리 로직을 process_chunk로 추출·샘플레이트 매개변수화"
```

---

## Task 2: `RemoteCaptureManager`/`RemoteCaptureSession` — 세션별 WAV 조립 + 실시간 이벤트 산출

원격 클라이언트가 보내는 PCM 청크를 받아 ① WAV로 누적 저장 ② `chunk_s`(기본 5초) 분량이 쌓일 때마다 Task 1의 `process_chunk`로 실시간 이벤트를 산출하는 핵심 로직. 아직 FastAPI 라우팅은 없음 — 순수 Python 단위로 테스트한다(muscriptor 불필요, 가짜 transcribe_chunk 주입).

**Files:**
- Create: `api/src/musicna_api/remote_capture.py`
- Test: `api/tests/test_remote_capture.py`

**Interfaces:**
- Consumes: `process_chunk` (Task 1), `LiveChordTracker`(`musicna_core.analyze.live_chords`), `float32_to_int16`(`musicna_api.session.pcm`), `TrackMeta`/`LiveEvent`(`musicna_core.models`)
- Produces: `RemoteCaptureManager(out_dir: Path, transcribe_chunk: Callable[[np.ndarray, int], Iterator[Any]] | None = None)` — `.start(meta: TrackMeta, sample_rate: int, channels: int, chunk_s: float = 5.0) -> str`(session_id), `.feed(session_id: str, raw_float32: bytes) -> list[LiveEvent]`(미지의 session_id면 `KeyError`), `.end(session_id: str) -> Path`(wav_path, 미지의 session_id면 `KeyError`). Task 3이 이 클래스를 라우터에서 사용한다.

- [ ] **Step 1: 실패하는 테스트를 작성**

`api/tests/test_remote_capture.py` 생성:

```python
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
```

- [ ] **Step 2: 테스트 실행 → 실패 확인**

Run: `uv run pytest api/tests/test_remote_capture.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'musicna_api.remote_capture'`

- [ ] **Step 3: `remote_capture.py` 구현 (핵심 로직만, 라우터는 Task 3에서 추가)**

`api/src/musicna_api/remote_capture.py` 생성:

```python
"""원격 오디오 인제스트 — 네트워크 클라이언트(iOS 등)가 스트리밍하는 PCM을 로컬 캡처와
동일한 산출물(WAV+JSON 사이드카)로 저장하고, 동시에 실시간 미리보기 파이프라인(Phase 6)에도 흘린다.

로컬 캡처(session/cli.py)는 서브프로세스가 stdout을 파이프하지만, 원격 클라이언트는
네트워크 너머에 있으므로 REST로 청크를 업로드한다. 트랙 경계는 클라이언트가 명시적으로
통지한다(로컬의 AppleScript 폴링과 달리 추론이 필요 없다 — docs/superpowers/specs/
2026-07-26-central-deployment-ios-player-design.md 참조).
"""

import re
import uuid
import wave
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import numpy as np

from musicna_api.live_cli import process_chunk
from musicna_api.session.pcm import float32_to_int16
from musicna_core.analyze.live_chords import LiveChordTracker
from musicna_core.models import LiveEvent, TrackMeta

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
        if not raw_float32:
            return []
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
```

- [ ] **Step 4: 테스트 실행 → 통과 확인**

Run: `uv run pytest api/tests/test_remote_capture.py -v`
Expected: PASS — 7개 전부

- [ ] **Step 5: 커밋**

```bash
git add api/src/musicna_api/remote_capture.py api/tests/test_remote_capture.py
git commit -m "feat: RemoteCaptureManager — 원격 PCM 청크를 WAV+실시간 이벤트로 처리"
```

---

## Task 3: `/remote/audio/*` REST 엔드포인트 + `main.py` 등록

`LiveBroadcaster` 싱글턴을 `main.py`에서 `live.py`로 옮겨 `remote_capture.py`와 순환 import 없이 공유하고, 세션 시작/청크 업로드/종료 3개 라우트를 추가한다.

**Files:**
- Modify: `api/src/musicna_api/live.py` (broadcaster 싱글턴 추가)
- Modify: `api/src/musicna_api/main.py:21-29` (import 정리, 라우터 등록)
- Modify: `api/src/musicna_api/remote_capture.py` (라우터 추가)
- Test: `api/tests/test_remote_capture_routes.py`

**Interfaces:**
- Consumes: `RemoteCaptureManager`(Task 2), `broadcaster`(공유 `LiveBroadcaster` 인스턴스, `live.py`로 이동)
- Produces: `POST /remote/audio/sessions` (body: `{meta: TrackMeta, sample_rate: int, channels: int=1}` → `{session_id: str}`), `POST /remote/audio/sessions/{id}/chunk` (raw bytes body → `{accepted: int}`, 미지의 id는 404), `POST /remote/audio/sessions/{id}/end` (→ `{wav_path: str}`, 미지의 id는 404). 모듈 전역 `manager: RemoteCaptureManager` — 테스트는 `monkeypatch.setattr(remote_capture, "manager", ...)`로 교체한다(`system.orchestrator`와 동일한 기존 패턴).

- [ ] **Step 1: 실패하는 라우트 테스트를 작성**

`api/tests/test_remote_capture_routes.py` 생성:

```python
"""remote_capture.py의 /remote/audio/* 엔드포인트 — FastAPI TestClient, manager는 fake로 교체."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from musicna_api import remote_capture
from musicna_api.remote_capture import RemoteCaptureManager


def _fake_transcribe(samples, sample_rate):
    return iter([])  # 노트 없음 — 라우팅·응답 형태만 검증


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("MUSICNA_DB", str(tmp_path / "remote.db"))
    import musicna_api.main as main

    main._session_factory.cache_clear()
    fake_manager = RemoteCaptureManager(out_dir=tmp_path / "audio", transcribe_chunk=_fake_transcribe)
    monkeypatch.setattr(remote_capture, "manager", fake_manager)
    return TestClient(main.app)


def _silence_bytes(seconds, sample_rate=16000):
    import numpy as np

    return np.zeros(int(sample_rate * seconds), dtype=np.float32).tobytes()


def test_full_session_lifecycle(client):
    meta = {"title": "테스트곡", "artist": "테스트", "source": "unknown"}
    r = client.post("/remote/audio/sessions", json={"meta": meta, "sample_rate": 16000, "channels": 1})
    assert r.status_code == 200
    session_id = r.json()["session_id"]

    r = client.post(
        f"/remote/audio/sessions/{session_id}/chunk",
        content=_silence_bytes(1.0),
        headers={"Content-Type": "application/octet-stream"},
    )
    assert r.status_code == 202

    r = client.post(f"/remote/audio/sessions/{session_id}/end")
    assert r.status_code == 200
    wav_path = Path(r.json()["wav_path"])
    assert wav_path.exists()
    assert wav_path.with_suffix(".json").exists()


def test_chunk_unknown_session_returns_404(client):
    r = client.post("/remote/audio/sessions/does-not-exist/chunk", content=_silence_bytes(0.1))
    assert r.status_code == 404


def test_end_unknown_session_returns_404(client):
    r = client.post("/remote/audio/sessions/does-not-exist/end")
    assert r.status_code == 404


def test_session_start_broadcasts_track_started(client):
    with client.websocket_connect("/ws/live") as ws:
        meta = {"title": "곡", "source": "unknown"}
        client.post("/remote/audio/sessions", json={"meta": meta, "sample_rate": 16000, "channels": 1})
        event = ws.receive_json()
        assert event["type"] == "track_started"
        assert event["track"]["title"] == "곡"


def test_session_end_broadcasts_track_ended(client):
    meta = {"title": "곡", "source": "unknown"}
    r = client.post("/remote/audio/sessions", json={"meta": meta, "sample_rate": 16000, "channels": 1})
    session_id = r.json()["session_id"]
    with client.websocket_connect("/ws/live") as ws:
        client.post(f"/remote/audio/sessions/{session_id}/end")
        event = ws.receive_json()
        assert event == {"type": "track_ended"}
```

- [ ] **Step 2: 테스트 실행 → 실패 확인**

Run: `uv run pytest api/tests/test_remote_capture_routes.py -v`
Expected: FAIL — `AttributeError: module 'musicna_api.remote_capture' has no attribute 'manager'` (라우터·매니저 싱글턴이 아직 없음)

- [ ] **Step 3: `live.py`에 broadcaster 싱글턴 추가**

`api/src/musicna_api/live.py` 파일 끝에 추가:

```python
broadcaster = LiveBroadcaster()
```

- [ ] **Step 4: `main.py`에서 broadcaster를 공유 인스턴스로 교체**

`api/src/musicna_api/main.py`의 아래 부분을 찾아:

```python
from musicna_api import player, system
from musicna_api.live import LiveBroadcaster
```

다음으로 교체:

```python
from musicna_api import player, remote_capture, system
from musicna_api.live import broadcaster
```

그리고 아래 부분:

```python
app = FastAPI(title="musicna", version="0.1.0")
app.include_router(player.router)
app.include_router(system.router)
broadcaster = LiveBroadcaster()
```

다음으로 교체:

```python
app = FastAPI(title="musicna", version="0.1.0")
app.include_router(player.router)
app.include_router(system.router)
app.include_router(remote_capture.router)
```

(`broadcaster.publish`/`.subscribe`/`.unsubscribe`를 쓰는 `live_ingest`/`ws_live` 함수는 무수정 — 같은 이름이 이제 `live.py`에서 임포트된 공유 인스턴스를 가리킬 뿐이다.)

- [ ] **Step 5: `remote_capture.py`에 라우터·매니저 싱글턴 추가**

`api/src/musicna_api/remote_capture.py` 상단 import에 추가:

```python
import os

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from musicna_api.live import broadcaster
from musicna_core.models import LiveTrackEnded, LiveTrackStarted, live_event_adapter
```

(`Path`는 이미 import돼 있음. `LiveEvent`/`TrackMeta`도 이미 import돼 있음.)

파일 끝에 추가:

```python
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
```

- [ ] **Step 6: 전체 테스트 실행 → 통과 확인**

Run: `uv run pytest api/tests -v`
Expected: PASS — 기존 전부 + 신규 5개(`test_remote_capture_routes.py`)

- [ ] **Step 7: 커밋**

```bash
git add api/src/musicna_api/live.py api/src/musicna_api/main.py api/src/musicna_api/remote_capture.py api/tests/test_remote_capture_routes.py
git commit -m "feat: /remote/audio/* 엔드포인트 — 원격 PCM 인제스트를 실시간·배치 파이프라인에 연결"
```

---

## Task 4: TUI — 자체 api 부트스트랩 제거, `MUSICNA_API_URL`로 접속 주소 설정

TUI가 더 이상 로컬 uvicorn을 스스로 띄우지 않고, 웹과 동일하게 상시 구동 중인 api(로컬 또는 Tailscale 경유 원격)에 접속만 하는 클라이언트가 된다. `ApiClient`는 이미 `base_url` 파라미터를 받으므로 변경 불필요 — `base_url` 조회용 프로퍼티만 추가한다.

**Files:**
- Modify: `tui/src/musicna_tui/client.py` (프로퍼티 추가)
- Modify: `tui/src/musicna_tui/app.py` (부트스트랩 제거, env var 적용)
- Modify: `tui/tests/test_app.py` (부트스트랩 테스트 제거, 신규 테스트 추가)

**Interfaces:**
- Produces: `ApiClient.base_url -> str` (프로퍼티). `MusicnaApp()`은 환경변수 `MUSICNA_API_URL`(기본값 `http://127.0.0.1:8000`)로 `ApiClient`를 구성한다. `ensure_api_running` 함수는 삭제된다.

- [ ] **Step 1: `ApiClient`에 `base_url` 프로퍼티를 요구하는 실패 테스트 작성**

`tui/tests/test_client.py`에 아래 테스트를 추가한다(파일 끝):

```python
def test_base_url_property_reflects_constructor_arg():
    client = ApiClient(base_url="http://mac-mini.tailnet.ts.net:8000")
    assert client.base_url == "http://mac-mini.tailnet.ts.net:8000"
```

- [ ] **Step 2: 테스트 실행 → 실패 확인**

Run: `uv run pytest tui/tests/test_client.py -k base_url -v`
Expected: FAIL — `AttributeError: 'ApiClient' object has no attribute 'base_url'`

- [ ] **Step 3: `ApiClient`에 프로퍼티 추가**

`tui/src/musicna_tui/client.py`의 `close` 메서드 앞에 추가:

```python
    @property
    def base_url(self) -> str:
        return str(self._http.base_url)
```

- [ ] **Step 4: 테스트 실행 → 통과 확인**

Run: `uv run pytest tui/tests/test_client.py -v`
Expected: PASS

- [ ] **Step 5: `app.py`에서 부트스트랩 제거, env var 적용을 검증하는 실패 테스트 작성**

`tui/tests/test_app.py`를 아래 내용으로 전체 교체한다(기존 `ensure_api_running` 관련 3개 테스트·`_make_advancing_clock`·`subprocess`/`time` import를 제거하고, env var 테스트를 추가):

```python
"""MusicnaApp 테스트 — 상시 api에 접속만 하는 클라이언트(Phase 8.5)."""

import pytest

from musicna_tui.app import DEFAULT_API_URL, MusicnaApp
from musicna_tui.widgets.player_panel import PlayerPanel
from musicna_tui.widgets.session_status import SessionStatus


def test_app_uses_default_api_url_when_env_unset(monkeypatch):
    monkeypatch.delenv("MUSICNA_API_URL", raising=False)
    app = MusicnaApp()
    assert app.client.base_url == DEFAULT_API_URL


def test_app_uses_musicna_api_url_env_var(monkeypatch):
    monkeypatch.setenv("MUSICNA_API_URL", "http://mac-mini.tailnet.ts.net:8000")
    app = MusicnaApp()
    assert app.client.base_url == "http://mac-mini.tailnet.ts.net:8000"


@pytest.mark.asyncio
async def test_app_composes_player_panel_and_session_status(monkeypatch):
    app = MusicnaApp()
    monkeypatch.setattr(app.client, "system_start", lambda: {"spotify_player_daemon": True, "session_capturing": False})
    async with app.run_test() as pilot:
        await pilot.pause()
        assert pilot.app.query_one(PlayerPanel) is not None
        assert pilot.app.query_one(SessionStatus) is not None


@pytest.mark.asyncio
async def test_app_exits_with_message_when_system_start_fails(monkeypatch):
    """system_start 실패(api 연결 불가 등)는 화면 크래시가 아니라 App.exit(message=...) 호출로 종료해야 한다."""
    app = MusicnaApp()

    def _raise():
        raise RuntimeError("연결 실패")

    monkeypatch.setattr(app.client, "system_start", _raise)
    exit_calls = []
    monkeypatch.setattr(app, "exit", lambda *a, **kw: exit_calls.append(kw))

    async with app.run_test() as pilot:
        await pilot.pause()

    assert len(exit_calls) == 1
    assert "연결 실패" in exit_calls[0]["message"]
```

- [ ] **Step 6: 테스트 실행 → 실패 확인**

Run: `uv run pytest tui/tests/test_app.py -v`
Expected: FAIL — `ImportError: cannot import name 'DEFAULT_API_URL'`

- [ ] **Step 7: `app.py`를 부트스트랩 없는 버전으로 교체**

`tui/src/musicna_tui/app.py` 전체를 아래로 교체:

```python
"""musicna TUI 진입점 — 상시 구동 중인 api 서버에 접속해 통합 대시보드를 표시한다.

api/system.py가 오케스트레이션(spotify_player 데몬·세션 캡처)을 소유한다. 이 앱은
웹 UI와 동일하게 api에 접속만 하는 순수 클라이언트다(Phase 8.5) — api는 Mac mini에서
launchd로 상시 구동되며, MUSICNA_API_URL 환경변수로 접속 주소를 지정한다
(기본값은 로컬 개발용, docs/PLAN.md 참조).
"""

import os

from textual.app import App, ComposeResult
from textual.widgets import Footer, Header

from musicna_tui.client import ApiClient
from musicna_tui.widgets.player_panel import PlayerPanel
from musicna_tui.widgets.session_status import SessionStatus

DEFAULT_API_URL = "http://127.0.0.1:8000"


class MusicnaApp(App):
    """musicna 통합 대시보드 — 재생 제어 + 세션 상태."""

    CSS = """
    PlayerPanel { height: 3; border: round $accent; padding: 0 1; }
    SessionStatus { height: 3; border: round $accent; padding: 0 1; }
    """

    def __init__(self) -> None:
        super().__init__()
        base_url = os.environ.get("MUSICNA_API_URL", DEFAULT_API_URL)
        self.client = ApiClient(base_url=base_url)

    def compose(self) -> ComposeResult:
        yield Header()
        yield PlayerPanel(self.client)
        yield SessionStatus(self.client)
        yield Footer()

    def on_mount(self) -> None:
        try:
            self.client.system_start()
        except Exception as e:
            self.exit(message=f"musicna 기동 실패: {e}")

    def on_unmount(self) -> None:
        self.client.close()


def run() -> None:
    MusicnaApp().run()


if __name__ == "__main__":
    run()
```

- [ ] **Step 8: 전체 TUI 테스트 실행 → 통과 확인**

Run: `uv run pytest tui/tests -v`
Expected: PASS — 전부

- [ ] **Step 9: 커밋**

```bash
git add tui/src/musicna_tui/client.py tui/src/musicna_tui/app.py tui/tests/test_app.py tui/tests/test_client.py
git commit -m "refactor: TUI 자체 api 부트스트랩 제거 — MUSICNA_API_URL로 상시 api에 접속(Phase 8.5)"
```

---

## Task 5: launchd LaunchAgent — Mac mini에서 api 상시 구동

**Files:**
- Create: `deploy/macos/com.musicna.api.plist`
- Create: `deploy/macos/install.sh`

**Interfaces:** 없음(코드 아님, macOS 실기기 전용 설정 파일).

- [ ] **Step 1: plist 템플릿 작성**

`deploy/macos/com.musicna.api.plist` 생성:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.musicna.api</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/zsh</string>
        <string>-lc</string>
        <string>cd __REPO_ROOT__ && uv run uvicorn musicna_api.main:app --host 0.0.0.0 --port 8000</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>__HOME__/Library/Logs/musicna-api.log</string>
    <key>StandardErrorPath</key>
    <string>__HOME__/Library/Logs/musicna-api.error.log</string>
</dict>
</plist>
```

(`--host 0.0.0.0`이 필요하다 — Tailscale·LAN 인터페이스에서 접근하려면 기본값 127.0.0.1로는 안 된다. 공인 인터넷 노출은 이 바인딩이 아니라 홈 라우터의 포트포워딩 미설정으로 막는다 — 라우터에 8000번 포트를 외부로 포워딩하지 않았는지 별도 확인 필요.)

- [ ] **Step 2: 설치 스크립트 작성**

`deploy/macos/install.sh` 생성:

```bash
#!/bin/bash
# musicna api를 launchd LaunchAgent로 등록한다. 이 저장소 루트에서 실행할 것.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PLIST_SRC="$REPO_ROOT/deploy/macos/com.musicna.api.plist"
PLIST_DST="$HOME/Library/LaunchAgents/com.musicna.api.plist"

mkdir -p "$HOME/Library/LaunchAgents"
sed -e "s|__REPO_ROOT__|$REPO_ROOT|g" -e "s|__HOME__|$HOME|g" "$PLIST_SRC" > "$PLIST_DST"

launchctl unload "$PLIST_DST" 2>/dev/null || true
launchctl load -w "$PLIST_DST"

echo "설치 완료: $PLIST_DST"
echo "확인: launchctl list | grep com.musicna.api"
echo "로그: tail -f $HOME/Library/Logs/musicna-api.log"
```

- [ ] **Step 3: 실행 권한 부여**

```bash
chmod +x deploy/macos/install.sh
```

- [ ] **Step 4: (macOS 실기기) 설치 및 검증**

Run: `./deploy/macos/install.sh`
Expected: "설치 완료" 출력

Run: `launchctl list | grep com.musicna.api`
Expected: PID와 상태코드 0이 출력됨(에러 시 음수 코드 — `cat ~/Library/Logs/musicna-api.error.log`로 원인 확인)

Run: `curl http://127.0.0.1:8000/health`
Expected: `{"status":"ok"}`

Run: 터미널을 닫고 재접속 후 다시 `curl http://127.0.0.1:8000/health`
Expected: 여전히 `{"status":"ok"}` — 터미널 세션과 무관하게 살아있음을 확인

- [ ] **Step 5: 커밋**

```bash
git add deploy/macos/com.musicna.api.plist deploy/macos/install.sh
git commit -m "feat: launchd LaunchAgent로 api 상시 구동 설정 추가 (Phase 8.5)"
```

---

## Task 6: Tailscale 설치·설정 — 원격 접근

**Files:** 없음(전부 macOS/iOS GUI·Tailscale 관리 콘솔 조작). PROGRESS.md 갱신은 Task 7에서 결과와 함께 기록.

**Interfaces:** 없음.

- [ ] **Step 1: (macOS 실기기) Mac mini에 Tailscale 설치**

Run: `brew install --cask tailscale` (또는 App Store판)
Tailscale 앱 실행 → 계정으로 로그인(Google/GitHub/이메일 등) → "Connected" 상태 확인

- [ ] **Step 2: (macOS 실기기) MagicDNS 활성화 확인**

Tailscale 관리 콘솔(https://login.tailscale.com/admin/dns) → MagicDNS가 켜져 있는지 확인(기본으로 켜져 있음)

Run: `tailscale status`
Expected: Mac mini 자신의 디바이스명과 tailnet IP(100.x.x.x)가 표시됨

Run: `tailscale ip -4`
Expected: `100.x.x.x` 형태의 IP 하나 출력 — 이 IP 또는 `<디바이스명>.<tailnet>.ts.net` 호스트네임이 이후 클라이언트 접속 주소가 됨

- [ ] **Step 3: (다른 기기 — iPhone/노트북 등) 같은 tailnet에 가입**

해당 기기에 Tailscale 앱 설치 → 같은 계정으로 로그인 → "Connected" 확인

- [ ] **Step 4: (다른 기기) Mac mini의 api에 원격 접속 확인**

같은 기기에서 브라우저로 `http://<mac-mini-hostname>.<tailnet>.ts.net:8000/health` 접속
Expected: `{"status":"ok"}` 표시 — 집 밖 네트워크(예: 모바일 데이터로 전환)에서도 동일하게 확인

- [ ] **Step 5: 결과를 PROGRESS.md에 기록** (Task 7에서 마일스톤과 함께 일괄 기록)

---

## Task 7: 전체 마일스톤 검증 + 문서 갱신

**Files:**
- Modify: `docs/PROGRESS.md` (Phase 8.5 체크리스트 완료 표시, 검증 기록 추가)

**Interfaces:** 없음.

- [ ] **Step 1: (macOS 실기기) TUI가 원격 api에 접속되는지 확인**

Mac mini가 아닌 다른 머신(또는 같은 Mac의 다른 터미널 세션에서 `MUSICNA_API_URL`을 Tailscale 주소로 지정)에서:

Run: `MUSICNA_API_URL=http://<mac-mini-hostname>.<tailnet>.ts.net:8000 uv run musicna-tui`
Expected: TUI가 뜨고 `PlayerPanel`에 Mac mini에서 실제 재생 중인 곡 정보가 표시됨(재생 중이 아니면 빈 상태) — space/n 키가 Mac mini의 실제 spotify_player를 제어하는지 확인

- [ ] **Step 2: (macOS 실기기) 집 밖에서 라이브러리 조회 확인**

휴대폰 등 다른 tailnet 기기에서 모바일 데이터(집 wifi 아님)로 전환 후 `http://<mac-mini-hostname>.<tailnet>.ts.net:8000/`(웹 UI) 접속
Expected: 라이브러리 트랙 목록이 정상 렌더됨

- [ ] **Step 3: 재부팅 복구 확인**

Mac mini를 재부팅(또는 로그아웃 후 재로그인)
Expected: 자동 로그인 후 별도 조작 없이 `curl http://127.0.0.1:8000/health`가 곧 `{"status":"ok"}` 응답(launchd가 재기동)

- [ ] **Step 4: `docs/PROGRESS.md` 갱신**

Phase 8.5 체크리스트의 5개 항목을 전부 `[x]`로 변경하고, "실기기 검증 상세 기록" 섹션에 Task 1~7 검증 결과(위 Step 1~3의 실제 확인 내용, 발견된 문제가 있었다면 그 원인·수정)를 기존 Phase 1·2·7 기록과 같은 형식으로 추가한다. 작업 로그 표에도 한 줄 추가한다.

- [ ] **Step 5: 커밋 및 푸시**

```bash
git add docs/PROGRESS.md
git commit -m "docs: Phase 8.5 실기기 검증 기록 — Tailscale+launchd 상시 배포 확인"
git push
```

---

## Self-Review 메모

- **스펙 커버리지**: 설계 스펙의 "Phase 8.5" 항목(Tailscale·launchd·단일 api 프로세스·원격 인제스트) 전부 Task 1~7에 매핑됨. "TUI 자체 부팅 제거"는 Task 4. iOS 클라이언트 자체(Phase 10)는 이 계획 범위 밖 — 별도 계획에서 다룸.
- **플레이스홀더 스캔**: 없음 — 전 Task가 실행 가능한 코드·명령으로 작성됨.
- **타입 일관성**: `process_chunk` 시그니처(Task 1에서 정의)가 Task 2의 `RemoteCaptureSession.feed`에서 쓰는 인자 순서(`tracker, samples, sample_rate, offset_s, transcribe_chunk, chord_poll_s`)와 일치. `RemoteCaptureManager.start/feed/end`(Task 2에서 정의)가 Task 3 라우터에서 쓰는 시그니처와 일치.
