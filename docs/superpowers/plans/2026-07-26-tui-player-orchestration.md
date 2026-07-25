# Phase 7 — 재생 엔진·오케스트레이션 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** musicna가 `spotify_player`(Homebrew/cargo, librespot 기반)를 서브프로세스로 구동해 스스로 Spotify Connect 기기가 되고, `api/`가 재생 제어(`/player/*`)와 백그라운드 프로세스 오케스트레이션(`/system/*`)을 REST로 노출하며, 최소 TUI 셸(플레이어 패널 + 세션 상태)에서 실제로 조작할 수 있게 한다.

**Architecture:** `api/`에 두 신규 모듈(`player.py`: spotify_player 데몬·CLI 제어, `system.py`: 데몬+세션 캡처 프로세스 오케스트레이션)을 추가하고 `main.py`에 라우터로 등록한다. 기존 "spotify" 소스 메타데이터 폴링(AppleScript)을 spotify_player 상태 폴링으로 교체한다(Apple Music 소스는 무수정). 신규 최상위 패키지 `tui/`(Python+Textual)가 `api/`만 호출하는 얇은 클라이언트로 대시보드를 그린다.

**Tech Stack:** Python 3.12, FastAPI(기존), Textual(신규, TUI), httpx(신규, tui의 api 클라이언트), pytest-asyncio(신규, tui의 Pilot 테스트), spotify_player 0.24+(외부 바이너리, cargo `daemon` feature 필요).

## Global Constraints

- Python 3.11+ (`.python-version`=3.12), uv 워크스페이스 — 새 패키지는 `[tool.uv.workspace] members`에 추가
- `core/`는 이 작업 범위에서 무수정 — macOS API·외부 프로세스 오케스트레이션은 전부 `api/`와 `tui/`에만 위치
- 캡처 파이프라인(ScreenCaptureKit, `capture-macos/`)은 무수정 — 이 계획은 재생 제어와 "spotify" 소스 메타데이터 공급자 교체만 다룬다
- 푸시는 `claude/music-analysis-app-planning-rsfa6x` 브랜치로만
- 커밋마다 `docs/PROGRESS.md`를 갱신하는 것이 프로젝트 관례이나, 이 계획 자체는 코드 작업에 집중하고 마지막 Task에서 PROGRESS.md 갱신을 다룬다

## 사전 준비 (구현 시작 전, 사용자 확인 필요)

`spotify_player`의 헤드리스(`-d`/`--daemon`) 모드는 Cargo `daemon` feature가 필요하다 — Homebrew 기본 배포판(`brew install spotify_player`)은 이 feature 없이 빌드되어 있어(`features = ["image", "notify"]`만 포함) `-d` 플래그가 동작하지 않는다(실측 확인: 이 머신에 설치된 0.24.1 `--help`에 daemon 옵션 없음). 대신 아래로 재설치해야 한다(cargo/rustc는 이미 Homebrew로 설치되어 있음, 실측 확인):

```bash
cargo install spotify_player --locked --features daemon,image,notify
```

이 명령은 시간이 걸리는 빌드(오디오 백엔드·이미지 처리 등 의존성 컴파일)이고 기존 Homebrew 설치를 대체하는 작업이므로 **Task 3 실행 전에 사용자에게 확인받고 실행한다**. 또한 `spotify_player authenticate`로 최초 1회 OAuth 인증이 되어 있어야 한다(이 머신은 이미 인증됨 — 실측 확인: `spotify_player get key devices`가 기존 등록된 "spotify-player" 기기를 반환함).

---

## 파일 구조

**`api/` (확장)**
- `api/src/musicna_api/player.py` (신규) — `PlayerStatus`/`PlayerDevice` 모델, JSON 파서, CLI 명령 래퍼, `SpotifyPlayerDaemon`, `/player/*` FastAPI 라우터
- `api/src/musicna_api/session/metadata.py` (확장) — spotify_player 기반 "spotify" 소스 조회로 교체, 죽은 AppleScript 코드 제거
- `api/src/musicna_api/system.py` (신규) — `SystemOrchestrator`(데몬+세션 프로세스 관리), `/system/*` FastAPI 라우터
- `api/src/musicna_api/main.py` (확장) — 두 라우터 등록
- `api/tests/test_player.py`, `api/tests/test_system.py` (신규)
- `api/tests/test_session_metadata.py` (확장)

**`tui/` (신규 최상위 패키지)**
- `tui/pyproject.toml`
- `tui/src/musicna_tui/__init__.py`
- `tui/src/musicna_tui/client.py` — `ApiClient`(httpx 기반 REST 클라이언트)
- `tui/src/musicna_tui/widgets/__init__.py`
- `tui/src/musicna_tui/widgets/player_panel.py` — `PlayerPanel`
- `tui/src/musicna_tui/widgets/session_status.py` — `SessionStatus`
- `tui/src/musicna_tui/app.py` — `MusicnaApp`, `ensure_api_running()`, `run()`
- `tui/tests/test_client.py`, `tui/tests/test_player_panel.py`, `tui/tests/test_session_status.py`, `tui/tests/test_app.py`

**루트**
- `pyproject.toml` — `[tool.uv.workspace] members`에 `"tui"` 추가

---

### Task 1: `api/player.py` — 데이터 모델과 JSON 파서

**Files:**
- Create: `api/src/musicna_api/player.py`
- Test: `api/tests/test_player.py`

**Interfaces:**
- Produces: `PlayerStatus`(Pydantic, 필드: `is_playing: bool`, `item_title: str|None`, `item_artist: str|None`, `item_album: str|None`, `item_duration_s: float|None`, `progress_s: float|None`, `volume_percent: int|None`, `device_name: str|None`, `shuffle: bool`, `repeat_state: str`), `PlayerDevice`(필드: `id: str`, `name: str`, `is_active: bool`, `volume_percent: int|None`), `parse_playback_json(raw: str) -> PlayerStatus | None`, `parse_devices_json(raw: str) -> list[PlayerDevice]`

- [ ] **Step 1: 실패하는 테스트 작성**

`spotify_player get key playback`/`get key devices`의 실제 출력(이 머신에서 직접 실행해 확보한 형태)을 fixture로 사용한다.

```python
# api/tests/test_player.py
"""player.py의 spotify_player JSON 출력 파서 테스트.

fixture 문자열은 실제 `spotify_player get key playback`/`get key devices` 실행 결과
(2026-07-26, spotify_player 0.24.1, macOS)를 그대로 반영한 축약형이다.
"""

from musicna_api.player import PlayerDevice, PlayerStatus, parse_devices_json, parse_playback_json

PLAYBACK_JSON = """
{
  "device": {"id": "c119de5b-0e0c-4771-b5ce-f7163dd216c0", "is_active": true,
             "is_private_session": false, "is_restricted": false,
             "name": "spotify-player", "type": "Speaker", "volume_percent": 75},
  "repeat_state": "off", "shuffle_state": true,
  "context": {"uri": "spotify:playlist:37i9dQZF1DZ06evO08h9Zv"},
  "timestamp": 1784999240879, "progress_ms": 5614, "is_playing": true,
  "item": {
    "album": {"name": "Test Album"},
    "artists": [{"name": "Test Artist"}],
    "duration_ms": 219413, "name": "Test Track"
  },
  "currently_playing_type": "track"
}
"""

DEVICES_JSON = """
[{"id": "c119de5b-0e0c-4771-b5ce-f7163dd216c0", "is_active": false,
  "is_private_session": false, "is_restricted": false,
  "name": "spotify-player", "type": "Speaker", "volume_percent": 75}]
"""


def test_parse_playback_returns_status():
    status = parse_playback_json(PLAYBACK_JSON)
    assert status == PlayerStatus(
        is_playing=True,
        item_title="Test Track",
        item_artist="Test Artist",
        item_album="Test Album",
        item_duration_s=219.413,
        progress_s=5.614,
        volume_percent=75,
        device_name="spotify-player",
        shuffle=True,
        repeat_state="off",
    )


def test_parse_playback_null_returns_none():
    """아무것도 재생 중이 아니면 spotify_player가 JSON null을 출력한다."""
    assert parse_playback_json("null") is None


def test_parse_playback_missing_item_returns_status_without_track():
    raw = '{"device": null, "is_playing": false, "shuffle_state": false, "repeat_state": "off"}'
    status = parse_playback_json(raw)
    assert status is not None
    assert status.is_playing is False
    assert status.item_title is None
    assert status.device_name is None


def test_parse_devices_returns_list():
    devices = parse_devices_json(DEVICES_JSON)
    assert devices == [
        PlayerDevice(id="c119de5b-0e0c-4771-b5ce-f7163dd216c0", name="spotify-player",
                      is_active=False, volume_percent=75)
    ]


def test_parse_devices_empty_list():
    assert parse_devices_json("[]") == []
```

- [ ] **Step 2: 테스트 실행해 실패 확인**

Run: `uv run pytest api/tests/test_player.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'musicna_api.player'`

- [ ] **Step 3: 최소 구현 작성**

```python
# api/src/musicna_api/player.py
"""spotify_player(Homebrew/cargo, librespot 기반) 서브프로세스 제어.

musicna은 spotify_player를 헤드리스 데몬(`-d`, cargo `daemon` feature 빌드 필요)으로 구동해
스스로 Spotify Connect 기기가 된다. 재생 제어는 이 바이너리의 CLI 서브커맨드를 그대로
서브프로세스로 호출해 이루어진다(자체 librespot 바인딩을 작성하지 않는다).

CLI 문법은 실측 확인(2026-07-26, spotify_player 0.24.1, macOS)에 기반한다:
  spotify_player get key playback   → 현재 재생 상태 JSON (rspotify CurrentPlaybackContext 형태)
  spotify_player get key devices    → 기기 목록 JSON
  spotify_player playback play|pause|play-pause|next|previous
  spotify_player playback volume <percent:-100..100> [--offset]
  spotify_player connect --id <id> | --name <name>
"""

import json

from pydantic import BaseModel


class PlayerStatus(BaseModel):
    is_playing: bool
    item_title: str | None = None
    item_artist: str | None = None
    item_album: str | None = None
    item_duration_s: float | None = None
    progress_s: float | None = None
    volume_percent: int | None = None
    device_name: str | None = None
    shuffle: bool = False
    repeat_state: str = "off"


class PlayerDevice(BaseModel):
    id: str
    name: str
    is_active: bool
    volume_percent: int | None = None


def parse_playback_json(raw: str) -> PlayerStatus | None:
    """`spotify_player get key playback` 출력을 파싱. 재생 중이 아니면(JSON null) None."""
    data = json.loads(raw)
    if not data:
        return None
    item = data.get("item") or {}
    device = data.get("device") or {}
    artists = item.get("artists") or []
    duration_ms = item.get("duration_ms")
    progress_ms = data.get("progress_ms")
    return PlayerStatus(
        is_playing=bool(data.get("is_playing", False)),
        item_title=item.get("name"),
        item_artist=artists[0]["name"] if artists else None,
        item_album=(item.get("album") or {}).get("name"),
        item_duration_s=(duration_ms / 1000) if duration_ms is not None else None,
        progress_s=(progress_ms / 1000) if progress_ms is not None else None,
        volume_percent=device.get("volume_percent"),
        device_name=device.get("name"),
        shuffle=bool(data.get("shuffle_state", False)),
        repeat_state=data.get("repeat_state", "off"),
    )


def parse_devices_json(raw: str) -> list[PlayerDevice]:
    """`spotify_player get key devices` 출력을 파싱."""
    data = json.loads(raw)
    return [
        PlayerDevice(
            id=d["id"], name=d["name"],
            is_active=d.get("is_active", False),
            volume_percent=d.get("volume_percent"),
        )
        for d in data
    ]
```

