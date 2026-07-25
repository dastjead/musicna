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
