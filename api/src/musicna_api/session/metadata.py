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