- [ ] **Step 4: 테스트 실행해 통과 확인**

Run: `uv run pytest api/tests/test_player.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: 커밋**

```bash
git add api/src/musicna_api/player.py api/tests/test_player.py
git commit -m "feat: spotify_player JSON 출력 파서 — PlayerStatus/PlayerDevice"
```

---

### Task 2: `api/player.py` — CLI 명령 실행·래퍼 함수

**Files:**
- Modify: `api/src/musicna_api/player.py`
- Modify: `api/tests/test_player.py`

**Interfaces:**
- Consumes: `parse_playback_json`, `parse_devices_json`, `PlayerStatus`, `PlayerDevice` (Task 1)
- Produces: `SpotifyPlayerError`(Exception), `play()`, `pause()`, `play_pause()`, `next_track()`, `previous_track()`, `set_volume(percent: int) -> None`, `list_devices() -> list[PlayerDevice]`, `connect_device(device_id: str) -> None`, `get_status() -> PlayerStatus | None`

- [ ] **Step 1: 실패하는 테스트 작성**

`subprocess.run`을 모킹해 서브프로세스를 실제로 띄우지 않고 명령 구성·오류 처리만 검증한다.

```python
# api/tests/test_player.py 에 추가
import subprocess

import pytest

from musicna_api import player
from musicna_api.player import (
    SpotifyPlayerError, connect_device, get_status, list_devices,
    next_track, pause, play, play_pause, previous_track, set_volume,
)


class _FakeCompleted:
    def __init__(self, stdout="", stderr="", returncode=0):
        self.stdout, self.stderr, self.returncode = stdout, stderr, returncode


@pytest.fixture
def fake_run(monkeypatch):
    calls: list[list[str]] = []

    def _fake(cmd, **kwargs):
        calls.append(cmd)
        if cmd[1:] == ["get", "key", "devices"]:
            return _FakeCompleted(stdout='[{"id":"d1","name":"spotify-player","is_active":true,"volume_percent":50}]')
        if cmd[1:] == ["get", "key", "playback"]:
            return _FakeCompleted(stdout="null")
        return _FakeCompleted(stdout="")

    monkeypatch.setattr(subprocess, "run", _fake)
    monkeypatch.setattr("shutil.which", lambda name: "/opt/homebrew/bin/spotify_player")
    return calls


def test_play_invokes_playback_play(fake_run):
    play()
    assert fake_run[-1][1:] == ["playback", "play"]


def test_pause_invokes_playback_pause(fake_run):
    pause()
    assert fake_run[-1][1:] == ["playback", "pause"]


def test_play_pause_invokes_playback_play_pause(fake_run):
    play_pause()
    assert fake_run[-1][1:] == ["playback", "play-pause"]


def test_next_track_invokes_playback_next(fake_run):
    next_track()
    assert fake_run[-1][1:] == ["playback", "next"]


def test_previous_track_invokes_playback_previous(fake_run):
    previous_track()
    assert fake_run[-1][1:] == ["playback", "previous"]


def test_set_volume_invokes_playback_volume(fake_run):
    set_volume(42)
    assert fake_run[-1][1:] == ["playback", "volume", "42"]


def test_set_volume_rejects_out_of_range():
    with pytest.raises(ValueError):
        set_volume(150)


def test_connect_device_invokes_connect_with_id(fake_run):
    connect_device("d1")
    assert fake_run[-1][1:] == ["connect", "--id", "d1"]


def test_list_devices_parses_output(fake_run):
    devices = list_devices()
    assert devices[0].id == "d1"
    assert fake_run[-1][1:] == ["get", "key", "devices"]


def test_get_status_returns_none_when_nothing_playing(fake_run):
    assert get_status() is None
    assert fake_run[-1][1:] == ["get", "key", "playback"]


def test_missing_binary_raises_helpful_error(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda name: None)
    with pytest.raises(SpotifyPlayerError, match="brew install spotify_player"):
        play()


def test_nonzero_exit_raises_with_stderr(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda name: "/opt/homebrew/bin/spotify_player")
    monkeypatch.setattr(subprocess, "run",
                         lambda cmd, **kw: _FakeCompleted(stderr="no active device", returncode=1))
    with pytest.raises(SpotifyPlayerError, match="no active device"):
        play()


def test_timeout_raises_spotify_player_error(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda name: "/opt/homebrew/bin/spotify_player")

    def _timeout(cmd, **kw):
        raise subprocess.TimeoutExpired(cmd, kw.get("timeout", 5))

    monkeypatch.setattr(subprocess, "run", _timeout)
    with pytest.raises(SpotifyPlayerError, match="응답 시간 초과"):
        play()
```

- [ ] **Step 2: 테스트 실행해 실패 확인**

Run: `uv run pytest api/tests/test_player.py -v -k "not parse_"`
Expected: FAIL with `ImportError` (함수들이 아직 없음)

- [ ] **Step 3: 구현 작성**

`api/src/musicna_api/player.py` 맨 끝에 추가:

```python
import shutil
import subprocess


class SpotifyPlayerError(Exception):
    """spotify_player CLI 호출 실패(비정상 종료·타임아웃·미설치)."""


