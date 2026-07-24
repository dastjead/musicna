"""재생 중 트랙 메타데이터 — AppleScript(osascript) 출력 파싱과 폴링.

Spotify/Apple Music은 AppleScript로 곡명·아티스트·재생 위치를 제공한다.
macOS 15.4+에서 MediaRemote 사적 API가 제한되어 사용하지 않는다 (docs/PLAN.md).
"""

import subprocess

from pydantic import BaseModel

# osascript 한 줄 출력의 필드 구분자(record separator) — 곡명에 쉼표 등이 있어도 안전
FIELD_SEP = "\x1e"
_KEY_SEP = "\x1f"

# state, title, artist, album, duration(s), position(s)
_FIELD_COUNT = 6

# 주의: 변수명 `st`는 앱 tell 블록 안에서 스크립팅 용어와 충돌해 구문 오류를 낸다
_SPOTIFY_SCRIPT = f"""
tell application "Spotify"
    if it is running then
        set playerStateText to player state as text
        if playerStateText is "playing" or playerStateText is "paused" then
            set t to current track
            return playerStateText & "{FIELD_SEP}" & (name of t) & "{FIELD_SEP}" & (artist of t) ¬
                & "{FIELD_SEP}" & (album of t) & "{FIELD_SEP}" & ((duration of t) / 1000) ¬
                & "{FIELD_SEP}" & (player position)
        end if
        return playerStateText
    end if
    return ""
end tell
"""

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

_SCRIPTS = {"spotify": _SPOTIFY_SCRIPT, "apple_music": _MUSIC_SCRIPT}


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


def poll_now_playing(source: str) -> NowPlaying | None:
    """osascript를 실행해 현재 재생 정보를 조회한다. 실패 시 None."""
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