def _run_cli(*args: str, timeout: float = 5.0) -> str:
    binary = shutil.which("spotify_player")
    if binary is None:
        raise SpotifyPlayerError(
            "spotify_player가 설치되지 않았습니다. `brew install spotify_player`로 설치하세요."
        )
    try:
        proc = subprocess.run([binary, *args], capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as e:
        raise SpotifyPlayerError(f"spotify_player 응답 시간 초과: {' '.join(args)}") from e
    if proc.returncode != 0:
        raise SpotifyPlayerError(proc.stderr.strip() or f"spotify_player 명령 실패: {' '.join(args)}")
    return proc.stdout


def play() -> None:
    _run_cli("playback", "play")


def pause() -> None:
    _run_cli("playback", "pause")


def play_pause() -> None:
    _run_cli("playback", "play-pause")


def next_track() -> None:
    _run_cli("playback", "next")


def previous_track() -> None:
    _run_cli("playback", "previous")


def set_volume(percent: int) -> None:
    if not -100 <= percent <= 100:
        raise ValueError(f"percent는 -100~100 범위여야 합니다: {percent}")
    _run_cli("playback", "volume", str(percent))


def list_devices() -> list[PlayerDevice]:
    return parse_devices_json(_run_cli("get", "key", "devices"))


def connect_device(device_id: str) -> None:
    _run_cli("connect", "--id", device_id)


def get_status() -> PlayerStatus | None:
    return parse_playback_json(_run_cli("get", "key", "playback"))
```

- [ ] **Step 4: 테스트 실행해 통과 확인**

Run: `uv run pytest api/tests/test_player.py -v`
Expected: PASS (18 tests)

- [ ] **Step 5: 커밋**

```bash
git add api/src/musicna_api/player.py api/tests/test_player.py
git commit -m "feat: spotify_player CLI 명령 래퍼 — play/pause/next/volume/connect/status"
```

---

### Task 3: `api/player.py` — `SpotifyPlayerDaemon` 생명주기 관리

**Files:**
- Modify: `api/src/musicna_api/player.py`
- Modify: `api/tests/test_player.py`

**Interfaces:**
- Consumes: `list_devices()`, `SpotifyPlayerError` (Task 2)
- Produces: `SpotifyPlayerDaemon`(클래스: `is_running() -> bool`, `start(ready_timeout: float = 10.0) -> None`, `stop(timeout: float = 5.0) -> None`), 모듈 싱글턴 `daemon: SpotifyPlayerDaemon`

> **사전 준비 항목 실행 확인**: 이 Task를 시작하기 전에 위 "사전 준비" 절의 `cargo install spotify_player --locked --features daemon,image,notify`를 사용자와 함께 실행해 `-d` 플래그가 동작하는지 `spotify_player --help`로 확인한다. 단위 테스트는 서브프로세스를 모킹하므로 이 확인 없이도 통과하지만, Task 14(실기기 검증)에서 반드시 필요하다.

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# api/tests/test_player.py 에 추가
import time

from musicna_api.player import SpotifyPlayerDaemon


class _FakeProc:
    def __init__(self):
        self._terminated = False

    def poll(self):
        return None if not self._terminated else 0

    def terminate(self):
        self._terminated = True

    def kill(self):
        self._terminated = True

    def wait(self, timeout=None):
        if not self._terminated:
            raise subprocess.TimeoutExpired(cmd="spotify_player", timeout=timeout)


def test_daemon_start_spawns_and_waits_ready(monkeypatch):
    spawned_cmds = []

    def _fake_popen(cmd, **kwargs):
        spawned_cmds.append(cmd)
        return _FakeProc()

    ready_after = {"n": 0}

    def _fake_list_devices():
        ready_after["n"] += 1
        if ready_after["n"] < 2:
            raise SpotifyPlayerError("not ready yet")
        return []

    monkeypatch.setattr("shutil.which", lambda name: "/opt/homebrew/bin/spotify_player")
    monkeypatch.setattr(subprocess, "Popen", _fake_popen)
    monkeypatch.setattr(player, "list_devices", _fake_list_devices)
    monkeypatch.setattr(time, "sleep", lambda s: None)  # 재시도 대기 스킵

    d = SpotifyPlayerDaemon()
    d.start(ready_timeout=5.0)

    assert spawned_cmds[0][1:] == ["-d", "-o", "enable_media_control=false"]
    assert d.is_running()


def test_daemon_start_missing_binary_raises(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda name: None)
    d = SpotifyPlayerDaemon()
    with pytest.raises(SpotifyPlayerError, match="brew install"):
        d.start()


def test_daemon_start_process_exits_immediately_raises(monkeypatch):
    class _DeadProc(_FakeProc):
        def poll(self):
            return 1  # 즉시 종료

    monkeypatch.setattr("shutil.which", lambda name: "/opt/homebrew/bin/spotify_player")
    monkeypatch.setattr(subprocess, "Popen", lambda cmd, **kw: _DeadProc())
    d = SpotifyPlayerDaemon()
    with pytest.raises(SpotifyPlayerError, match="종료"):
        d.start(ready_timeout=1.0)


def test_daemon_start_idempotent_when_already_running(monkeypatch):
    calls = []
    monkeypatch.setattr("shutil.which", lambda name: "/opt/homebrew/bin/spotify_player")
    monkeypatch.setattr(subprocess, "Popen", lambda cmd, **kw: calls.append(1) or _FakeProc())
    monkeypatch.setattr(player, "list_devices", lambda: [])

    d = SpotifyPlayerDaemon()
    d.start()
    d.start()  # 두 번째 호출은 재기동하지 않아야 함
    assert len(calls) == 1


def test_daemon_stop_terminates_process(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda name: "/opt/homebrew/bin/spotify_player")
    monkeypatch.setattr(subprocess, "Popen", lambda cmd, **kw: _FakeProc())
    monkeypatch.setattr(player, "list_devices", lambda: [])

    d = SpotifyPlayerDaemon()
    d.start()
    d.stop()
    assert not d.is_running()


def test_daemon_stop_when_not_running_is_noop():
    d = SpotifyPlayerDaemon()
    d.stop()  # 예외 없이 조용히 반환
    assert not d.is_running()
```

- [ ] **Step 2: 테스트 실행해 실패 확인**

Run: `uv run pytest api/tests/test_player.py -v -k daemon`
Expected: FAIL with `ImportError: cannot import name 'SpotifyPlayerDaemon'`

- [ ] **Step 3: 구현 작성**

`api/src/musicna_api/player.py` 맨 끝에 추가:

```python
import time


class SpotifyPlayerDaemon:
    """`spotify_player -d`(cargo `daemon` feature 빌드 필요) 서브프로세스 생명주기 관리.

    macOS에서 `enable_media_control`은 기본 비활성화지만(포커스 문제), 헤드리스 실행에서는
    창이 아예 없으므로 명시적으로 꺼서 예기치 않은 동작을 막는다.
    """

    def __init__(self) -> None:
        self._proc: subprocess.Popen | None = None

    def is_running(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def start(self, ready_timeout: float = 10.0) -> None:
        if self.is_running():
            return
        binary = shutil.which("spotify_player")
        if binary is None:
            raise SpotifyPlayerError(
                "spotify_player가 설치되지 않았습니다. `brew install spotify_player`로 설치하세요."
            )
        self._proc = subprocess.Popen(
            [binary, "-d", "-o", "enable_media_control=false"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        deadline = time.monotonic() + ready_timeout
        while time.monotonic() < deadline:
            if not self.is_running():
                raise SpotifyPlayerError(
                    "spotify_player 데몬이 시작 직후 종료됐습니다 "
                    "(cargo daemon feature 빌드 여부·인증 상태를 확인하세요)"
                )
            try:
                list_devices()
                return
            except SpotifyPlayerError:
                time.sleep(0.5)
        raise SpotifyPlayerError(f"spotify_player 데몬이 {ready_timeout}초 내에 준비되지 않았습니다")

    def stop(self, timeout: float = 5.0) -> None:
        if not self.is_running():
            return
        assert self._proc is not None
        self._proc.terminate()
        try:
            self._proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            self._proc.kill()
            self._proc.wait(timeout=timeout)


daemon = SpotifyPlayerDaemon()
```

- [ ] **Step 4: 테스트 실행해 통과 확인**

Run: `uv run pytest api/tests/test_player.py -v`
Expected: PASS (24 tests)

- [ ] **Step 5: 커밋**

```bash
git add api/src/musicna_api/player.py api/tests/test_player.py
git commit -m "feat: SpotifyPlayerDaemon — spotify_player 헤드리스 데몬 생명주기 관리"
```

---

### Task 4: `api/session/metadata.py` — "spotify" 소스를 spotify_player 폴링으로 교체

**Files:**
- Modify: `api/src/musicna_api/session/metadata.py`
- Modify: `api/tests/test_session_metadata.py`

**Interfaces:**
- Consumes: `get_status() -> PlayerStatus | None`, `SpotifyPlayerError` (Task 2, `api/player.py`)
- Produces: `poll_now_playing_via_spotify_player() -> NowPlaying | None`; `poll_now_playing("spotify")`가 이 함수로 라우팅됨 (기존 시그니처 무변경)

- [ ] **Step 1: 실패하는 테스트 작성**

기존 `api/tests/test_session_metadata.py`의 AppleScript 파싱 테스트들은 "apple_music"만 남기고(더 이상 "spotify"가 AppleScript를 쓰지 않으므로), spotify_player 경로 테스트를 추가한다.

```python
# api/tests/test_session_metadata.py — 파일 전체를 아래로 교체
"""메타데이터 폴링 테스트.

- Apple Music: AppleScript(osascript) 출력 파싱 (parse_now_playing)
- Spotify: spotify_player 상태 폴링 (poll_now_playing_via_spotify_player) — musicna이 직접
  Spotify Connect 기기가 되므로(Phase 7), AppleScript는 더 이상 "spotify" 소스에 쓰이지 않는다
"""

from musicna_api.player import PlayerStatus, SpotifyPlayerError
from musicna_api.session.metadata import (
    FIELD_SEP, NowPlaying, parse_now_playing, poll_now_playing_via_spotify_player,
)


def _osa_line(*fields: str) -> str:
    return FIELD_SEP.join(fields)


def test_parse_playing_track():
    out = _osa_line("playing", "Canon in D", "Pachelbel", "Baroque Hits", "223.5", "12.3")
    now = parse_now_playing(out, source="apple_music")
    assert now == NowPlaying(
        state="playing",
        title="Canon in D",
        artist="Pachelbel",
        album="Baroque Hits",
        duration_s=223.5,
        position_s=12.3,
        source="apple_music",
    )
    assert now.track_key == "Pachelbel\x1fCanon in D"


def test_parse_paused_track_keeps_state():
    out = _osa_line("paused", "Canon in D", "Pachelbel", "", "223.5", "0.0")
    now = parse_now_playing(out, source="apple_music")
    assert now is not None
    assert now.state == "paused"
    assert now.album is None
    assert not now.is_playing


def test_parse_empty_output_returns_none():
    assert parse_now_playing("", source="apple_music") is None
    assert parse_now_playing("\n", source="apple_music") is None


def test_parse_stopped_returns_none():
    assert parse_now_playing("stopped", source="apple_music") is None


def test_spotify_player_now_playing_maps_status(monkeypatch):
    import musicna_api.session.metadata as metadata

    monkeypatch.setattr(
        metadata, "get_status",
        lambda: PlayerStatus(
            is_playing=True, item_title="Test Track", item_artist="Test Artist",
            item_album="Test Album", item_duration_s=200.0, progress_s=10.0,
        ),
    )
    now = poll_now_playing_via_spotify_player()
    assert now == NowPlaying(
        state="playing", title="Test Track", artist="Test Artist", album="Test Album",
        duration_s=200.0, position_s=10.0, source="spotify",
    )


def test_spotify_player_paused_maps_state(monkeypatch):
    import musicna_api.session.metadata as metadata

    monkeypatch.setattr(
        metadata, "get_status",
        lambda: PlayerStatus(is_playing=False, item_title="Test Track"),
    )
    now = poll_now_playing_via_spotify_player()
    assert now is not None
    assert now.state == "paused"


def test_spotify_player_none_status_returns_none(monkeypatch):
    import musicna_api.session.metadata as metadata

    monkeypatch.setattr(metadata, "get_status", lambda: None)
    assert poll_now_playing_via_spotify_player() is None


def test_spotify_player_no_track_title_returns_none(monkeypatch):
    """기기는 활성이지만 재생 중인 곡이 없는 경우(item 없음)."""
    import musicna_api.session.metadata as metadata

    monkeypatch.setattr(metadata, "get_status", lambda: PlayerStatus(is_playing=False))
    assert poll_now_playing_via_spotify_player() is None


def test_spotify_player_error_returns_none(monkeypatch):
    """데몬 미기동·인증 전 등 오류 시 크래시 없이 None(재생 없음 취급)."""
    import musicna_api.session.metadata as metadata

    def _raise():
        raise SpotifyPlayerError("daemon not running")

    monkeypatch.setattr(metadata, "get_status", _raise)
    assert poll_now_playing_via_spotify_player() is None


def test_poll_now_playing_routes_spotify_to_spotify_player(monkeypatch):
    import musicna_api.session.metadata as metadata

    monkeypatch.setattr(
        metadata, "poll_now_playing_via_spotify_player",
        lambda: NowPlaying(state="playing", title="X", source="spotify"),
    )
    result = metadata.poll_now_playing("spotify")
    assert result is not None
    assert result.title == "X"
```

- [ ] **Step 2: 테스트 실행해 실패 확인**

Run: `uv run pytest api/tests/test_session_metadata.py -v`
Expected: FAIL with `ImportError: cannot import name 'poll_now_playing_via_spotify_player'`

- [ ] **Step 3: 구현 작성**

`api/src/musicna_api/session/metadata.py`를 아래처럼 수정한다 — `_SPOTIFY_SCRIPT`와 `_SCRIPTS` 딕셔너리의 `"spotify"` 항목을 제거하고(더 이상 쓰이지 않음), spotify_player 기반 함수를 추가하고, `poll_now_playing`의 라우팅을 바꾼다.

```python
# api/src/musicna_api/session/metadata.py
"""재생 중 트랙 메타데이터.

- Apple Music: AppleScript(osascript) 폴링
- Spotify: spotify_player 상태 폴링 (Phase 7부터) — musicna이 직접 Spotify Connect 기기가
  되므로(player.py), 로컬 Spotify 데스크톱 앱을 대상으로 한 AppleScript 폴링은 더 이상
  "spotify" 소스에 쓰이지 않는다. macOS 15.4+에서 MediaRemote 사적 API가 제한되어
  Apple Music도 AppleScript를 계속 사용한다 (docs/PLAN.md).
"""

import subprocess

from pydantic import BaseModel

from musicna_api.player import SpotifyPlayerError, get_status

# osascript 한 줄 출력의 필드 구분자(record separator) — 곡명에 쉼표 등이 있어도 안전
FIELD_SEP = "\x1e"
_KEY_SEP = "\x1f"

# state, title, artist, album, duration(s), position(s)
_FIELD_COUNT = 6

# 주의: 변수명 `st`는 앱 tell 블록 안에서 스크립팅 용어와 충돌해 구문 오류를 낸다
_MUSIC_SCRIPT = f"""
tell application "Music"
    if it is running then
        set playerStateText to player state as text
        if playerStateText is "playing" or playerStateText is "paused" then
            set t to current track
            return playerStateText & "{FIELD_SEP}" & (name of t) & "{FIELD_SEP}" & (artist of t) ¬
                & "{FIELD_SEP}" & (album of t) & "{FIELD_SEP}" & (duration of t) ¬
                & "{FIELD_SEP}" & (player position)
        end if
        return playerStateText
    end if
    return ""
end tell
"""

_SCRIPTS = {"apple_music": _MUSIC_SCRIPT}


class NowPlaying(BaseModel):
    state: str
    title: str
    artist: str | None = None
    album: str | None = None
    duration_s: float | None = None
    position_s: float | None = None
    source: str

    @property
    def track_key(self) -> str:
        return f"{self.artist or ''}{_KEY_SEP}{self.title}"

    @property
    def is_playing(self) -> bool:
        return self.state == "playing"


def _to_float(value: str) -> float | None:
    try:
        return float(value.replace(",", "."))  # AppleScript는 로케일에 따라 쉼표 소수점
    except ValueError:
        return None


def parse_now_playing(output: str, source: str) -> NowPlaying | None:
    """osascript 출력 한 줄을 NowPlaying으로 파싱. 재생 중 트랙이 없으면 None."""
    line = output.strip()
    if not line:
        return None
    fields = line.split(FIELD_SEP)
    if len(fields) < _FIELD_COUNT:
        return None  # "stopped" 등 상태만 온 경우
    state, title, artist, album, duration, position = fields[:_FIELD_COUNT]
    if not title:
        return None
    return NowPlaying(
        state=state,
        title=title,
        artist=artist or None,
        album=album or None,
        duration_s=_to_float(duration),
        position_s=_to_float(position),
        source=source,
    )


def poll_now_playing_via_spotify_player() -> NowPlaying | None:
    """spotify_player 상태를 폴링해 NowPlaying으로 매핑. 오류·재생 없음이면 None."""
    try:
        status = get_status()
    except SpotifyPlayerError:
        return None
    if status is None or status.item_title is None:
        return None
    return NowPlaying(
        state="playing" if status.is_playing else "paused",
        title=status.item_title,
        artist=status.item_artist,
        album=status.item_album,
        duration_s=status.item_duration_s,
        position_s=status.progress_s,
        source="spotify",
    )


def poll_now_playing(source: str) -> NowPlaying | None:
    """현재 재생 정보를 조회한다. 실패 시 None."""
    if source == "spotify":
        return poll_now_playing_via_spotify_player()
    script = _SCRIPTS.get(source)
    if script is None:
        return None
    try:
        proc = subprocess.run(
            ["osascript", "-e", script], capture_output=True, text=True, timeout=5
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    return parse_now_playing(proc.stdout, source=source)
```

- [ ] **Step 4: 테스트 실행해 통과 확인**

Run: `uv run pytest api/tests/test_session_metadata.py -v`
Expected: PASS (10 tests)

- [ ] **Step 5: 전체 api 테스트로 회귀 확인**

Run: `uv run pytest api/tests -v`
Expected: PASS (`test_session_cli.py` 등 기존 테스트도 영향 없어야 함 — `poll_now_playing` 시그니처 무변경)

- [ ] **Step 6: 커밋**

```bash
git add api/src/musicna_api/session/metadata.py api/tests/test_session_metadata.py
git commit -m "feat: spotify 소스 메타데이터를 AppleScript에서 spotify_player 폴링으로 교체

musicna이 직접 Spotify Connect 기기가 되므로(Phase 7 player.py), 로컬 Spotify 앱을
대상으로 한 AppleScript는 더 이상 유효하지 않다. Apple Music 소스는 무수정."
```

---

### Task 5: `api/system.py` — `SystemOrchestrator`

**Files:**
- Create: `api/src/musicna_api/system.py`
- Test: `api/tests/test_system.py`

**Interfaces:**
- Consumes: `player.daemon`(`SpotifyPlayerDaemon`, Task 3), `player.SpotifyPlayerError`
- Produces: `SystemStatus`(Pydantic: `spotify_player_daemon: bool`, `session_capturing: bool`), `SystemOrchestrator`(클래스: `session_capturing() -> bool`, `start() -> None`, `stop(timeout: float = 10.0) -> None`, `status() -> SystemStatus`), 모듈 싱글턴 `orchestrator: SystemOrchestrator`

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# api/tests/test_system.py
"""SystemOrchestrator 테스트 — spotify_player 데몬과 세션 캡처 서브프로세스를 모두 모킹."""

import signal
import subprocess

import pytest

from musicna_api import player
from musicna_api.system import SystemOrchestrator, SystemStatus


class _FakeSessionProc:
    def __init__(self):
        self.signals_received: list[int] = []
        self._exited = False

    def poll(self):
        return None if not self._exited else 0

    def send_signal(self, sig):
        self.signals_received.append(sig)
        self._exited = True  # SIGINT를 받으면 정상 종료된다고 가정

    def kill(self):
        self._exited = True

    def wait(self, timeout=None):
        if not self._exited:
            raise subprocess.TimeoutExpired(cmd="musicna-session", timeout=timeout)


@pytest.fixture
def orch(monkeypatch, tmp_path):
    monkeypatch.setattr(player.daemon, "start", lambda *a, **kw: None)
    monkeypatch.setattr(player.daemon, "stop", lambda *a, **kw: None)
    monkeypatch.setattr(player.daemon, "is_running", lambda: True)
    return SystemOrchestrator(audio_dir=tmp_path)


def test_start_starts_daemon_and_session(monkeypatch, orch):
    spawned = []
    monkeypatch.setattr(subprocess, "Popen", lambda cmd, **kw: spawned.append(cmd) or _FakeSessionProc())

    orch.start()

    assert "musicna_api.session.cli" in spawned[0]
    assert "--source" in spawned[0] and "spotify" in spawned[0]
    assert orch.session_capturing()


def test_start_is_idempotent_for_session(monkeypatch, orch):
    spawned = []
    monkeypatch.setattr(subprocess, "Popen", lambda cmd, **kw: spawned.append(cmd) or _FakeSessionProc())

    orch.start()
    orch.start()

    assert len(spawned) == 1


def test_stop_sends_sigint_not_sigterm(monkeypatch, orch):
    """SIGTERM(기본 terminate())은 세션의 KeyboardInterrupt 핸들러를 트리거하지 않아
    녹음 중이던 WAV가 마무리 저장되지 않는다 — 반드시 SIGINT를 보내야 한다."""
    fake_proc = _FakeSessionProc()
    monkeypatch.setattr(subprocess, "Popen", lambda cmd, **kw: fake_proc)

    orch.start()
    orch.stop()

    assert fake_proc.signals_received == [signal.SIGINT]
    assert not orch.session_capturing()


def test_stop_when_not_capturing_is_noop(orch):
    orch.stop()  # 예외 없이 조용히 반환
    assert not orch.session_capturing()


def test_status_reports_both_components(monkeypatch, orch):
    monkeypatch.setattr(subprocess, "Popen", lambda cmd, **kw: _FakeSessionProc())
    orch.start()
    assert orch.status() == SystemStatus(spotify_player_daemon=True, session_capturing=True)
```

- [ ] **Step 2: 테스트 실행해 실패 확인**

Run: `uv run pytest api/tests/test_system.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'musicna_api.system'`

- [ ] **Step 3: 구현 작성**

```python
# api/src/musicna_api/system.py
"""오케스트레이션 — spotify_player 데몬과 캡처 세션 프로세스의 시작/중지/상태 조회.

TUI·미래의 macOS/iOS 앱은 이 모듈이 노출하는 REST(/system/*)만 호출한다 — 백그라운드
프로세스 관리 로직을 클라이언트마다 중복 구현하지 않는다 (docs/PLAN.md 코어 분리 전략).
"""

import signal
import subprocess
import sys
from pathlib import Path

from pydantic import BaseModel

from musicna_api import player


class SystemStatus(BaseModel):
    spotify_player_daemon: bool
    session_capturing: bool


class SystemOrchestrator:
    """spotify_player 데몬 + `musicna-session` 캡처 프로세스의 생명주기를 관리."""

    def __init__(self, audio_dir: Path = Path("data/audio")) -> None:
        self.audio_dir = audio_dir
        self._session_proc: subprocess.Popen | None = None

    def session_capturing(self) -> bool:
        return self._session_proc is not None and self._session_proc.poll() is None

    def start(self) -> None:
        player.daemon.start()
        if self.session_capturing():
            return
        self._session_proc = subprocess.Popen(
            [sys.executable, "-m", "musicna_api.session.cli",
             "--source", "spotify", "--out", str(self.audio_dir)]
        )

    def stop(self, timeout: float = 10.0) -> None:
        if self.session_capturing():
            assert self._session_proc is not None
            # SIGTERM(기본 terminate())은 세션의 `except KeyboardInterrupt` 핸들러를
            # 트리거하지 않아 녹음 중이던 WAV가 마무리 저장되지 않는다 — SIGINT 필요.
            self._session_proc.send_signal(signal.SIGINT)
            try:
                self._session_proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                self._session_proc.kill()
                self._session_proc.wait(timeout=timeout)
        player.daemon.stop()

    def status(self) -> SystemStatus:
        return SystemStatus(
            spotify_player_daemon=player.daemon.is_running(),
            session_capturing=self.session_capturing(),
        )


orchestrator = SystemOrchestrator()
```

- [ ] **Step 4: 테스트 실행해 통과 확인**

Run: `uv run pytest api/tests/test_system.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: 커밋**

```bash
git add api/src/musicna_api/system.py api/tests/test_system.py
git commit -m "feat: SystemOrchestrator — spotify_player 데몬+세션 캡처 오케스트레이션

세션 프로세스 정지는 SIGINT(WAV 마무리 저장 트리거)를 쓴다 — SIGTERM은 안 됨"
```

---

### Task 6: `api/player.py`·`api/system.py` — FastAPI 라우터

**Files:**
- Modify: `api/src/musicna_api/player.py`
- Modify: `api/src/musicna_api/system.py`
- Modify: `api/src/musicna_api/main.py`
- Test: `api/tests/test_player_routes.py`, `api/tests/test_system_routes.py`

**Interfaces:**
- Consumes: 모든 Task 1~5 산출물
- Produces: `player.router`(FastAPI `APIRouter`, prefix `/player`), `system.router`(prefix `/system`); `main.app`에 두 라우터 등록

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# api/tests/test_player_routes.py
"""player.py의 /player/* 엔드포인트 — FastAPI TestClient, player 함수들은 모킹."""

import pytest
from fastapi.testclient import TestClient

from musicna_api import player
from musicna_api.player import PlayerDevice, PlayerStatus, SpotifyPlayerError


@pytest.fixture
def client():
    import musicna_api.main as main
    return TestClient(main.app)


def test_play_returns_ok(monkeypatch, client):
    monkeypatch.setattr(player, "play", lambda: None)
    r = client.post("/player/play")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_play_failure_returns_503(monkeypatch, client):
    def _raise():
        raise SpotifyPlayerError("daemon not running")
    monkeypatch.setattr(player, "play", _raise)
    r = client.post("/player/play")
    assert r.status_code == 503
    assert "daemon not running" in r.json()["detail"]


def test_pause_returns_ok(monkeypatch, client):
    monkeypatch.setattr(player, "pause", lambda: None)
    assert client.post("/player/pause").status_code == 200


def test_next_returns_ok(monkeypatch, client):
    monkeypatch.setattr(player, "next_track", lambda: None)
    assert client.post("/player/next").status_code == 200


def test_previous_returns_ok(monkeypatch, client):
    monkeypatch.setattr(player, "previous_track", lambda: None)
    assert client.post("/player/previous").status_code == 200


def test_volume_valid_returns_ok(monkeypatch, client):
    calls = []
    monkeypatch.setattr(player, "set_volume", lambda p: calls.append(p))
    r = client.post("/player/volume", params={"percent": 60})
    assert r.status_code == 200
    assert calls == [60]


def test_volume_out_of_range_returns_400(monkeypatch, client):
    def _raise(p):
        raise ValueError("out of range")
    monkeypatch.setattr(player, "set_volume", _raise)
    r = client.post("/player/volume", params={"percent": 999})
    assert r.status_code == 400


def test_devices_returns_list(monkeypatch, client):
    monkeypatch.setattr(player, "list_devices",
                         lambda: [PlayerDevice(id="d1", name="spotify-player", is_active=True)])
    r = client.get("/player/devices")
    assert r.status_code == 200
    assert r.json()[0]["id"] == "d1"


def test_connect_returns_ok(monkeypatch, client):
    calls = []
    monkeypatch.setattr(player, "connect_device", lambda device_id: calls.append(device_id))
    r = client.post("/player/connect", params={"device_id": "d1"})
    assert r.status_code == 200
    assert calls == ["d1"]


def test_status_returns_player_status(monkeypatch, client):
    monkeypatch.setattr(player, "get_status",
                         lambda: PlayerStatus(is_playing=True, item_title="X"))
    r = client.get("/player/status")
    assert r.status_code == 200
    assert r.json()["item_title"] == "X"


def test_status_returns_null_when_nothing_playing(monkeypatch, client):
    monkeypatch.setattr(player, "get_status", lambda: None)
    r = client.get("/player/status")
    assert r.status_code == 200
    assert r.json() is None
```

```python
# api/tests/test_system_routes.py
"""system.py의 /system/* 엔드포인트 — FastAPI TestClient, orchestrator는 모킹."""

import pytest
from fastapi.testclient import TestClient

from musicna_api import player, system
from musicna_api.system import SystemStatus


@pytest.fixture
def client():
    import musicna_api.main as main
    return TestClient(main.app)


def test_start_returns_status(monkeypatch, client):
    monkeypatch.setattr(system.orchestrator, "start", lambda: None)
    monkeypatch.setattr(system.orchestrator, "status",
                         lambda: SystemStatus(spotify_player_daemon=True, session_capturing=True))
    r = client.post("/system/start")
    assert r.status_code == 200
    assert r.json() == {"spotify_player_daemon": True, "session_capturing": True}


def test_start_failure_returns_503(monkeypatch, client):
    def _raise():
        raise player.SpotifyPlayerError("brew install spotify_player 필요")
    monkeypatch.setattr(system.orchestrator, "start", _raise)
    r = client.post("/system/start")
    assert r.status_code == 503


def test_stop_returns_status(monkeypatch, client):
    monkeypatch.setattr(system.orchestrator, "stop", lambda: None)
    monkeypatch.setattr(system.orchestrator, "status",
                         lambda: SystemStatus(spotify_player_daemon=False, session_capturing=False))
    r = client.post("/system/stop")
    assert r.status_code == 200
    assert r.json()["session_capturing"] is False


def test_status_returns_current_state(monkeypatch, client):
    monkeypatch.setattr(system.orchestrator, "status",
                         lambda: SystemStatus(spotify_player_daemon=False, session_capturing=False))
    r = client.get("/system/status")
    assert r.status_code == 200
    assert r.json() == {"spotify_player_daemon": False, "session_capturing": False}
```

- [ ] **Step 2: 테스트 실행해 실패 확인**

Run: `uv run pytest api/tests/test_player_routes.py api/tests/test_system_routes.py -v`
Expected: FAIL (404 — 라우트가 아직 없음)

- [ ] **Step 3: `player.py`에 라우터 추가**

`api/src/musicna_api/player.py` 맨 끝에 추가:

```python
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/player", tags=["player"])


@router.post("/play")
def api_play() -> dict[str, str]:
    try:
        play()
    except SpotifyPlayerError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    return {"status": "ok"}


@router.post("/pause")
def api_pause() -> dict[str, str]:
    try:
        pause()
    except SpotifyPlayerError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    return {"status": "ok"}


@router.post("/next")
def api_next() -> dict[str, str]:
    try:
        next_track()
    except SpotifyPlayerError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    return {"status": "ok"}


@router.post("/previous")
def api_previous() -> dict[str, str]:
    try:
        previous_track()
    except SpotifyPlayerError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    return {"status": "ok"}


@router.post("/volume")
def api_set_volume(percent: int) -> dict[str, str]:
    try:
        set_volume(percent)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except SpotifyPlayerError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    return {"status": "ok"}


@router.get("/devices", response_model=list[PlayerDevice])
def api_list_devices() -> list[PlayerDevice]:
    try:
        return list_devices()
    except SpotifyPlayerError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e


@router.post("/connect")
def api_connect(device_id: str) -> dict[str, str]:
    try:
        connect_device(device_id)
    except SpotifyPlayerError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    return {"status": "ok"}


@router.get("/status", response_model=PlayerStatus | None)
def api_get_status() -> PlayerStatus | None:
    try:
        return get_status()
    except SpotifyPlayerError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
```

- [ ] **Step 4: `system.py`에 라우터 추가**

`api/src/musicna_api/system.py` 맨 끝에 추가:

```python
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/system", tags=["system"])


@router.post("/start", response_model=SystemStatus)
def api_start() -> SystemStatus:
    try:
        orchestrator.start()
    except player.SpotifyPlayerError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    return orchestrator.status()


@router.post("/stop", response_model=SystemStatus)
def api_stop() -> SystemStatus:
    orchestrator.stop()
    return orchestrator.status()


@router.get("/status", response_model=SystemStatus)
def api_status() -> SystemStatus:
    return orchestrator.status()
```

- [ ] **Step 5: `main.py`에 라우터 등록**

`api/src/musicna_api/main.py`를 수정한다. `app = FastAPI(...)` 선언 직후, `/health` 라우트 앞에 등록한다(정적 마운트보다는 반드시 앞).

```python
# api/src/musicna_api/main.py — import 구역에 추가
from musicna_api import player, system

# app = FastAPI(...) 선언 직후에 추가
app.include_router(player.router)
app.include_router(system.router)
```

- [ ] **Step 6: 테스트 실행해 통과 확인**

Run: `uv run pytest api/tests/test_player_routes.py api/tests/test_system_routes.py -v`
Expected: PASS (15 tests)

- [ ] **Step 7: 전체 api 테스트 회귀 확인**

Run: `uv run pytest api/tests core/tests -v`
Expected: PASS (전체)

- [ ] **Step 8: 커밋**

```bash
git add api/src/musicna_api/player.py api/src/musicna_api/system.py api/src/musicna_api/main.py \
        api/tests/test_player_routes.py api/tests/test_system_routes.py
git commit -m "feat: /player/*, /system/* REST 엔드포인트 등록"
```

---

### Task 7: `tui/` 패키지 스캐폴딩 + 워크스페이스 등록

**Files:**
- Modify: `pyproject.toml` (루트)
- Create: `tui/pyproject.toml`
- Create: `tui/src/musicna_tui/__init__.py`
- Create: `tui/tests/__init__.py` (빈 파일, 불필요하면 생략 가능하나 일관성을 위해 생성)

**Interfaces:**
- Produces: `tui` uv 워크스페이스 멤버, `musicna-tui` 콘솔 스크립트 등록(엔트리포인트는 Task 11에서 실제로 채움)

- [ ] **Step 1: 루트 워크스페이스에 tui 추가**

```toml
# pyproject.toml (루트) — 전체 교체
[tool.uv.workspace]
members = ["core", "api", "tui"]

[tool.uv]
# natten 0.14.x sdist는 빌드 시 torch를 요구하면서 build-system.requires에 선언하지 않음
# → venv의 torch(transcribe extra)를 그대로 쓰도록 빌드 격리 해제
no-build-isolation-package = ["natten"]

# 크로스 플랫폼 해석 시 natten sdist 메타데이터 빌드를 건너뛴다 — natten은 Darwin 전용
# 마커인데도 uv가 Linux에서 메타데이터를 뽑으려고 sdist를 빌드(setuptools·torch 부재로 실패).
# 정적 선언으로 해석만 통과시키고, 실제 휠 빌드는 macOS 설치 시(no-build-isolation) 수행된다.
[[tool.uv.dependency-metadata]]
name = "natten"
version = "0.15.1"
requires-dist = ["packaging", "torch"]
```

(주의: 위 파일 내용은 기존 natten 관련 설정을 보존하고 `members`에 `"tui"`만 추가한 것 — 실제 편집 시 기존 파일을 읽고 `members` 줄만 바꿀 것. 기존 파일 내용과 다르면 기존 내용을 우선한다.)

- [ ] **Step 2: `tui/pyproject.toml` 작성**

```toml
# tui/pyproject.toml
[project]
name = "musicna-tui"
version = "0.1.0"
description = "musicna 터미널 UI — api만 호출하는 독립 클라이언트 (Phase 7~)"
requires-python = ">=3.11,<3.13"
dependencies = [
    "textual>=0.60",
    "httpx>=0.28",
]

[project.scripts]
musicna-tui = "musicna_tui.app:run"

[dependency-groups]
dev = [
    "pytest>=8",
    "pytest-asyncio>=0.24",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/musicna_tui"]
```

- [ ] **Step 3: 패키지 스켈레톤 생성**

```python
# tui/src/musicna_tui/__init__.py
```
(빈 파일)

```python
# tui/src/musicna_tui/widgets/__init__.py
```
(빈 파일 — 디렉터리 생성 겸용, Task 9에서 위젯 추가)

- [ ] **Step 4: 워크스페이스 동기화 확인**

Run: `uv sync --all-packages`
Expected: `musicna-tui` 패키지가 설치 목록에 나타남(에러 없이 완료)

- [ ] **Step 5: 커밋**

```bash
git add pyproject.toml tui/
git commit -m "feat: tui/ 패키지 스캐폴딩 — uv 워크스페이스에 등록 (Phase 7)"
```

---

### Task 8: `tui/client.py` — `ApiClient`

**Files:**
- Create: `tui/src/musicna_tui/client.py`
- Create: `tui/tests/test_client.py`

**Interfaces:**
- Produces: `ApiClient`(클래스: `__init__(base_url: str = "http://127.0.0.1:8000", transport: httpx.BaseTransport | None = None)`, `health() -> bool`, `player_status() -> dict | None`, `player_play() -> None`, `player_pause() -> None`, `player_next() -> None`, `player_previous() -> None`, `player_volume(percent: int) -> None`, `system_start() -> dict`, `system_status() -> dict`, `close() -> None`)

- [ ] **Step 1: 실패하는 테스트 작성**

`httpx.MockTransport`로 실제 네트워크 없이 요청/응답을 검증한다.

```python
# tui/tests/test_client.py
"""ApiClient 테스트 — httpx.MockTransport로 실제 서버 없이 요청 형태를 검증."""

import httpx
import pytest

from musicna_tui.client import ApiClient


def _client_with(handler) -> ApiClient:
    return ApiClient(transport=httpx.MockTransport(handler))


def test_health_true_on_200():
    def handler(request):
        assert request.url.path == "/health"
        return httpx.Response(200, json={"status": "ok"})
    assert _client_with(handler).health() is True


def test_health_false_on_connection_error():
    def handler(request):
        raise httpx.ConnectError("refused", request=request)
    assert _client_with(handler).health() is False


def test_player_status_returns_json():
    def handler(request):
        assert request.url.path == "/player/status"
        return httpx.Response(200, json={"is_playing": True, "item_title": "X"})
    status = _client_with(handler).player_status()
    assert status == {"is_playing": True, "item_title": "X"}


def test_player_status_returns_none_when_null():
    def handler(request):
        return httpx.Response(200, json=None)
    assert _client_with(handler).player_status() is None


def test_player_play_posts_to_correct_path():
    calls = []
    def handler(request):
        calls.append((request.method, request.url.path))
        return httpx.Response(200, json={"status": "ok"})
    _client_with(handler).player_play()
    assert calls == [("POST", "/player/play")]


def test_player_pause_posts_to_correct_path():
    calls = []
    def handler(request):
        calls.append(request.url.path)
        return httpx.Response(200, json={"status": "ok"})
    _client_with(handler).player_pause()
    assert calls == ["/player/pause"]


def test_player_next_and_previous():
    calls = []
    def handler(request):
        calls.append(request.url.path)
        return httpx.Response(200, json={"status": "ok"})
    client = _client_with(handler)
    client.player_next()
    client.player_previous()
    assert calls == ["/player/next", "/player/previous"]


def test_player_volume_sends_percent_param():
    def handler(request):
        assert request.url.path == "/player/volume"
        assert request.url.params["percent"] == "55"
        return httpx.Response(200, json={"status": "ok"})
    _client_with(handler).player_volume(55)


def test_system_start_returns_json():
    def handler(request):
        assert request.url.path == "/system/start"
        return httpx.Response(200, json={"spotify_player_daemon": True, "session_capturing": True})
    result = _client_with(handler).system_start()
    assert result["spotify_player_daemon"] is True


def test_system_status_returns_json():
    def handler(request):
        assert request.url.path == "/system/status"
        return httpx.Response(200, json={"spotify_player_daemon": False, "session_capturing": False})
    result = _client_with(handler).system_status()
    assert result["session_capturing"] is False


def test_http_error_raises():
    def handler(request):
        return httpx.Response(503, json={"detail": "daemon not running"})
    with pytest.raises(httpx.HTTPStatusError):
        _client_with(handler).player_play()
```

- [ ] **Step 2: 테스트 실행해 실패 확인**

Run: `uv run pytest tui/tests/test_client.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'musicna_tui.client'`

- [ ] **Step 3: 구현 작성**

```python
# tui/src/musicna_tui/client.py
"""api 서버와 통신하는 얇은 REST 클라이언트 — TUI 위젯은 이것만 통해 api와 통신한다.

직접 서브프로세스나 파일에 접근하지 않는다 (docs/PLAN.md 코어 분리 전략: 클라이언트는
api만 호출).
"""

import httpx


class ApiClient:
    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8000",
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._http = httpx.Client(base_url=base_url, timeout=5.0, transport=transport)

    def health(self) -> bool:
        try:
            r = self._http.get("/health")
            return r.status_code == 200
        except httpx.HTTPError:
            return False

    def player_status(self) -> dict | None:
        r = self._http.get("/player/status")
        r.raise_for_status()
        return r.json()

    def player_play(self) -> None:
        self._http.post("/player/play").raise_for_status()

    def player_pause(self) -> None:
        self._http.post("/player/pause").raise_for_status()

    def player_next(self) -> None:
        self._http.post("/player/next").raise_for_status()

    def player_previous(self) -> None:
        self._http.post("/player/previous").raise_for_status()

    def player_volume(self, percent: int) -> None:
        self._http.post("/player/volume", params={"percent": percent}).raise_for_status()

    def system_start(self) -> dict:
        r = self._http.post("/system/start")
        r.raise_for_status()
        return r.json()

    def system_status(self) -> dict:
        r = self._http.get("/system/status")
        r.raise_for_status()
        return r.json()

    def close(self) -> None:
        self._http.close()
```

- [ ] **Step 4: 테스트 실행해 통과 확인**

Run: `uv run pytest tui/tests/test_client.py -v`
Expected: PASS (11 tests)

- [ ] **Step 5: 커밋**

```bash
git add tui/src/musicna_tui/client.py tui/tests/test_client.py
git commit -m "feat: ApiClient — TUI의 api REST 클라이언트"
```

---

### Task 9: `tui/widgets/player_panel.py` — `PlayerPanel`

**Files:**
- Create: `tui/src/musicna_tui/widgets/player_panel.py`
- Create: `tui/tests/test_player_panel.py`

**Interfaces:**
- Consumes: `ApiClient`(Task 8)
- Produces: `PlayerPanel`(Textual `Static` 서브클래스, 생성자 `(client: ApiClient)`, 액션: `action_play_pause`, `action_next_track`, `action_previous_track`, 메서드 `refresh_status()`)

- [ ] **Step 1: 실패하는 테스트 작성**

가짜 `ApiClient`(스텁)로 위젯의 표시·키 입력 동작을 Textual Pilot으로 검증한다.

```python
# tui/tests/test_player_panel.py
"""PlayerPanel 위젯 테스트 — Textual Pilot + 가짜 ApiClient."""

import pytest
from textual.app import App, ComposeResult

from musicna_tui.widgets.player_panel import PlayerPanel


class _FakeClient:
    def __init__(self, status=None):
        self._status = status
        self.play_calls = 0
        self.pause_calls = 0
        self.next_calls = 0
        self.previous_calls = 0

    def player_status(self):
        return self._status

    def player_play(self):
        self.play_calls += 1
        if self._status:
            self._status["is_playing"] = True

    def player_pause(self):
        self.pause_calls += 1
        if self._status:
            self._status["is_playing"] = False

    def player_next(self):
        self.next_calls += 1

    def player_previous(self):
        self.previous_calls += 1


class _PanelApp(App):
    def __init__(self, client):
        super().__init__()
        self.client = client

    def compose(self) -> ComposeResult:
        yield PlayerPanel(self.client)


@pytest.mark.asyncio
async def test_shows_no_track_when_status_none():
    app = _PanelApp(_FakeClient(status=None))
    async with app.run_test() as pilot:
        await pilot.pause()
        panel = pilot.app.query_one(PlayerPanel)
        assert "재생 중인 곡 없음" in str(panel.render())


@pytest.mark.asyncio
async def test_shows_track_title_and_artist():
    status = {"is_playing": True, "item_title": "Test Track", "item_artist": "Test Artist",
              "volume_percent": 50}
    app = _PanelApp(_FakeClient(status=status))
    async with app.run_test() as pilot:
        await pilot.pause()
        panel = pilot.app.query_one(PlayerPanel)
        rendered = str(panel.render())
        assert "Test Track" in rendered
        assert "Test Artist" in rendered


@pytest.mark.asyncio
async def test_space_toggles_play_pause():
    status = {"is_playing": False, "item_title": "X", "item_artist": "Y", "volume_percent": 50}
    client = _FakeClient(status=status)
    app = _PanelApp(client)
    async with app.run_test() as pilot:
        await pilot.pause()
        pilot.app.query_one(PlayerPanel).focus()
        await pilot.press("space")
        assert client.play_calls == 1
        assert client.pause_calls == 0


@pytest.mark.asyncio
async def test_n_key_skips_next():
    client = _FakeClient(status={"is_playing": True, "item_title": "X", "volume_percent": 50})
    app = _PanelApp(client)
    async with app.run_test() as pilot:
        await pilot.pause()
        pilot.app.query_one(PlayerPanel).focus()
        await pilot.press("n")
        assert client.next_calls == 1


@pytest.mark.asyncio
async def test_p_key_goes_previous():
    client = _FakeClient(status={"is_playing": True, "item_title": "X", "volume_percent": 50})
    app = _PanelApp(client)
    async with app.run_test() as pilot:
        await pilot.pause()
        pilot.app.query_one(PlayerPanel).focus()
        await pilot.press("p")
        assert client.previous_calls == 1


@pytest.mark.asyncio
async def test_status_fetch_error_shows_message():
    class _BrokenClient(_FakeClient):
        def player_status(self):
            raise RuntimeError("connection refused")

    app = _PanelApp(_BrokenClient())
    async with app.run_test() as pilot:
        await pilot.pause()
        panel = pilot.app.query_one(PlayerPanel)
        assert "api 연결" in str(panel.render())
```

- [ ] **Step 2: 테스트 실행해 실패 확인**

Run: `uv run pytest tui/tests/test_player_panel.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'musicna_tui.widgets.player_panel'`

- [ ] **Step 3: 구현 작성**

```python
# tui/src/musicna_tui/widgets/player_panel.py
"""현재 재생 상태 표시 + 재생 제어 위젯."""

from textual.widgets import Static

from musicna_tui.client import ApiClient


class PlayerPanel(Static):
    """재생 상태를 주기적으로 폴링해 표시하고, 키 입력으로 재생을 제어한다."""

    BINDINGS = [
        ("space", "play_pause", "재생/일시정지"),
        ("n", "next_track", "다음 곡"),
        ("p", "previous_track", "이전 곡"),
    ]
    can_focus = True

    def __init__(self, client: ApiClient) -> None:
        super().__init__()
        self.client = client

    def on_mount(self) -> None:
        self.refresh_status()
        self.set_interval(2.0, self.refresh_status)

    def refresh_status(self) -> None:
        try:
            status = self.client.player_status()
        except Exception:
            self.update("재생 상태를 가져올 수 없습니다 (api 연결 확인)")
            return
        if status is None:
            self.update("재생 중인 곡 없음")
            return
        icon = "▶" if status.get("is_playing") else "⏸"
        title = status.get("item_title") or "?"
        artist = status.get("item_artist") or "?"
        volume = status.get("volume_percent")
        self.update(f"{icon} {title} — {artist}  (볼륨 {volume}%)")

    def action_play_pause(self) -> None:
        try:
            status = self.client.player_status()
        except Exception:
            return
        if status and status.get("is_playing"):
            self.client.player_pause()
        else:
            self.client.player_play()
        self.refresh_status()

    def action_next_track(self) -> None:
        self.client.player_next()
        self.refresh_status()

    def action_previous_track(self) -> None:
        self.client.player_previous()
        self.refresh_status()
```

- [ ] **Step 4: 테스트 실행해 통과 확인**

Run: `uv run pytest tui/tests/test_player_panel.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: 커밋**

```bash
git add tui/src/musicna_tui/widgets/player_panel.py tui/tests/test_player_panel.py
git commit -m "feat: PlayerPanel 위젯 — 재생 상태 표시 + space/n/p 키 제어"
```

---

### Task 10: `tui/widgets/session_status.py` — `SessionStatus`

**Files:**
- Create: `tui/src/musicna_tui/widgets/session_status.py`
- Create: `tui/tests/test_session_status.py`

**Interfaces:**
- Consumes: `ApiClient`(Task 8)
- Produces: `SessionStatus`(Textual `Static` 서브클래스, 생성자 `(client: ApiClient)`, 메서드 `refresh_status()`)

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# tui/tests/test_session_status.py
"""SessionStatus 위젯 테스트 — Textual Pilot + 가짜 ApiClient."""

import pytest
from textual.app import App, ComposeResult

from musicna_tui.widgets.session_status import SessionStatus


class _FakeClient:
    def __init__(self, status):
        self._status = status

    def system_status(self):
        return self._status


class _StatusApp(App):
    def __init__(self, client):
        super().__init__()
        self.client = client

    def compose(self) -> ComposeResult:
        yield SessionStatus(self.client)


@pytest.mark.asyncio
async def test_shows_daemon_on_and_capturing():
    client = _FakeClient({"spotify_player_daemon": True, "session_capturing": True})
    app = _StatusApp(client)
    async with app.run_test() as pilot:
        await pilot.pause()
        widget = pilot.app.query_one(SessionStatus)
        rendered = str(widget.render())
        assert "켜짐" in rendered
        assert "녹음 중" in rendered


@pytest.mark.asyncio
async def test_shows_daemon_off_and_idle():
    client = _FakeClient({"spotify_player_daemon": False, "session_capturing": False})
    app = _StatusApp(client)
    async with app.run_test() as pilot:
        await pilot.pause()
        widget = pilot.app.query_one(SessionStatus)
        rendered = str(widget.render())
        assert "꺼짐" in rendered
        assert "대기" in rendered


@pytest.mark.asyncio
async def test_status_fetch_error_shows_message():
    class _BrokenClient(_FakeClient):
        def system_status(self):
            raise RuntimeError("connection refused")

    app = _StatusApp(_BrokenClient(None))
    async with app.run_test() as pilot:
        await pilot.pause()
        widget = pilot.app.query_one(SessionStatus)
        assert "가져올 수 없습니다" in str(widget.render())
```

- [ ] **Step 2: 테스트 실행해 실패 확인**

Run: `uv run pytest tui/tests/test_session_status.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: 구현 작성**

```python
# tui/src/musicna_tui/widgets/session_status.py
"""세션 캡처·spotify_player 데몬 상태 표시 위젯."""

from textual.widgets import Static

from musicna_tui.client import ApiClient


class SessionStatus(Static):
    """`/system/status`를 주기적으로 폴링해 데몬·캡처 상태를 표시한다."""

    def __init__(self, client: ApiClient) -> None:
        super().__init__()
        self.client = client

    def on_mount(self) -> None:
        self.refresh_status()
        self.set_interval(3.0, self.refresh_status)

    def refresh_status(self) -> None:
        try:
            status = self.client.system_status()
        except Exception:
            self.update("시스템 상태를 가져올 수 없습니다")
            return
        daemon = "켜짐" if status["spotify_player_daemon"] else "꺼짐"
        capturing = "녹음 중" if status["session_capturing"] else "대기"
        self.update(f"spotify_player 데몬: {daemon}  |  캡처: {capturing}")
```

- [ ] **Step 4: 테스트 실행해 통과 확인**

Run: `uv run pytest tui/tests/test_session_status.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: 커밋**

```bash
git add tui/src/musicna_tui/widgets/session_status.py tui/tests/test_session_status.py
git commit -m "feat: SessionStatus 위젯 — spotify_player 데몬·캡처 상태 표시"
```

---

### Task 11: `tui/app.py` — `MusicnaApp` 조립 + api 부트스트랩

**Files:**
- Create: `tui/src/musicna_tui/app.py`
- Create: `tui/tests/test_app.py`

**Interfaces:**
- Consumes: `ApiClient`(Task 8), `PlayerPanel`(Task 9), `SessionStatus`(Task 10)
- Produces: `ensure_api_running(client: ApiClient, timeout: float = 15.0) -> subprocess.Popen | None`, `MusicnaApp`(Textual `App`), `run() -> None`

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# tui/tests/test_app.py
"""MusicnaApp·ensure_api_running 테스트."""

import subprocess
import time

import pytest
from textual.app import App

import musicna_tui.app as app_module
from musicna_tui.app import MusicnaApp, ensure_api_running
from musicna_tui.widgets.player_panel import PlayerPanel
from musicna_tui.widgets.session_status import SessionStatus


class _FakeClient:
    def __init__(self, healthy_sequence):
        self._seq = list(healthy_sequence)

    def health(self):
        return self._seq.pop(0) if self._seq else self._seq[-1] if self._seq else True

    def system_start(self):
        return {"spotify_player_daemon": True, "session_capturing": True}

    def player_status(self):
        return None

    def system_status(self):
        return {"spotify_player_daemon": True, "session_capturing": True}

    def close(self):
        pass


def test_ensure_api_running_noop_when_already_healthy(monkeypatch):
    spawned = []
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **kw: spawned.append(1))
    client = _FakeClient(healthy_sequence=[True])
    proc = ensure_api_running(client)
    assert proc is None
    assert spawned == []


def test_ensure_api_running_spawns_when_unhealthy(monkeypatch):
    class _FakeProc:
        def terminate(self):
            pass

    spawned = []
    monkeypatch.setattr(subprocess, "Popen", lambda cmd, **kw: spawned.append(cmd) or _FakeProc())
    monkeypatch.setattr(time, "sleep", lambda s: None)

    client = _FakeClient(healthy_sequence=[False, False, True])
    proc = ensure_api_running(client, timeout=5.0)

    assert proc is not None
    assert "uvicorn" in " ".join(spawned[0])


def test_ensure_api_running_times_out(monkeypatch):
    class _FakeProc:
        def __init__(self):
            self.terminated = False

        def terminate(self):
            self.terminated = True

    fake_proc = _FakeProc()
    monkeypatch.setattr(subprocess, "Popen", lambda cmd, **kw: fake_proc)
    monkeypatch.setattr(time, "sleep", lambda s: None)
    # 항상 unhealthy
    monkeypatch.setattr(time, "monotonic", _make_advancing_clock())

    client = _FakeClient(healthy_sequence=[])
    client.health = lambda: False  # 항상 실패
    with pytest.raises(RuntimeError, match="기동하지"):
        ensure_api_running(client, timeout=0.01)
    assert fake_proc.terminated


def _make_advancing_clock():
    """time.monotonic()이 호출마다 큰 폭으로 흘러 짧은 timeout을 즉시 초과하게 한다."""
    state = {"t": 0.0}

    def _clock():
        state["t"] += 1.0
        return state["t"]

    return _clock


@pytest.mark.asyncio
async def test_app_composes_player_panel_and_session_status(monkeypatch):
    monkeypatch.setattr(app_module, "ensure_api_running", lambda client: None)

    app = MusicnaApp()
    monkeypatch.setattr(app.client, "system_start", lambda: {"spotify_player_daemon": True, "session_capturing": False})
    async with app.run_test() as pilot:
        await pilot.pause()
        assert pilot.app.query_one(PlayerPanel) is not None
        assert pilot.app.query_one(SessionStatus) is not None


@pytest.mark.asyncio
async def test_app_exits_with_message_when_bootstrap_fails(monkeypatch):
    """부트스트랩 실패는 화면 크래시가 아니라 App.exit(message=...) 호출로 종료해야 한다."""
    def _raise(client):
        raise RuntimeError("api 서버가 15.0초 내에 기동하지 않았습니다")

    monkeypatch.setattr(app_module, "ensure_api_running", _raise)

    exit_calls = []
    app = MusicnaApp()
    monkeypatch.setattr(app, "exit", lambda *a, **kw: exit_calls.append(kw))

    async with app.run_test() as pilot:
        await pilot.pause()

    assert len(exit_calls) == 1
    assert "기동하지 않았습니다" in exit_calls[0]["message"]
```

- [ ] **Step 2: 테스트 실행해 실패 확인**

Run: `uv run pytest tui/tests/test_app.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: 구현 작성**

```python
# tui/src/musicna_tui/app.py
"""musicna TUI 진입점 — 로컬 api 서버 부트스트랩 후 통합 대시보드를 표시한다.

api/system.py가 오케스트레이션(spotify_player 데몬·세션 캡처)을 소유한다 — 이 앱의
특수 역할은 로컬 api 서버(uvicorn) 자체가 안 떠 있을 때 부트스트랩하는 것뿐이다.
원격 클라이언트(미래 iOS 앱)는 이 부트스트랩이 필요 없다 — Mac의 api가 항상 떠 있다고
가정한다 (docs/PLAN.md).
"""

import subprocess
import sys
import time

from textual.app import App, ComposeResult
from textual.widgets import Footer, Header

from musicna_tui.client import ApiClient
from musicna_tui.widgets.player_panel import PlayerPanel
from musicna_tui.widgets.session_status import SessionStatus


def ensure_api_running(client: ApiClient, timeout: float = 15.0) -> subprocess.Popen | None:
    """로컬 api 서버가 응답하지 않으면 uvicorn을 서브프로세스로 띄우고 준비될 때까지 대기.

    이미 떠 있으면 아무것도 하지 않고 None을 반환한다(우리가 띄운 게 아니므로 종료 책임도 없음).
    """
    if client.health():
        return None
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "musicna_api.main:app", "--host", "127.0.0.1", "--port", "8000"]
    )
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if client.health():
            return proc
        time.sleep(0.5)
    proc.terminate()
    raise RuntimeError(f"api 서버가 {timeout}초 내에 기동하지 않았습니다")


class MusicnaApp(App):
    """musicna 통합 대시보드 — 재생 제어 + 세션 상태 (Phase 7 최소 셸)."""

    CSS = """
    PlayerPanel { height: 3; border: round $accent; padding: 0 1; }
    SessionStatus { height: 3; border: round $accent; padding: 0 1; }
    """

    def __init__(self) -> None:
        super().__init__()
        self.client = ApiClient()
        self._owned_api_proc: subprocess.Popen | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        yield PlayerPanel(self.client)
        yield SessionStatus(self.client)
        yield Footer()

    def on_mount(self) -> None:
        try:
            self._owned_api_proc = ensure_api_running(self.client)
            self.client.system_start()
        except Exception as e:
            # 부트스트랩 실패를 화면 크래시가 아니라 터미널에 메시지로 남기고 종료한다.
            self.exit(message=f"musicna 기동 실패: {e}")

    def on_unmount(self) -> None:
        self.client.close()
        if self._owned_api_proc is not None:
            self._owned_api_proc.terminate()


def run() -> None:
    MusicnaApp().run()


if __name__ == "__main__":
    run()
```

- [ ] **Step 4: 테스트 실행해 통과 확인**

Run: `uv run pytest tui/tests/test_app.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: 전체 tui 테스트 회귀 확인**

Run: `uv run pytest tui/tests -v`
Expected: PASS (전체)

- [ ] **Step 6: 커밋**

```bash
git add tui/src/musicna_tui/app.py tui/tests/test_app.py
git commit -m "feat: MusicnaApp — TUI 진입점, 로컬 api 부트스트랩 + 위젯 조립

musicna-tui 콘솔 스크립트(tui/pyproject.toml)가 이 run()을 가리킨다"
```

---

### Task 12: 전체 워크스페이스 회귀 테스트

**Files:** 없음(검증 전용)

- [ ] **Step 1: 전체 테스트 스위트 실행**

Run: `uv run pytest core/tests api/tests tui/tests -v`
Expected: PASS — Phase 0~6에서 쌓인 기존 테스트(66개, 이 계획 시작 시점 기준)와 이번 Task 1~11에서 추가한 테스트(약 60여 개) 전부 통과

- [ ] **Step 2: 실패가 있다면 원인 조사 후 수정**

이 Step은 조건부다 — Step 1이 이미 PASS면 건너뛴다. 실패 시 `pytest -v --tb=long`으로 스택 트레이스 확인 후 해당 Task로 돌아가 수정한다(새 커밋으로, 이전 커밋을 amend하지 않는다).

- [ ] **Step 3: uv workspace 전체 sync 재확인**

Run: `uv sync --all-packages --extra transcribe --extra analyze --extra mood`
Expected: 에러 없이 완료 (tui 패키지가 다른 extras와 충돌하지 않는지 확인 — httpx/textual은 순수 Python이라 충돌 가능성 낮음)

---

### Task 13: macOS 실기기 검증 (수동, 코드 변경 없음)

**Files:** 없음(수동 검증) — 결과는 `docs/PROGRESS.md`에 기록(Task 14)

이 Task는 자동화 테스트로 대체할 수 없는 부분이다(Phase 1·2·3·6과 동일한 이유 — 실제 spotify_player 데몬·실제 Spotify 계정 연동).

- [ ] **Step 1**: 사전 준비 — `cargo install spotify_player --locked --features daemon,image,notify` 실행(사용자 확인 후), `spotify_player --help`에 `-d`/`--daemon` 옵션이 나타나는지 확인
- [ ] **Step 2**: `spotify_player authenticate`로 인증 상태 확인 (이미 인증되어 있으면 생략)
- [ ] **Step 3**: `uv run uvicorn musicna_api.main:app`로 api 단독 기동 후 `curl -X POST http://127.0.0.1:8000/system/start`로 오케스트레이션 확인 — spotify_player 데몬이 백그라운드로 뜨는지(`ps aux | grep spotify_player`), `curl http://127.0.0.1:8000/system/status`가 `spotify_player_daemon: true`를 보고하는지
- [ ] **Step 4**: `curl -X POST http://127.0.0.1:8000/player/play`(또는 spotify_player 기기가 활성화된 상태에서) 실행 시 실제로 음악이 재생되는지 확인. `/player/next`, `/player/previous`, `/player/volume?percent=50`도 확인
- [ ] **Step 5**: 재생 중 `curl http://127.0.0.1:8000/system/status`로 `session_capturing: true`를 확인하고, `data/audio/`에 WAV가 실제로 쌓이는지 확인 — 이게 이 Phase의 핵심 마일스톤("TUI에서 재생 조작 시 실제 캡처·트랙 분할에 반영됨")
- [ ] **Step 6**: `curl -X POST http://127.0.0.1:8000/system/stop` 후 진행 중이던 WAV가 정상적으로 마무리 저장되는지 확인(파일 크기가 0이 아니고 재생 시간과 대략 일치하는지)
- [ ] **Step 7**: `uv run musicna-tui` 실행 — 별도로 떠 있는 api가 없는 상태에서 TUI가 스스로 uvicorn을 부트스트랩하는지, 플레이어 패널·세션 상태가 표시되는지, `space`/`n`/`p` 키로 재생이 실제로 반응하는지 확인
- [ ] **Step 8**: 발견된 문제(있다면)를 수정 — 이 계획의 관련 Task로 돌아가 TDD로 수정하고 새 커밋 생성

---

### Task 14: `docs/PROGRESS.md` 갱신 및 커밋·푸시

**Files:**
- Modify: `docs/PROGRESS.md`

- [ ] **Step 1**: "현재 상태"·"Phase 체크리스트"에 Phase 7 섹션 추가(Phase 6 다음, Phase 8 앞) — Task 13의 실기기 검증 결과(사전 준비 방법, 발견한 문제, 마일스톤 통과 여부)를 기존 Phase들과 같은 형식(체크리스트 + 상세 기록 절)으로 기록
- [ ] **Step 2**: "작업 로그" 표에 이번 세션 행 추가
- [ ] **Step 3**: 커밋 및 푸시

```bash
git add docs/PROGRESS.md
git commit -m "docs: Phase 7 실기기 검증 기록 — spotify_player 데몬 통합, 재생↔캡처 연동 확인"
git push origin claude/music-analysis-app-planning-rsfa6x
```

---

## Self-Review 메모 (계획 작성자용, 실행 시 참고)

- **스펙 커버리지**: 설계 문서의 Phase 7 범위(재생 제어 4종+볼륨+기기전환, 오케스트레이션 2종 프로세스, 메타데이터 교체, 최소 TUI 셸) 전부 Task 1~11에 매핑됨. 검색·플레이리스트·실시간뷰·라이브러리 브라우저는 의도적으로 Phase 8로 제외.
- **타입 일관성**: `PlayerStatus`/`PlayerDevice`/`SystemStatus` 필드명은 Task 1·5에서 정의된 그대로 Task 6(라우터)·Task 8(클라이언트)·Task 9·10(위젯)에서 동일하게 사용됨(`is_playing`, `item_title`, `item_artist`, `volume_percent`, `spotify_player_daemon`, `session_capturing`).
- **알려진 리스크**: spotify_player의 정확한 daemon 모드 플래그(`-d`/`--daemon`)와 헤드리스 기동 시 안정성은 공식 문서 인용에 의존했고 이 계획 작성 시점에 실제로 daemon feature 빌드를 검증하지 못했다 — Task 13에서 반드시 실측 검증하고, 문제 발견 시 Task 3(`SpotifyPlayerDaemon.start`)로 돌아가 실제 동작에 맞게 조정한다.
